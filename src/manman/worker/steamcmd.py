import logging
import os

from manman.processbuilder import ProcessBuilder

logger = logging.getLogger(__name__)


class SteamCMD:
    DEFAULT_USERNAME = "anonymous"
    DEFAULT_EXECUTABLE = "steamcmd"

    def __init__(
        self,
        install_dir: str,
        username: str = DEFAULT_USERNAME,
        password: str | None = None,
        steamcmd_executable: str | None = None,
    ) -> None:
        self._install_dir = install_dir

        if username != SteamCMD.DEFAULT_USERNAME and password is None:
            raise Exception(
                "non-anonymous username specified and password not provided"
            )
        self._username = username
        self._password = password

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
        if not os.path.exists(self._install_dir):
            logger.info("directroy not found, creating=[%s]", self._install_dir)
            os.makedirs(self._install_dir)

        # leave a little something behind
        # check_file_name = os.path.join(self._install_dir, ".manman")
        # pathlib.Path(check_file_name).touch()

        cb = ProcessBuilder(self._steamcmd_executable)
        # steamcmd is different and uses + for args
        cb.add_parameter("+force_install_dir", self._install_dir)
        cb.add_parameter("+login", self._username)
        if self._password is not None:
            cb.add_parameter_stdin(self._password)
        cb.add_parameter("+app_update", str(app_id))
        cb.add_parameter("+exit")

        cb.execute()

        logger.info("installed app_id=[%s]", app_id)
