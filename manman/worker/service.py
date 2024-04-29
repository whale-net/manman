import logging
import time
from typing import Optional
from enum import Enum

from pydantic import BaseModel
# from sqlalchemy.orm import Session

from manman.host.api_client import WorkerAPI
from manman.models import GameServerConfig
from manman.util import NamedThreadPool
from manman.worker.server import Server

logger = logging.getLogger(__name__)


class CommandType(Enum):
    START = 1
    STOP = 2
    # KILL = 3
    CUSTOM = 4


# TODO - subclass for each comamnd type + parent class factory based on enum
class ServerCommand(BaseModel):
    server_id: int
    command_type: CommandType
    command_data: Optional[str]


class WorkerService:
    def __init__(
        self,
        install_dir: str,
    ):
        # TODO error checking
        self._install_dir = install_dir

        self._threadpool = NamedThreadPool()
        # this isn't threadsafe, but this is the only thread working on it
        self._servers: list[Server] = []
        self._wapi = WorkerAPI("http://localhost:8000/")
        self._futures = []

    def run(self):
        self._create_server(5)
        count = 0
        while True:
            count += 1
            if count % 10 == 0:
                logger.info("still running - server_count=%s", len(self._servers))

            time.sleep(1)

    def _process_queue(self):
        # process worker and worker/server queue (maybe block on these? can we block on an OR?)
        pass

    def _create_server(self, game_server_config_id: int) -> Server:
        config: GameServerConfig = self._wapi.game_server_config(game_server_config_id)
        server = Server(
            wapi=self._wapi,
            root_install_directory=self._install_dir,
            config=config,
        )
        future = self._threadpool.submit(
            server.run,
            name=f"server[{server.instance.game_server_instance_id}]",
            should_update=False,
        )
        # TODO - does threadpool ever get too big with dead threads?
        self._futures.append(future)
        # TODO - need way to prune this list
        self._servers.append(server)

        # TODO TEMP
        time.sleep(20)
        server._process_queue()
