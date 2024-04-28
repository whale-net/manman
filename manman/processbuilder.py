import logging
import enum
import datetime
import subprocess
import os
import time
from queue import Queue

from manman.util import log_stream

logger = logging.getLogger(__name__)


class ProcessBuilderStatus(enum.Enum):
    NOTSTARTED = 0
    INIT = 1
    RUNNING = 2
    STOPPED = 3


class ProcessBuilder:
    def __init__(self, executable: str, stdin_delay_seconds: int = 20) -> None:
        self._executable: str = executable
        self._args: list[str] = []
        self._parameter_stdin: list[str] = []
        self._stdin_queue: Queue[str] = Queue()
        self._stdin_delay_seconds = stdin_delay_seconds
        self._process_start_time: datetime.datetime | None = None
        self._process_stop_time: datetime.datetime | None = None

    @property
    def status(self) -> ProcessBuilderStatus:
        if self._process_start_time is None:
            return ProcessBuilderStatus.NOTSTARTED
        elif self._process_stop_time is not None:
            return ProcessBuilderStatus.STOPPED

        current_time = datetime.datetime.now()
        if current_time < self._process_start_time + datetime.timedelta(
            seconds=self._stdin_delay_seconds
        ):
            return ProcessBuilderStatus.INIT
        return ProcessBuilderStatus.RUNNING

    def add_parameter(self, *parameters: str):
        for parm in parameters:
            self._args.append(parm)

    def add_parameter_stdin(self, input: str):
        self._parameter_stdin.append(input)

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
        if len(self._parameter_stdin) > 0:
            stdinput = " ".join(self._parameter_stdin)

        return command, stdinput

    def execute(self):
        command_base = os.path.basename(self._executable)

        logger.info("About to start executing [%s]", command_base)
        parm_stdinput_bytes: bytes | None = None
        if len(self._parameter_stdin) > 0:
            # this may contain sensitive info and I don't have a more sophisticated way to handle it
            # so just don't log unless debug. hopefully I don't deploy that way
            logger.debug("stdinput list: %s", self._parameter_stdin)
            stdinput = "".join(arg + "\n" for arg in self._parameter_stdin)
            parm_stdinput_bytes = bytes(stdinput, encoding="ascii")

        # proc = subprocess.run(, input=stdinput_bytes, stdout=subprocess.PIPE)
        proc = subprocess.Popen([self._executable, *self._args], stdout=subprocess.PIPE)
        # everything is delimited, so just stuffff
        if parm_stdinput_bytes is not None:
            # TODO test
            proc.communicate(parm_stdinput_bytes)
        self._process_start_time = datetime.datetime.now()

        while True:
            status = proc.poll()
            is_subprocess_running = status is None
            # logger.debug("process status %s", status)

            if is_subprocess_running and self.status == ProcessBuilderStatus.RUNNING:
                # TODO kill logic
                while not self._stdin_queue.empty():
                    stdin_command = self._stdin_queue.get()
                    if len(stdin_command) == 0:
                        continue
                    if not stdin_command.endswith("\n"):
                        stdin_command = stdin_command + "\n"

                    stdinput_bytes = bytes(stdin_command, encoding="ascii")
                    proc.communicate(stdinput_bytes)
                    log_stream(proc.stdout, logger=logger)
                    log_stream(proc.stderr, logger=logger, prefix="stderr:")

            # feels stupid to log again but whatever it's what I'm going to do for now
            log_stream(proc.stdout, logger=logger)
            log_stream(proc.stderr, logger=logger, prefix="stderr:")

            if is_subprocess_running:
                time.sleep(0.1)
                continue
            break

        self._process_stop_time = datetime.datetime.now()
        logger.info("Finished executing [%s]", command_base)

    @property
    def stdin_queue(self) -> Queue[str]:
        """
        for runtime (after process initialization) stdinput

        :return: _description_
        """
        return self._stdin_queue
