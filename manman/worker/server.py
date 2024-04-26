import os
from dataclasses import dataclass
from enum import Enum

from manman.processbuilder import ProcessBuilder
from manman.worker.steamcmd import SteamCMD


class ServerType(Enum):
    STEAM = 1


@dataclass
class ServerID:
    server_type: ServerType
    app_id: int
    # TODO pydantic to validate?
    name: str


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
