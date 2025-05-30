"""Mock ProcessBuilder that simulates process lifecycle without actual processes."""
import datetime
import logging
import time
from typing import Optional

from manman.worker.processbuilder import ProcessBuilderStatus

logger = logging.getLogger(__name__)


class MockProcessBuilder:
    """A mock ProcessBuilder that simulates process lifecycle without executing real processes."""
    
    def __init__(self, executable: str, stdin_delay_seconds: int = 5) -> None:
        self._executable: str = executable
        self._args: list[str] = []
        self._parameter_stdin: list[str] = []
        self._stdin_delay_seconds = stdin_delay_seconds
        self._process_start_time: datetime.datetime | None = None
        self._mock_stopped = False
        self._mock_killed = False

    @property
    def status(self) -> ProcessBuilderStatus:
        if self._process_start_time is None:
            return ProcessBuilderStatus.NOTSTARTED
        
        if self._mock_stopped or self._mock_killed:
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

    def run(self, wait: bool = False, extra_env: Optional[dict[str, str]] = None):
        logger.info("Mock process starting [%s]", self._executable)
        self._process_start_time = datetime.datetime.now()
        
        if wait:
            logger.info("Mock process running and waiting...")
            # Simulate some processing time
            time.sleep(0.1)
            self._mock_stopped = True
            logger.info("Mock process finished")

    def stop(self):
        if self.status in (ProcessBuilderStatus.INIT, ProcessBuilderStatus.RUNNING):
            logger.info("Mock process stopping")
            self._mock_stopped = True

    def kill(self):
        if self.status in (ProcessBuilderStatus.INIT, ProcessBuilderStatus.RUNNING):
            logger.info("Mock process killed")
            self._mock_killed = True

    def read_output(self):
        # Mock reading output - no actual output to read
        if self.status != ProcessBuilderStatus.NOTSTARTED:
            logger.debug("Mock process output read (no actual output)")

    def write_stdin(self, stdin_command: str):
        status = self.status
        if self.status != ProcessBuilderStatus.RUNNING:
            logger.warning(
                "Mock process is %s, cannot write to stdin. ignored input", status.name
            )
            return
        logger.info("Mock process received stdin: %s", stdin_command)