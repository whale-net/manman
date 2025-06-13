import concurrent.futures
import io
import logging
import ssl
import threading
from typing import Optional, Union
from unittest.mock import MagicMock

import amqpstorm
import sqlalchemy
from sqlmodel import Session

from manman.repository.api_client import AuthAPIClient
from manman.repository.rabbitmq.config import BindingConfig, QueueConfig
from manman.repository.rabbitmq.connection import RobustConnection
from manman.repository.rabbitmq.subscriber import RabbitSubscriber

logger = logging.getLogger(__name__)

__GLOBALS = {}
__GLOBALS_LOCK = threading.RLock()


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
    with __GLOBALS_LOCK:
        if __GLOBALS.get("engine") is None:
            raise RuntimeError("global engine not defined - cannot start")
        return __GLOBALS["engine"]


def init_sql_alchemy_engine(
    connection_string: str,
):
    with __GLOBALS_LOCK:
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


def init_rabbitmq(
    host: str,
    port: int,
    username: str,
    password: str,
    virtual_host: str = "/",
    ssl_enabled: bool = False,
    ssl_options=None,
    heartbeat_interval: int = 30,
    max_reconnect_attempts: int = 5,
    reconnect_delay: float = 1.0,
):
    """Initialize RabbitMQ connection using AMQPStorm with robust connection handling."""
    connection_params = {
        "hostname": host,
        "port": port,
        "username": username,
        "password": password,
        "virtual_host": virtual_host,
        "ssl": ssl_enabled,
        "ssl_options": ssl_options,
    }

    def on_connection_lost():
        logger.warning("RabbitMQ connection lost - services may become unreachable")

    def on_connection_restored():
        logger.info(
            "RabbitMQ connection restored - services should be accessible again"
        )

    robust_connection = RobustConnection(
        connection_params=connection_params,
        heartbeat_interval=heartbeat_interval,
        max_reconnect_attempts=max_reconnect_attempts,
        reconnect_delay=reconnect_delay,
        on_connection_lost=on_connection_lost,
        on_connection_restored=on_connection_restored,
    )

    with __GLOBALS_LOCK:
        # Store parameters for potential reconnection
        __GLOBALS["rmq_parameters"] = connection_params.copy()
        __GLOBALS["rmq_parameters"]["heartbeat_interval"] = heartbeat_interval
        __GLOBALS["rmq_parameters"]["max_reconnect_attempts"] = max_reconnect_attempts
        __GLOBALS["rmq_parameters"]["reconnect_delay"] = reconnect_delay
        __GLOBALS["rmq_robust_connection"] = robust_connection

    logger.info(
        "rmq robust connection established with heartbeat=%ds", heartbeat_interval
    )


def get_rabbitmq_ssl_options(hostname: str) -> dict:
    """Create SSL options with enhanced security settings to prevent connection errors."""
    if hostname is None or len(hostname) == 0:
        raise RuntimeError(
            "SSL is enabled but no hostname provided. "
            "Please set MANMAN_RABBITMQ_SSL_HOSTNAME"
        )
    
    # Create SSL context with enhanced security settings
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_default_certs(purpose=ssl.Purpose.SERVER_AUTH)
    
    # Enhanced security settings to prevent SSL errors
    # Disable insecure protocols to avoid bad record MAC errors
    context.options |= ssl.OP_NO_SSLv2
    context.options |= ssl.OP_NO_SSLv3
    context.options |= ssl.OP_NO_TLSv1
    context.options |= ssl.OP_NO_TLSv1_1
    
    # Set minimum TLS version to 1.2 for better security
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    
    # Enable hostname checking and certificate verification
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    
    # Restrict to secure cipher suites to prevent MAC errors
    # This removes weak ciphers that might cause bad record MAC errors
    context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
    
    ssl_options = {
        "context": context,
        "server_hostname": hostname,
    }
    
    logger.debug("Created SSL context with enhanced security settings for hostname: %s", hostname)
    return ssl_options


def get_rabbitmq_connection() -> amqpstorm.Connection:
    """Get the RabbitMQ connection through the robust connection wrapper."""
    with __GLOBALS_LOCK:
        if "rmq_robust_connection" not in __GLOBALS:
            raise RuntimeError("rmq_robust_connection not defined - cannot start")
        robust_connection: RobustConnection = __GLOBALS["rmq_robust_connection"]

    return robust_connection.get_connection()


def get_rabbitmq_connection_provider():
    """
    Get a connection provider function for RabbitMQ subscribers.

    :return: Function that returns current valid connection
    """

    def connection_provider() -> amqpstorm.Connection:
        return get_rabbitmq_connection()

    return connection_provider


def register_subscriber_for_recovery(subscriber_callback):
    """
    Register a subscriber callback to be notified when connection is restored.

    :param subscriber_callback: Function to call when connection is restored
    """
    with __GLOBALS_LOCK:
        if "rmq_robust_connection" not in __GLOBALS:
            logger.warning(
                "rmq_robust_connection not defined - subscriber recovery will be disabled"
            )
            return
        robust_connection: RobustConnection = __GLOBALS["rmq_robust_connection"]

    robust_connection.register_subscriber_callback(subscriber_callback)


def unregister_subscriber_from_recovery(subscriber_callback):
    """
    Unregister a subscriber callback from connection recovery notifications.

    :param subscriber_callback: Function to remove from callbacks
    """
    with __GLOBALS_LOCK:
        if "rmq_robust_connection" in __GLOBALS:
            robust_connection: RobustConnection = __GLOBALS["rmq_robust_connection"]
            robust_connection.unregister_subscriber_callback(subscriber_callback)


def create_robust_subscriber(
    binding_configs: Union[BindingConfig, list[BindingConfig]],
    queue_config: QueueConfig,
):
    """
    Create a RabbitSubscriber with automatic channel recovery support.

    :param binding_configs: Binding configuration(s) for the subscriber
    :param queue_config: Queue configuration for the subscriber
    :return: RabbitSubscriber instance with recovery support
    """
    return RabbitSubscriber(
        connection_provider=get_rabbitmq_connection_provider(),
        binding_configs=binding_configs,
        queue_config=queue_config,
        recovery_registry=register_subscriber_for_recovery,
        recovery_unregistry=unregister_subscriber_from_recovery,
    )


def shutdown_rabbitmq():
    """Shutdown the RabbitMQ connection properly."""
    with __GLOBALS_LOCK:
        if "rmq_robust_connection" in __GLOBALS:
            robust_connection: RobustConnection = __GLOBALS["rmq_robust_connection"]
            robust_connection.close()
            del __GLOBALS["rmq_robust_connection"]


def init_auth_api_client(auth_url: str):
    with __GLOBALS_LOCK:
        __GLOBALS["auth_api_client"] = AuthAPIClient(base_url=auth_url)


def get_auth_api_client() -> AuthAPIClient:
    # api_client = __GLOBALS.get("auth_api_client")
    # if api_client is None:
    #     raise RuntimeError("api_client is not initialized")
    # return api_client
    # TODO - re-add authcz
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
        from amqpstorm.management import ManagementApi
    except ImportError:
        raise RuntimeError("amqpstorm.management is required for vhost creation")
    logger.info("ignoring port %s using default 15672", port)
    mgmt = ManagementApi(
        # hardcoding port, whatever
        api_url=f"http://{host}:15672",
        username=username,
        password=password,
    )
    mgmt.virtual_host.create(vhost)
    logger.info("RabbitMQ vhost created: %s", vhost)
