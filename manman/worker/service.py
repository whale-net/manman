import logging
import time
from typing import Optional
from enum import Enum

import pika
from pydantic import BaseModel
# from sqlalchemy.orm import Session

from manman.models import GameServerConfig
from manman.util import NamedThreadPool, get_session
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
        root_install_dir: str,
        rabbitmq_host: str,
        rabbitmq_port: int,
        rabbitmq_username: str,
        rabbitmq_password: str,
    ):
        # TODO error checking
        self._root_install_dir = root_install_dir

        self._threadpool = NamedThreadPool()
        # this isn't threadsafe, but this is the only thread working on it
        self._servers: list[Server] = []

        credentials = pika.credentials.PlainCredentials(
            username=rabbitmq_username, password=rabbitmq_password
        )
        self._rabbitmq_conn = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=rabbitmq_host, port=rabbitmq_port, credentials=credentials
            )
        )

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
        # some of this logic should move to API
        with get_session() as sess:
            config = sess.get_one(GameServerConfig, game_server_config_id)
        server = Server(
            root_install_directory=self._root_install_dir,
            config=config,
        )
        server.start(self._threadpool, should_update=False)
        return server
