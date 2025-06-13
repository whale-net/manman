import logging
import os
import threading
from typing import Optional

import sqlalchemy
import typer
import uvicorn
from typing_extensions import Annotated

import alembic
import alembic.command
import alembic.config
from manman.logging_config import setup_logging
from manman.repository.rabbitmq.config import ExchangeRegistry
from manman.util import (
    create_rabbitmq_vhost,
    get_rabbitmq_ssl_options,
    get_sqlalchemy_engine,
    init_rabbitmq,
    init_sql_alchemy_engine,
)

app = typer.Typer()
logger = logging.getLogger(__name__)


def _init_common_services(
    rabbitmq_host: str,
    rabbitmq_port: int,
    rabbitmq_username: str,
    rabbitmq_password: str,
    app_env: Optional[str],
    enable_ssl: bool,
    rabbitmq_ssl_hostname: Optional[str],
    should_run_migration_check: bool,
    create_vhost: bool = False,
):
    """Initialize common services required by both APIs."""
    if should_run_migration_check and _need_migration():
        raise RuntimeError("migration needs to be ran before starting")
    virtual_host = f"manman-{app_env}" if app_env else "/"
    # Optionally create vhost via management API
    if create_vhost and app_env == "dev":
        create_rabbitmq_vhost(
            host=rabbitmq_host,
            port=rabbitmq_port,
            username=rabbitmq_username,
            password=rabbitmq_password,
            vhost=virtual_host,
        )

    # Initialize with AMQPStorm connection parameters
    init_rabbitmq(
        host=rabbitmq_host,
        port=rabbitmq_port,
        username=rabbitmq_username,
        password=rabbitmq_password,
        virtual_host=virtual_host,
        ssl_enabled=enable_ssl,
        ssl_options=get_rabbitmq_ssl_options(
            hostname=rabbitmq_ssl_hostname,
        )
        if enable_ssl
        else None,
    )

    # declare rabbitmq exchanges
    from manman.util import get_rabbitmq_connection

    rmq_connection = get_rabbitmq_connection()

    exchanges = []
    for exchange in ExchangeRegistry:
        exchanges.append(exchange.value)
    for exchange in exchanges:
        rmq_connection.channel().exchange.declare(
            exchange=exchange,
            exchange_type="topic",
            durable=True,
        )
        logger.info("Exchange declared %s", exchange)


@app.command()
def start_experience_api(
    rabbitmq_host: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_HOST")],
    rabbitmq_port: Annotated[int, typer.Option(envvar="MANMAN_RABBITMQ_PORT")],
    rabbitmq_username: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_USER")],
    rabbitmq_password: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_PASSWORD")],
    app_env: Annotated[Optional[str], typer.Option(envvar="APP_ENV")] = None,
    port: int = 8000,
    workers: Annotated[
        Optional[int],
        typer.Option(
            help="Number of uvicorn workers (default: 1 if not specified, or CPU count * 2 + 1 if gunicorn was used)"
        ),
    ] = 1,  # Default to 1 for direct uvicorn
    should_run_migration_check: Optional[bool] = True,
    enable_ssl: Annotated[
        bool, typer.Option(envvar="MANMAN_RABBITMQ_ENABLE_SSL")
    ] = False,
    rabbitmq_ssl_hostname: Annotated[
        str, typer.Option(envvar="MANMAN_RABBITMQ_SSL_HOSTNAME")
    ] = None,
    log_otlp: Annotated[
        bool,
        typer.Option(
            envvar="MANMAN_LOG_OTLP", help="Enable OpenTelemetry OTLP logging"
        ),
    ] = False,
    create_vhost: Annotated[
        bool, typer.Option(help="Create RabbitMQ vhost before initialization")
    ] = False,
):
    """Start the experience API directly with Uvicorn."""
    # Setup logging
    setup_logging(
        service_name="manman-experience-api", enable_otel=log_otlp, force_setup=log_otlp
    )

    _init_common_services(
        rabbitmq_host=rabbitmq_host,
        rabbitmq_port=rabbitmq_port,
        rabbitmq_username=rabbitmq_username,
        rabbitmq_password=rabbitmq_password,
        app_env=app_env,
        enable_ssl=enable_ssl,
        rabbitmq_ssl_hostname=rabbitmq_ssl_hostname,
        should_run_migration_check=should_run_migration_check,
        create_vhost=create_vhost,
    )

    from manman.host.asgi import create_experience_app

    app_instance = create_experience_app()

    log_level = os.getenv("LOG_LEVEL", "info").lower()

    logger.info(
        "Starting Experience API with Uvicorn (workers: %d, port: %d)", workers, port
    )
    uvicorn.run(
        app_instance,
        host="0.0.0.0",
        port=port,
        workers=workers,
        log_level=log_level,
    )


