import os
from enum import Enum
from typing import Optional

from pydantic import BaseModel

from manman.processbuilder import ProcessBuilder
from manman.worker.steamcmd import SteamCMD


class ServerTypeEnum(Enum):
    STEAM = 1


class CommandType(Enum):
    START = 1
    STOP = 2
    # KILL = 3
    CUSTOM = 4


class ServerID(BaseModel):
    id: str
    server_type: ServerTypeEnum
    app_id: int
    name: str


class ServerCommand(BaseModel):
    server_id: ServerID
    command_type: CommandType
    command_data: Optional[str]


# TODO logging
class Server:
    def __init__(
        self,
        server_id: ServerID,
        # TODO where should this come from?
        root_install_directory: str,
        executable: str,
    ) -> None:
        self._server_id = server_id
        self._root_install_directory = root_install_directory
        self._executable = executable

        self._server_directory = os.path.join(
            self._root_install_directory,
            self._server_id.server_type.name.lower(),
            f"{server_id.app_id}-{server_id.name}",
        )

    @property
    def server_id(self) -> ServerID:
        return self._server_id

    def run(self, args: list[str] | None = None, should_update: bool = True):
        if args is None:
            args = []

        steam = SteamCMD(self._server_directory)
        if should_update:
            steam.install(app_id=self.server_id.app_id)

        executable_path = os.path.join(self._server_directory, self._executable)
        pb = ProcessBuilder(executable=executable_path)
        for arg in args:
            pb.add_parameter(arg)

        pb.execute()
