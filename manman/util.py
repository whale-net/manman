import logging
import threading
import io
import concurrent.futures
from typing import Optional

import sqlalchemy
from sqlalchemy.orm import sessionmaker
import pika

from manman.api_client import AuthAPIClient

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
        return

    line_count = 0
    while True:
        if max_lines is not None and line_count >= max_lines:
            break

        line = stream.readline()
        if line is None or len(line) == 0:
            break
        logger.info("%s%s", prefix, line.decode("utf-8").rstrip())
        line_count += 1 if max_lines is not None else 0


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
        __GLOBALS["engine"] = sqlalchemy.create_engine(
            connection_string,
            pool_pre_ping=True,
        )
    return __GLOBALS["engine"]


def init_sql_alchemy_engine(
    postgres_host: str, postgres_port: int, postgres_user: str, postgres_password: str
):
    __GLOBALS["engine"] = get_sqlalchemy_engine(
        postgres_host, postgres_port, postgres_user, postgres_password
    )


def get_sqlalchemy_session():
    if __GLOBALS.get("engine") is None:
        raise RuntimeError("global engine not defined - cannot start")
    if __GLOBALS.get("session") is None:
        # expire_on_commit allows usage of objects after session context closes
        # __GLOBALS["session"] = sessionmaker(bind=__GLOBALS["engine"], expire_on_commit=False)
        __GLOBALS["session"] = sessionmaker(bind=__GLOBALS["engine"])
    return __GLOBALS["session"]()


def init_rabbitmq(connection_parms: pika.ConnectionParameters):
    __GLOBALS["rmq_parameters"] = connection_parms


def get_rabbitmq_connection():
    stored_parms = __GLOBALS.get("rmq_parameters")
    if stored_parms is None:
        raise RuntimeError("need to provide init rabbitmq")

    if "rmq_connection" not in __GLOBALS:
        __GLOBALS["rmq_connection"] = pika.BlockingConnection(stored_parms)
    return __GLOBALS["rmq_connection"]


def init_auth_api_client(auth_url: str):
    __GLOBALS["auth_api_client"] = AuthAPIClient(base_url=auth_url)


def get_auth_api_client() -> AuthAPIClient:
    api_client = __GLOBALS.get("auth_api_client")
    if api_client is None:
        raise RuntimeError("api_client is not initialized")
    return api_client
