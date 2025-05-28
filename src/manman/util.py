import concurrent.futures
import io
import logging
import ssl
import threading
from typing import Optional

import amqpstorm
import sqlalchemy
from sqlmodel import Session

from manman.repository.api_client import AuthAPIClient

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


def get_sqlalchemy_engine() -> sqlalchemy.engine:
    if __GLOBALS.get("engine") is None:
        raise RuntimeError("global engine not defined - cannot start")
    return __GLOBALS["engine"]


def init_sql_alchemy_engine(
    connection_string: str,
):
    if "engine" in __GLOBALS:
        return
    __GLOBALS["engine"] = sqlalchemy.create_engine(
        connection_string,
        pool_pre_ping=True,
    )


def get_sqlalchemy_session(session: Optional[Session] = None) -> Session:
    # TODO : apply lessons from fcm on session management. this doesn't seem right.
    if session is not None:
        return session
    return Session(get_sqlalchemy_engine())


# Update RabbitMQ functions to use AMQPStorm
def init_rabbitmq(
    host: str,
    port: int,
    username: str,
    password: str,
    virtual_host: str = "/",
    ssl_enabled: bool = False,
    ssl_options=None,
):
    """Initialize RabbitMQ connection using AMQPStorm."""
    __GLOBALS["rmq_parameters"] = {
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "virtual_host": virtual_host,
        "ssl": ssl_enabled,
        "ssl_options": ssl_options,
    }

    rmq_connection = amqpstorm.Connection(
        hostname=host,
        port=port,
        username=username,
        password=password,
        virtual_host=virtual_host,
        ssl=ssl_enabled,
        ssl_options=ssl_options,
    )
    __GLOBALS["rmq_connection"] = rmq_connection
    logger.info("rmq connection established")


def get_rabbitmq_ssl_options(hostname: str) -> dict:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_default_certs(purpose=ssl.Purpose.SERVER_AUTH)
    if hostname is None or len(hostname) == 0:
        raise RuntimeError(
            "SSL is enabled but no hostname provided. "
            "Please set MANMAN_RABBITMQ_SSL_HOSTNAME"
        )
    ssl_options = {
        #'context': ssl.create_default_context(cafile='ca_certificate.pem'),
        "context": context,
        "server_hostname": hostname,
        #'check_hostname': True,        # New 2.8.0, default is False
        #'verify_mode': 'required',     # New 2.8.0, default is 'none'
    }
    return ssl_options


def get_rabbitmq_connection() -> amqpstorm.Connection:
    """Get the RabbitMQ connection."""
    if "rmq_connection" not in __GLOBALS:
        raise RuntimeError("rmq_connection not defined - cannot start")
    return __GLOBALS["rmq_connection"]


def init_auth_api_client(auth_url: str):
    __GLOBALS["auth_api_client"] = AuthAPIClient(base_url=auth_url)


def get_auth_api_client() -> AuthAPIClient:
    # api_client = __GLOBALS.get("auth_api_client")
    # if api_client is None:
    #     raise RuntimeError("api_client is not initialized")
    # return api_client
    # TODO - re-add authcz
    from unittest.mock import MagicMock

    return MagicMock()


def env_list_to_dict(env_list: list[str]) -> dict[str, str]:
    """Convert a list of environment variables to a dictionary."""
    env_dict = {}
    for env in env_list:
        if "=" not in env:
            raise ValueError(f"Invalid environment variable: {env}")
        key, value = env.split("=", 1)
        env_dict[key] = value
    return env_dict


def create_rabbitmq_vhost(
    host: str,
    port: int,
    username: str,
    password: str,
    vhost: str,
):
    """Create a RabbitMQ virtual host using the management HTTP API via AMQPStorm."""
    try:
        from amqpstorm.management import Client as ManagementClient
    except ImportError:
        raise RuntimeError("amqpstorm.management is required for vhost creation")
    mgmt = ManagementClient(
        hostname=host, username=username, password=password, port=port
    )
    mgmt.vhost.create(vhost)
    logger.info("RabbitMQ vhost created: %s", vhost)