@app.command()
def start_status_api(
    rabbitmq_host: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_HOST")],
    rabbitmq_port: Annotated[int, typer.Option(envvar="MANMAN_RABBITMQ_PORT")],
    rabbitmq_username: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_USER")],
    rabbitmq_password: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_PASSWORD")],
    app_env: Annotated[Optional[str], typer.Option(envvar="APP_ENV")] = None,
    port: int = 8000,
    workers: Annotated[
        Optional[int],
        typer.Option(
            help="Number of uvicorn workers (default: 1 if not specified, or CPU count * 2 + 1 if gunicorn was used)"
        ),
    ] = 1,  # Default to 1 for direct uvicorn
    should_run_migration_check: Optional[bool] = True,
    enable_ssl: Annotated[
        bool, typer.Option(envvar="MANMAN_RABBITMQ_ENABLE_SSL")
    ] = False,
    rabbitmq_ssl_hostname: Annotated[
        str, typer.Option(envvar="MANMAN_RABBITMQ_SSL_HOSTNAME")
    ] = None,
    log_otlp: Annotated[
        bool,
        typer.Option(
            envvar="MANMAN_LOG_OTLP", help="Enable OpenTelemetry OTLP logging"
        ),
    ] = False,
    create_vhost: Annotated[
        bool, typer.Option(help="Create RabbitMQ vhost before initialization")
    ] = False,
):
    """Start the status API directly with Uvicorn."""
    # Setup logging
    setup_logging(
        service_name="manman-status-api", enable_otel=log_otlp, force_setup=log_otlp
    )

    _init_common_services(
        rabbitmq_host=rabbitmq_host,
        rabbitmq_port=rabbitmq_port,
        rabbitmq_username=rabbitmq_username,
        rabbitmq_password=rabbitmq_password,
        app_env=app_env,
        enable_ssl=enable_ssl,
        rabbitmq_ssl_hostname=rabbitmq_ssl_hostname,
        should_run_migration_check=should_run_migration_check,
        create_vhost=create_vhost,
    )

    from manman.host.asgi import create_status_app

    app_instance = create_status_app()
    log_level = os.getenv("LOG_LEVEL", "info").lower()

    logger.info(
        "Starting Status API with Uvicorn (workers: %d, port: %d)", workers, port
    )
    uvicorn.run(
        app_instance,
        host="0.0.0.0",
        port=port,
        workers=workers,
        log_level=log_level,
    )


@app.command()
def start_worker_dal_api(
    rabbitmq_host: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_HOST")],
    rabbitmq_port: Annotated[int, typer.Option(envvar="MANMAN_RABBITMQ_PORT")],
    rabbitmq_username: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_USER")],
    rabbitmq_password: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_PASSWORD")],
    app_env: Annotated[Optional[str], typer.Option(envvar="APP_ENV")] = None,
    port: int = 8000,
    workers: Annotated[
        Optional[int],
        typer.Option(
            help="Number of uvicorn workers (default: 1 if not specified, or CPU count * 2 + 1 if gunicorn was used)"
        ),
    ] = 1,  # Default to 1 for direct uvicorn
    should_run_migration_check: Optional[bool] = True,
    enable_ssl: Annotated[
        bool, typer.Option(envvar="MANMAN_RABBITMQ_ENABLE_SSL")
    ] = False,
    rabbitmq_ssl_hostname: Annotated[
        str, typer.Option(envvar="MANMAN_RABBITMQ_SSL_HOSTNAME")
    ] = None,
    log_otlp: Annotated[
        bool,
        typer.Option(
            envvar="MANMAN_LOG_OTLP", help="Enable OpenTelemetry OTLP logging"
        ),
    ] = False,
    create_vhost: Annotated[
        bool, typer.Option(help="Create RabbitMQ vhost before initialization")
    ] = False,
):
    """Start the worker DAL API directly with Uvicorn."""
    # Setup logging
    setup_logging(
        service_name="manman-worker-dal-api", enable_otel=log_otlp, force_setup=log_otlp
    )

    _init_common_services(
        rabbitmq_host=rabbitmq_host,
        rabbitmq_port=rabbitmq_port,
        rabbitmq_username=rabbitmq_username,
        rabbitmq_password=rabbitmq_password,
        app_env=app_env,
        enable_ssl=enable_ssl,
        rabbitmq_ssl_hostname=rabbitmq_ssl_hostname,
        should_run_migration_check=should_run_migration_check,
        create_vhost=create_vhost,
    )

    from manman.host.asgi import create_worker_dal_app

    app_instance = create_worker_dal_app()
    log_level = os.getenv("LOG_LEVEL", "info").lower()

    logger.info(
        "Starting Worker DAL API with Uvicorn (workers: %d, port: %d)", workers, port
    )
    uvicorn.run(
        app_instance,
        host="0.0.0.0",
        port=port,
        workers=workers,
        log_level=log_level,
    )


