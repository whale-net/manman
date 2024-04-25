import logging
import threading
import io

logger = logging.getLogger(__name__)


def log_stream(
    stream: io.IOBase | None,
    prefix: str | None = None,
    logger: logging.Logger = logger,
    max_lines: int | None = None,
):
    if prefix is None:
        prefix = ""

    if stream is None:
        logger.debug(f"cannot read, stream is empty prefix=[{prefix}]")
        return

    line_count = 0
    while True:
        if max_lines is not None and line_count >= max_lines:
            logger.info(
                "exiting stream read early %s of %s max lines read",
                line_count,
                max_lines,
            )
            break

        line = stream.readline()
        if line is None or len(line) == 0:
            break
        logger.info("%s%s", prefix, line.decode("utf-8").rstrip())
        line_count += 1

    logger.debug("finished reading stream")


# TODO - make threadsafe if need be
# currently no need
class NamedThreadPool:
    def __init__(self) -> None:
        self._threads: list[threading.Thread] = []

    def __enter__(self) -> "NamedThreadPool":
        return self

    def _graceful_shutdown(self):
        logger.info("all work submitted, beginning to join threads")
        for thread in self._threads:
            try:
                logger.debug(f"joining thread: {thread.name} id={thread.native_id}")
                thread.join()
                logger.debug(f"thread completed: {thread.name} id={thread.native_id}")
            except KeyboardInterrupt:
                logger.warning(
                    f"KeyboardInterrupt recieved for thread: {thread.name} id={thread.native_id}"
                )

    def __exit__(self, exc_type, exc_value, exc_tb):
        self._graceful_shutdown()

    def __del__(self):
        self._graceful_shutdown()

    def submit(self, target, name: str, *args, **kwargs):
        thread_name = name
        if len(self.thread_name_prefix) > 0:
            thread_name = f"{self.thread_name_prefix}.{name}"

        logger.info(f"creating thread {thread_name} target={target.__name__}")
        thread = threading.Thread(target=target, name=thread_name, *args, **kwargs)
        thread.start()
        self._threads.append(thread)

    def prune():
        return
