import logging
from threading import Lock

from amqpstorm import Connection
from requests import ConnectionError

from manman.models import (
    Command,
    CommandType,
    GameServerConfig,
)

# from sqlalchemy.orm import Session
from manman.repository.api_client import WorkerAPIClient
from manman.repository.rabbitmq.config import EntityRegistrar
from manman.repository.rabbitmq.util import add_routing_key_prefix
from manman.util import NamedThreadPool, get_auth_api_client
from manman.worker.abstract_service import ManManService
from manman.worker.server import Server

logger = logging.getLogger(__name__)


class WorkerService(ManManService):
    @property
    def service_entity_type(self) -> EntityRegistrar:
        return EntityRegistrar.WORKER

    @property
    def identifier(self) -> str:
        if not hasattr(self, "_worker_instance"):
            raise RuntimeError("Worker instance not initialized")
        if not hasattr(self._worker_instance, "worker_id"):
            raise RuntimeError("Worker instance does not have a worker_id")
        if self._worker_instance.worker_id is None:
            raise RuntimeError("Worker instance worker_id is None")
        # Return the worker ID as a string
        return str(self._worker_instance.worker_id)

    def __init__(
        self,
        rabbitmq_connection: Connection,
        *,
        install_directory: str,
        host_url: str,
        sa_client_id: str,
        sa_client_secret: str,
    ):
        # pre-init
        self._wapi = WorkerAPIClient(
            host_url,
            auth_api_client=get_auth_api_client(),
            sa_client_id=sa_client_id,
            sa_client_secret=sa_client_secret,
        )

        try:
            self._worker_instance = self._wapi.worker_create()
        except ConnectionError as e:
            logger.exception(e)
            # if you see this while debugging, wait for tilt to start the api server
            raise RuntimeError("failed to connect to host - is it running?") from e
        except Exception as e:
            logger.exception(e)
            raise RuntimeError("failed to create worker instance") from e

        # SHUT DOWN OTHER WORKERS to enfroce single worker for now
        self._wapi.close_other_workers(self._worker_instance)

        super().__init__(rabbitmq_connection)

        self._install_dir = install_directory
        # TODO - deprecated, fix
        self._threadpool = NamedThreadPool()

        self._servers_lock = Lock()
        self._servers: list[Server] = []

        self._futures = []

    @staticmethod
    def _generate_common_queue_name(worker_id: int) -> str:
        return f"worker-instance.{worker_id}"

    @staticmethod
    def generate_command_queue_name(worker_id: int) -> str:
        return add_routing_key_prefix(
            WorkerService._generate_common_queue_name(worker_id), "cmd"
        )

    @property
    def legacy_command_routing_key(self) -> str:
        return self.generate_command_queue_name(self._worker_instance.worker_id)

    # TODO - deprecate these legacy methods
    def _legacy_extra_command_routing_key(self) -> list[str]:
        return [self.legacy_command_routing_key]

    @staticmethod
    def generate_status_queue_name(worker_id: int) -> str:
        return add_routing_key_prefix(
            WorkerService._generate_common_queue_name(worker_id), "status"
        )

    @property
    def legacy_status_routing_key(self) -> str:
        return self.generate_status_queue_name(self._worker_instance.worker_id)

    # TODO - deprecate these legacy methods
    def _legacy_extra_status_routing_key(self) -> list[str]:
        return [self.legacy_status_routing_key]

    def _send_heartbeat(self):
        self._wapi.worker_heartbeat(self._worker_instance)

    def _initialize_service(self):
        logger.info("noop")

    def _do_work(self, log_still_running: bool):
        # prune servers
        logger.debug("%s", log_still_running)
        self._servers_lock.acquire()
        new_server_list = []
        for server in self._servers:
            if server.is_shutdown:
                logger.info("%s is shutdown, pruning", server.instance)
                continue
            new_server_list.append(server)
        self._servers = new_server_list
        self._servers_lock.release()

    def _handle_commands(self, commands: list[Command]):
        for command in commands:
            if command.command_type == CommandType.START:
                self.__handle_start_command(command)
            elif command.command_type == CommandType.STOP:
                self.__handle_stop_command(command)
            elif command.command_type == CommandType.STDIN:
                self.__handle_stdin_command(command)
            else:
                logger.warning("unknown command for worker %s", command)

    def __handle_start_command(self, command: Command):
        # for now, just taking in the id from the arg list as-is until better typing TODO
        if len(command.command_args) != 1:
            logger.warning(
                "too many args, just want ID %s",
                command.command_args,
            )
            return
        self._servers_lock.acquire()
        game_server_config_id = int(command.command_args[0])

        can_start = True
        for server in self._servers:
            if server._config.game_server_config_id == game_server_config_id:
                logger.warning(
                    "server with app_id %s already running, ignoring create request",
                    server._config.game_server_config_id,
                )
                can_start = False
                break
        self._servers_lock.release()
        if can_start:
            self._create_server(game_server_config_id)
            # don't pass command through, doing creation in service layer for now

    def __handle_stop_command(self, command: Command):
        if len(command.command_args) != 1:
            logger.warning(
                "too many args, just want ID %s",
                command.command_args,
            )
            return
        game_server_config_id = int(command.command_args[0])
        self._servers_lock.acquire()
        for server in self._servers:
            if server._config.game_server_config_id == game_server_config_id:
                logger.info("stopping server %s", server.instance)
                # pass command through
                server.execute_command(command)
        self._servers_lock.release()

    def __handle_stdin_command(self, command: Command):
        if len(command.command_args) < 1:
            logger.warning(
                "too few args, at least need ID %s",
                command.command_args,
            )
            return
        game_server_config_id = int(command.command_args[0])
        self._servers_lock.acquire()
        for server in self._servers:
            if server._config.game_server_config_id == game_server_config_id:
                logger.info("sending stdin to server %s", server.instance)
                # chain command
                server.execute_command(command)
                break
        self._servers_lock.release()

    def _shutdown(self):
        self._wapi.worker_shutdown(self._worker_instance)

    def _create_server(self, game_server_config_id: int):
        config: GameServerConfig = self._wapi.game_server_config(game_server_config_id)

        # Temp check to prevent duplicates
        # ideally this will be a check against the database via api
        self._servers_lock.acquire()
        game_server_ids = {
            server._game_server.game_server_id for server in self._servers
        }
        if config.game_server_id in game_server_ids:
            logger.warning(
                "server with app_id %s already running, ignoring create request",
                config.game_server_id,
            )
            self._servers_lock.release()
            return
        self._servers_lock.release()

        server = Server(
            wapi=self._wapi,
            rabbitmq_connection=self._rabbitmq_connection,
            root_install_directory=self._install_dir,
            config=config,
            worker_id=self._worker_instance.worker_id,
        )
        future = self._threadpool.submit(
            server.run,
            name=server.instance.get_thread_name(),
            # TODO - set this to false when we get blocked by steamcmd
            should_update=True,
        )
        # TODO - just make server responsible for its own thread management
        # TODO - does threadpool ever get too big with dead threads?
        # TODO - should I use a threadpool for this? I think I should move to explicit thread management
        self._futures.append(future)
        # TODO - not thread safe, but this is the only thread working on it for now
        self._servers_lock.acquire()
        self._servers.append(server)
        self._servers_lock.release()
