import logging
import threading
import io
import concurrent.futures
from typing import Optional

import sqlalchemy

logger = logging.getLogger(__name__)


def log_stream(
    stream: io.BufferedReader | None,
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
# class NamedThreadPool:
#     def __init__(self) -> None:
#         self._threads: list[threading.Thread] = []

#     def __enter__(self) -> "NamedThreadPool":
#         return self

#     def _graceful_shutdown(self):
#         logger.info("all work submitted, beginning to join threads")
#         for thread in self._threads:
#             try:
#                 logger.debug(f"joining thread: {thread.name} id={thread.native_id}")
#                 thread.join()
#                 logger.debug(f"thread completed: {thread.name} id={thread.native_id}")
#             except KeyboardInterrupt:
#                 logger.warning(
#                     f"KeyboardInterrupt recieved for thread: {thread.name} id={thread.native_id}"
#                 )

#     def __exit__(self, exc_type, exc_value, exc_tb):
#         self._graceful_shutdown()

#     def __del__(self):
#         self._graceful_shutdown()

#     def submit(self, target, thread_name: str, *args, **kwargs):
#         logger.info(f"creating thread {thread_name} target={target.__name__}")
#         kwargs.update(
#             {
#                 "target": target,
#                 "name": thread_name,
#             }
#         )
#         thread = threading.Thread(*args, **kwargs)
#         thread.start()
#         self._threads.append(thread)


#     def prune(self):
#         return
class NamedThreadPool(concurrent.futures.ThreadPoolExecutor):
    def submit(self, fn, /, name: Optional[str] = None, *args, **kwargs):  # type: ignore
        def rename_thread(*args, **kwargs):
            if name is not None and len(name) > 0:
                threading.current_thread().name = name
            fn(*args, **kwargs)

        return super().submit(rename_thread, *args, **kwargs)


# TODO this may be useless with sessions
def get_sqlalchemy_connection(
    postgres_host: str, postgres_port: int, postgres_user: str, postgres_password: str
) -> sqlalchemy.Connection:
    connection_string = sqlalchemy.URL.create(
        "postgresql+psycopg2",
        username=postgres_user,
        password=postgres_password,
        host=postgres_host,
        port=postgres_port,
        database="manman",
    )
    engine = sqlalchemy.create_engine(connection_string)
    salch = sqlalchemy.Connection(engine=engine)
    return salch


# TODO
# def create_rabbitmq_connection():
