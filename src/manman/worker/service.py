import logging
import time

# from sqlalchemy.orm import Session
from manman.api_client import WorkerAPIClient
from manman.models import GameServerConfig
from manman.util import NamedThreadPool, get_auth_api_client
from manman.worker.server import Server

logger = logging.getLogger(__name__)


class WorkerService:
    def __init__(
        self,
        install_dir: str,
        host_url: str,
        sa_client_id: str,
        sa_client_secret: str,
    ):
        self.__is_started = False
        self.__is_stopped = False

        # TODO error checking
        self._install_dir = install_dir

        self._threadpool = NamedThreadPool()
        # this isn't threadsafe, but this is the only thread working on it
        self._servers: list[Server] = []

        self._wapi = WorkerAPIClient(
            host_url,
            auth_api_client=get_auth_api_client(),
            sa_client_id=sa_client_id,
            sa_client_secret=sa_client_secret,
        )

        self._worker_instance = self._wapi.worker_create()

        self._futures = []

    def run(self):
        # TODO - this is temporary, need to figure out a way to start/stop this more easily
        # openttd didn't work so good
        # TODO - docker compose for worker. MUST run from container for linux compatibility?
        self._create_server(3)
        count = 0
        try:
            while True:
                count += 1
                if count % 10 == 0:
                    logger.info("still running - server_count=%s", len(self._servers))
                new_server_list = []
                for server in self._servers:
                    if server.is_shutdown:
                        logger.info("%s is shutdown, pruning", server.instance)
                        continue
                    new_server_list.append(server)
                self._servers = new_server_list
                time.sleep(1)
        finally:
            self._shutdown()

    def _shutdown(self):
        if self.__is_stopped:
            return
        self._wapi.worker_shutdown(self._worker_instance)
        self.__is_stopped = True

    def _create_server(self, game_server_config_id: int):
        config: GameServerConfig = self._wapi.game_server_config(game_server_config_id)
        server = Server(
            wapi=self._wapi,
            root_install_directory=self._install_dir,
            config=config,
        )
        future = self._threadpool.submit(
            server.run,
            name=server.instance.get_thread_name(),
            # TODO - set this to false when we get blocked by steamcmd
            should_update=True,
        )
        # TODO - does threadpool ever get too big with dead threads?
        # TODO - should I use a threadpool for this? I think I should move to explicit thread management
        self._futures.append(future)
        # TODO - not thread safe, but this is the only thread working on it for now
        self._servers.append(server)
