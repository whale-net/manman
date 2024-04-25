import logging
import subprocess
import os
import time

from manman.util import log_stream

logger = logging.getLogger(__name__)


class ProcessBuilder:
    def __init__(self, executable: str) -> None:
        self._executable = executable
        self._args: list[str] = []
        self._stdinput: list[str] = []

    @property
    def executable(self) -> str:
        return self._executable

    def add_parameter(self, *parameters: str):
        for parm in parameters:
            self._args.append(parm)

    def add_stdin(self, input: str):
        self._stdinput.append(input)

    def render_command(self) -> tuple[str, str | None]:
        """
        render executable + parameters

        :param self: _description_
        :param str: _description_
        :return: command to run, stdin
        """
        command = self._executable
        if len(self._args) > 0:
            command += " " + " ".join(self._args)
        stdinput = None
        if len(self._stdinput) > 0:
            stdinput = " ".join(stdinput)

        return command, stdinput

    def execute_command(self):
        command_base = os.path.basename(self._executable)

        logger.info("About to start executing [%s]", command_base)
        stdinput_bytes: bytes | None = None
        if len(self._stdinput) > 0:
            # this may contain sensitive info and I don't have a more sophisticated way to handle it
            # so just don't log unless debug. hopefully I don't deploy that way
            logger.debug("stdinput list: %s", self._stdinput)
            stdinput = "".join(arg + "\n" for arg in self._stdinput)
            stdinput_bytes = bytes(stdinput, encoding="ascii")

        # proc = subprocess.run(, input=stdinput_bytes, stdout=subprocess.PIPE)
        proc = subprocess.Popen([self._executable, *self._args], stdout=subprocess.PIPE)
        # everything is delimited, so just stuffff
        if stdinput_bytes is not None:
            # TODO test
            proc.communicate(stdinput_bytes)

        while True:
            status = proc.poll()
            logger.info("process status %s", status)

            log_stream(proc.stdout, logger=logger)
            log_stream(proc.stderr, logger=logger, prefix="stderr:")

            if status is None:
                time.sleep(1)
                continue
            break

        logger.info("Finished executing [%s]", command_base)