@app.command()
def start_status_processor(
    rabbitmq_host: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_HOST")],
    rabbitmq_port: Annotated[int, typer.Option(envvar="MANMAN_RABBITMQ_PORT")],
    rabbitmq_username: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_USER")],
    rabbitmq_password: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_PASSWORD")],
    app_env: Annotated[Optional[str], typer.Option(envvar="APP_ENV")] = None,
    should_run_migration_check: Optional[bool] = True,
    enable_ssl: Annotated[
        bool, typer.Option(envvar="MANMAN_RABBITMQ_ENABLE_SSL")
    ] = False,
    rabbitmq_ssl_hostname: Annotated[
        str, typer.Option(envvar="MANMAN_RABBITMQ_SSL_HOSTNAME")
    ] = None,
    log_otlp: Annotated[
        bool,
        typer.Option(
            envvar="MANMAN_LOG_OTLP", help="Enable OpenTelemetry OTLP logging"
        ),
    ] = False,
    create_vhost: Annotated[
        bool, typer.Option(help="Create RabbitMQ vhost before initialization")
    ] = False,
):
    """Start the status event processor that handles status-related pub/sub messages."""

    # Setup logging first - this is a standalone service (no uvicorn)
    setup_logging(
        service_name="manman-status-processor",
        enable_otel=log_otlp,
        force_setup=log_otlp,
    )

    logger.info("Starting status event processor...")

    _init_common_services(
        rabbitmq_host=rabbitmq_host,
        rabbitmq_port=rabbitmq_port,
        rabbitmq_username=rabbitmq_username,
        rabbitmq_password=rabbitmq_password,
        app_env=app_env,
        enable_ssl=enable_ssl,
        rabbitmq_ssl_hostname=rabbitmq_ssl_hostname,
        should_run_migration_check=should_run_migration_check,
        create_vhost=create_vhost,
    )

    # Start the status event processor (pub/sub only, no HTTP server other than health check)
    from fastapi import FastAPI  # Add FastAPI import

    from manman.host.api.shared import (
        add_health_check,  # Ensure this import is present or add it
    )
    from manman.host.status_processor import StatusEventProcessor
    from manman.util import get_rabbitmq_connection

    # Define and run health check API in a separate thread
    health_check_app = FastAPI(title="ManMan Status Processor Health Check")
    add_health_check(health_check_app)

    def run_health_check_server():
        # Use uvicorn for the health check server too
        uvicorn.run(
            health_check_app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
        )

    health_check_thread = threading.Thread(target=run_health_check_server, daemon=True)
    health_check_thread.start()

    logger.info("Health check API for status processor started on port 8000")

    processor = StatusEventProcessor(get_rabbitmq_connection())
    processor.run()


@app.command()
def run_migration():
    _run_migration(get_sqlalchemy_engine())


@app.command()
def create_migration(migration_message: Optional[str] = None):
    # TODO - make use of this? or remove
    if os.environ.get("ENVIRONMENT", "DEV") == "PROD":
        raise RuntimeError("cannot create revisions in production")
    _create_migration(get_sqlalchemy_engine(), message=migration_message)


@app.command()
def run_downgrade(target: str):
    config = _get_alembic_config()
    engine = get_sqlalchemy_engine()
    with engine.begin() as conn:
        config.attributes["connection"] = conn
        alembic.command.downgrade(config, target)


@app.callback()
def callback(
    db_connection_string: Annotated[str, typer.Option(envvar="MANMAN_POSTGRES_URL")],
):
    # Setup basic logging as early as possible for CLI operations
    setup_logging()
    init_sql_alchemy_engine(db_connection_string)


# alembic helpers
# TODO context manager to reduce duplication
# TODO - figure out what I meant with the previous TODO
def _get_alembic_config() -> alembic.config.Config:
    alembic_path = "./alembic.ini"
    config = alembic.config.Config(alembic_path)
    return config


def _need_migration() -> bool:
    config = _get_alembic_config()
    engine = get_sqlalchemy_engine()
    with engine.begin() as conn:
        # TODO remove connection from env and use this?
        config.attributes["connection"] = conn
        try:
            alembic.command.check(config)
        except alembic.command.util.AutogenerateDiffsDetected:
            return True

        return False


def _run_migration(engine: sqlalchemy.Engine):
    config = _get_alembic_config()
    # with engine.begin() as conn:
    # config.attributes["connection"] = conn
    alembic.command.upgrade(config, "head")


def _create_migration(engine: sqlalchemy.Engine, message: Optional[str] = None):
    if not _need_migration():
        raise RuntimeError("no migration creation required")

    config = _get_alembic_config()
    # with engine.begin() as conn:
    # config.attributes["connection"] = conn
    alembic.command.revision(config, message=message, autogenerate=True)
