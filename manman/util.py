import logging
import threading
import io
import concurrent.futures
from typing import Optional

import sqlalchemy
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

__GLOBALS = {}


def log_stream(
    stream: io.BufferedReader | None,
    prefix: str | None = None,
    logger: logging.Logger = logger,
    max_lines: int | None = None,
):
    if prefix is None:
        prefix = ""

    if stream is None:
        # logger.debug(f"cannot read, stream is empty prefix=[{prefix}]")
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


class NamedThreadPool(concurrent.futures.ThreadPoolExecutor):
    def submit(
        self, fn, /, name: Optional[str] = None, *args, **kwargs
    ) -> concurrent.futures.Future:  # type: ignore
        def rename_thread(*args, **kwargs):
            if name is not None and len(name) > 0:
                threading.current_thread().name = name
            fn(*args, **kwargs)

        return super().submit(rename_thread, *args, **kwargs)


def get_sqlalchemy_engine(
    postgres_host: str, postgres_port: int, postgres_user: str, postgres_password: str
) -> sqlalchemy.engine:
    if __GLOBALS.get("engine") is None:
        connection_string = sqlalchemy.URL.create(
            "postgresql+psycopg2",
            username=postgres_user,
            password=postgres_password,
            host=postgres_host,
            port=postgres_port,
            database="manman",
        )
        __GLOBALS["engine"] = sqlalchemy.create_engine(connection_string)
    return __GLOBALS["engine"]


def init_sql_alchemy_engine(
    postgres_host: str, postgres_port: int, postgres_user: str, postgres_password: str
):
    __GLOBALS["engine"] = get_sqlalchemy_engine(
        postgres_host, postgres_port, postgres_user, postgres_password
    )


def get_session():
    if __GLOBALS.get("engine") is None:
        raise RuntimeError("global engine not defined - cannot start")
    if __GLOBALS.get("session") is None:
        __GLOBALS["session"] = sessionmaker(bind=__GLOBALS["engine"])
    return __GLOBALS["session"]()


# TODO
# def create_rabbitmq_connection():
