import logging
import os
import pathlib

from manman.commandbuilder import CommandBuilder

logger = logging.getLogger(__name__)


class SteamCMD:
    DEFAULT_USERNAME = "anonymous"
    DEFAULT_EXECUTABLE = "steamcmd"

    def __init__(
        self,
        install_dir: str,
        username: str | None = None,
        password: str | None = None,
        steamcmd_executable: str | None = None,
    ) -> None:
        self._install_dir = install_dir

        self._username = username or SteamCMD.DEFAULT_USERNAME
        self._password = password
        if self._username != SteamCMD.DEFAULT_USERNAME and self._password is None:
            raise Exception(
                "non-anonymous username specified and password not provided"
            )

        self._steamcmd_executable = steamcmd_executable or SteamCMD.DEFAULT_EXECUTABLE

        logger.info("using login [%s]", self._username)
        # don't log password
        logger.info("using steamcmd executable [%s]", self._steamcmd_executable)

    def install(self, app_id: int):
        """
        install provided app_id
        limited to a single server per app_id

        :param app_id: steam app_id
        """
        logger.info("installing app_id=[%s]", app_id)

        # prepare directory
        install_dir = os.path.join(self._install_dir, str(app_id))
        if not os.path.exists(install_dir):
            logger.info("directroy not found, creating=[%s]", install_dir)
            os.makedirs(install_dir)

        # leave a little something behind
        check_file_name = os.path.join(install_dir, ".manman")
        pathlib.Path(check_file_name).touch()

        cb = CommandBuilder(self._steamcmd_executable)
        # steamcmd is different and uses + for args
        cb.add_parameter("+force_install_dir", install_dir)
        cb.add_parameter("+login", self._username)
        if self._password is not None:
            cb.add_stdin(self._password)
        cb.add_parameter("+app_update", str(app_id))
        cb.add_parameter("+exit")

        cb.execute_command()

        logger.info("installed app_id=[%s]", app_id)
