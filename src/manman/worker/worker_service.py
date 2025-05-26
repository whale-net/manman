import logging
import time
from datetime import datetime, timedelta
from threading import Lock

from amqpstorm import Connection
from requests import ConnectionError

from manman.models import (
    Command,
    CommandType,
    GameServerConfig,
    StatusInfo,
    StatusType,
)

# from sqlalchemy.orm import Session
from manman.repository.api_client import WorkerAPIClient
from manman.repository.rabbitmq import RabbitCommandSubscriber, RabbitStatusPublisher
from manman.repository.rabbitmq.util import add_routing_key_prefix
from manman.util import NamedThreadPool, get_auth_api_client
from manman.worker.server import Server

logger = logging.getLogger(__name__)


class WorkerService:
    RMQ_EXCHANGE = "worker"

    def __init__(
        self,
        install_dir: str,
        host_url: str,
        sa_client_id: str,
        sa_client_secret: str,
        rabbitmq_connection: Connection,
    ):
        self.__is_started = False
        self.__is_stopped = False

        # TODO error checking
        self._install_dir = install_dir

        self._threadpool = NamedThreadPool()

        self._servers_lock = Lock()
        self._servers: list[Server] = []

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

        self._rabbitmq_connection = rabbitmq_connection
        self._status_publisher = RabbitStatusPublisher(
            connection=self._rabbitmq_connection,
            exchange=WorkerService.RMQ_EXCHANGE,
            routing_key_base=self.status_routing_key,
        )
        self._command_provider = RabbitCommandSubscriber(
            connection=self._rabbitmq_connection,
            exchange=WorkerService.RMQ_EXCHANGE,
            queue_name=self.command_routing_key,
        )

        # heartbeat
        self._wapi.worker_heartbeat(self._worker_instance)

        self._futures = []

        # TODO - https://github.com/whale-net/manman/issues/44
        self._status_publisher.publish(
            status=StatusInfo.create(
                self.__class__.__name__,
                StatusType.CREATED,
                worker_id=self._worker_instance.worker_id,
            ),
        )

    @staticmethod
    def _generate_common_queue_name(worker_id: int) -> str:
        return f"worker-instance.{worker_id}"

    @staticmethod
    def generate_command_queue_name(worker_id: int) -> str:
        return add_routing_key_prefix(
            WorkerService._generate_common_queue_name(worker_id), "cmd"
        )

    @property
    def command_routing_key(self) -> str:
        return self.generate_command_queue_name(self._worker_instance.worker_id)

    @staticmethod
    def generate_status_queue_name(worker_id: int) -> str:
        return add_routing_key_prefix(
            WorkerService._generate_common_queue_name(worker_id), "status"
        )

    @property
    def status_routing_key(self) -> str:
        return self.generate_status_queue_name(self._worker_instance.worker_id)

    def run(self):
        loop_log_time = datetime.now()
        loop_heartbeat_time = datetime.now()
        try:
            logger.info("worker service starting")
            # TODO - https://github.com/whale-net/manman/issues/44
            self._status_publisher.publish(
                status=StatusInfo.create(
                    self.__class__.__name__,
                    StatusType.RUNNING,
                    worker_id=self._worker_instance.worker_id,
                ),
            )
            while True:
                # TODO - periodically check if the worker instance is tracked as alive. exit if not
                #  doing single worker architecture for now, so not needed
                now = datetime.now()
                if now - loop_log_time > timedelta(seconds=30):
                    logger.info("still running - server_count=%s", len(self._servers))
                    loop_log_time = now
                if now - loop_heartbeat_time > timedelta(seconds=2):
                    self._wapi.worker_heartbeat(self._worker_instance)
                    loop_heartbeat_time = now

                # prune servers
                self._servers_lock.acquire()
                new_server_list = []
                for server in self._servers:
                    if server.is_shutdown:
                        logger.info("%s is shutdown, pruning", server.instance)
                        continue
                    new_server_list.append(server)
                self._servers = new_server_list
                self._servers_lock.release()

                # process commands
                self._process_commands()

                # no need to spin
                time.sleep(0.1)
        finally:
            self._shutdown()

    def _shutdown(self):
        if self.__is_stopped:
            return
        self._wapi.worker_shutdown(self._worker_instance)
        # TODO - https://github.com/whale-net/manman/issues/44
        self._status_publisher.publish(
            status=StatusInfo.create(
                self.__class__.__name__,
                StatusType.COMPLETE,
                worker_id=self._worker_instance.worker_id,
            ),
        )
        self._command_provider.shutdown()
        self._status_publisher.shutdown()
        self.__is_stopped = True

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

    def _process_commands(self):
        commands = self._command_provider.get_commands()
        if commands is not None:
            for command in commands:
                logger.info("received command %s", command)
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
