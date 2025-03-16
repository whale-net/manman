import logging
import time
from datetime import datetime, timedelta
from threading import Lock

from amqpstorm import Connection
from requests import ConnectionError

# from sqlalchemy.orm import Session
from manman.api_client import WorkerAPIClient
from manman.models import CommandType, GameServerConfig
from manman.repository.rabbit import RabbitMessageProvider
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

        self._rabbitmq_connection = rabbitmq_connection
        self._message_provider = RabbitMessageProvider(
            connection=self._rabbitmq_connection,
            exchange=WorkerService.RMQ_EXCHANGE,
            queue_name=self.rmq_queue_name,
        )

        self._futures = []

    @property
    def rmq_queue_name(self) -> str:
        return f"worker.{self._worker_instance.worker_id}"

    def run(self):
        loop_log_time = datetime.now()
        try:
            logger.info("worker service starting")
            while True:
                if datetime.now() - loop_log_time > timedelta(seconds=30):
                    logger.info("still running - server_count=%s", len(self._servers))
                    loop_log_time = datetime.now()

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
                # TODO - offload to another function
                commands = self._message_provider.get_commands()
                if commands is not None:
                    for command in commands:
                        logger.info("received command %s", command)
                        if command.command_type == CommandType.START:
                            # for now, just taking in the id from the arg list as-is until better typing TODO
                            if len(command.command_args) != 1:
                                logger.warning(
                                    "too many args, just want ID %s",
                                    command.command_args,
                                )
                                continue
                            self._create_server(int(command.command_args[0]))
                        elif command.command_type == CommandType.STOP:
                            # TODO - stop the server?
                            logger.info("stop requested %s, but ignored", command)
                        else:
                            logger.warning("unknown command for worker %s", command)

                # no need to spin
                time.sleep(0.1)
        finally:
            self._shutdown()

    def _shutdown(self):
        if self.__is_stopped:
            return
        self._wapi.worker_shutdown(self._worker_instance)
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
