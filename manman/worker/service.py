import logging
import time
from typing import Optional
from enum import Enum

import pika
from pydantic import BaseModel
# from sqlalchemy.orm import Session

from manman.host.api_client import WorkerAPI
from manman.models import GameServerConfig
from manman.util import NamedThreadPool, get_rabbitmq_connection
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
        rmq_parameters: pika.ConnectionParameters,
    ):
        # TODO error checking
        self._install_dir = install_dir

        self._threadpool = NamedThreadPool()
        # this isn't threadsafe, but this is the only thread working on it
        self._servers: list[Server] = []

        self._rabbitmq_conn = get_rabbitmq_connection(rmq_parameters)

        self._wapi = WorkerAPI("http://localhost:8000/")

    def run(self):
        server = self._create_server(5)
        self._servers.append(server)
        while True:
            logger.info("still running")
            # for server in self._servers:
            #     logger.info("%s", server._pb.status)
            time.sleep(0.25)

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
        server.start(self._threadpool, should_update=False)
        return server
