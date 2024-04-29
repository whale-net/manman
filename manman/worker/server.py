import os
import logging

# import sqlalchemy
# from sqlalchemy.orm import Session

# from pydantic import BaseModel

from manman.models import GameServerConfig, GameServer, GameServerInstance
from manman.processbuilder import ProcessBuilder
from manman.worker.steamcmd import SteamCMD
from manman.host.api_client import WorkerAPI
from manman.util import NamedThreadPool, get_session

logger = logging.getLogger(__name__)


# TODO logging
class Server:
    def __init__(
        self,
        wapi: WorkerAPI,
        root_install_directory: str,
        config: GameServerConfig,
    ) -> None:
        self._config = config
        self._api = wapi

        self._instance = self._api.game_server_instance_create(config)
        self._game_server = self._api.game_server(self._config.game_server_id)

        with get_session() as sess:
            self._game_server: GameServer = sess.get_one(
                GameServer, config.game_server_id
            )
            self._instance: GameServerInstance = GameServerInstance(
                game_server_config_id=self._config.game_server_config_id
            )
            sess.add(self._instance)
            sess.flush()
            sess.expunge(self._game_server)
            sess.expunge(self._instance)
            sess.commit()

        logger.info("starting instance %s", self._instance.game_server_instance_id)

        self._root_install_directory = root_install_directory
        self._server_directory = os.path.join(
            self._root_install_directory,
            # game_server is unique on server_type_appid
            self._game_server.server_type.name.lower(),
            str(self._game_server.app_id),
            # and then config is unique on game_server_id
            self._config.name,
        )

        executable_path = os.path.join(self._server_directory, self._config.executable)
        pb = ProcessBuilder(executable=executable_path)
        for arg in self._config.args:
            pb.add_parameter(arg)
        self._pb = pb

    @property
    def instance(self) -> GameServerInstance:
        return self._instance

    def add_stdin(self, input: str):
        # TODO check if pb is running
        self._pb.stdin_queue.put(input)

    def start(
        self,
        threadpool: NamedThreadPool,
        # extra_args: list[str] | None = None,
        should_update: bool = True,
    ):
        # if extra_args is None:
        #     extra_args = []

        def fn():
            if should_update:
                steam = SteamCMD(self._server_directory)
                steam.install(app_id=self._game_server.app_id)
            # for arg in extra_args:
            #     pb.add_parameter(arg)
            self._pb.execute()

        threadpool.submit(fn, name=f"server[{self.instance.game_server_instance_id}]")
