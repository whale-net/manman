import json
import logging
import logging.config
import os
import threading
from pathlib import Path
from typing import Optional

import alembic
import alembic.command
import alembic.config
import sqlalchemy
import typer
import uvicorn
from typing_extensions import Annotated

from manman.config import ManManConfig
from manman.logging_config import get_uvicorn_log_config, setup_logging
from manman.util import (
    get_rabbitmq_ssl_options,
    get_sqlalchemy_engine,
    init_rabbitmq,
    init_sql_alchemy_engine,
)
from manman.worker.server import Server
from manman.worker.worker_service import WorkerService

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
):
    """Initialize common services required by both APIs."""
    if should_run_migration_check and _need_migration():
        raise RuntimeError("migration needs to be ran before starting")
    virtual_host = f"manman-{app_env}" if app_env else "/"

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

    exchanges = [Server.RMQ_EXCHANGE, WorkerService.RMQ_EXCHANGE]
    for exchange in exchanges:
        rmq_connection.channel().exchange.declare(
            exchange=exchange,
            exchange_type="topic",
            durable=True,
        )
        logger.info("Exchange declared %s", exchange)


def _generate_openapi_spec(app, service_name: str):
    """Generate and save OpenAPI specification for a FastAPI app."""
    output_path = Path("./openapi-specs")
    output_path.mkdir(exist_ok=True)

    # Generate OpenAPI spec
    openapi_spec = app.openapi()

    # Save to file with service name
    spec_file = output_path / f"{service_name}.json"
    with open(spec_file, "w") as f:
        json.dump(openapi_spec, f, indent=2)

    logger.info(f"OpenAPI spec saved to: {spec_file}")
    print(f"OpenAPI spec saved to: {spec_file}")


@app.command()
def start_experience_api(
    rabbitmq_host: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_HOST")],
    rabbitmq_port: Annotated[int, typer.Option(envvar="MANMAN_RABBITMQ_PORT")],
    rabbitmq_username: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_USER")],
    rabbitmq_password: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_PASSWORD")],
    app_env: Annotated[Optional[str], typer.Option(envvar="APP_ENV")] = None,
    port: int = 8000,
    should_run_migration_check: Optional[bool] = True,
    enable_ssl: Annotated[
        bool, typer.Option(envvar="MANMAN_RABBITMQ_ENABLE_SSL")
    ] = False,
    rabbitmq_ssl_hostname: Annotated[
        str, typer.Option(envvar="MANMAN_RABBITMQ_SSL_HOSTNAME")
    ] = None,
    generate_openapi: Annotated[
        bool,
        typer.Option(
            help="Generate OpenAPI spec and exit instead of running the server"
        ),
    ] = False,
    log_otlp: Annotated[
        bool, 
        typer.Option(
            envvar="MANMAN_LOG_OTLP",
            help="Enable OpenTelemetry OTLP logging"
        )
    ] = False,
):
    """Start the experience API (host layer) that provides game server management and user-facing functionality."""
    # Setup logging first
    setup_logging(service_name="experience-api", enable_otel=log_otlp)

    _init_common_services(
        rabbitmq_host=rabbitmq_host,
        rabbitmq_port=rabbitmq_port,
        rabbitmq_username=rabbitmq_username,
        rabbitmq_password=rabbitmq_password,
        app_env=app_env,
        enable_ssl=enable_ssl,
        rabbitmq_ssl_hostname=rabbitmq_ssl_hostname,
        should_run_migration_check=should_run_migration_check,
    )

    # Create FastAPI app with only host/experience routes
    from fastapi import FastAPI

    from manman.host.api.experience import router as experience_router
    from manman.host.api.shared import add_health_check

    experience_app = FastAPI(title="ManMan Experience API", root_path="/experience")
    experience_app.include_router(experience_router)
    add_health_check(experience_app)

    # If OpenAPI generation is requested, generate spec and exit
    if generate_openapi:
        _generate_openapi_spec(experience_app, ManManConfig.EXPERIENCE_API)
        return

    uvicorn.run(
        experience_app,
        host="0.0.0.0",
        port=port,
        log_config=get_uvicorn_log_config("experience-api"),
    )


@app.command()
def start_status_api(
    rabbitmq_host: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_HOST")],
    rabbitmq_port: Annotated[int, typer.Option(envvar="MANMAN_RABBITMQ_PORT")],
    rabbitmq_username: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_USER")],
    rabbitmq_password: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_PASSWORD")],
    app_env: Annotated[Optional[str], typer.Option(envvar="APP_ENV")] = None,
    port: int = 8000,
    should_run_migration_check: Optional[bool] = True,
    enable_ssl: Annotated[
        bool, typer.Option(envvar="MANMAN_RABBITMQ_ENABLE_SSL")
    ] = False,
    rabbitmq_ssl_hostname: Annotated[
        str, typer.Option(envvar="MANMAN_RABBITMQ_SSL_HOSTNAME")
    ] = None,
    generate_openapi: Annotated[
        bool,
        typer.Option(
            help="Generate OpenAPI spec and exit instead of running the server"
        ),
    ] = False,
    log_otlp: Annotated[
        bool, 
        typer.Option(
            envvar="MANMAN_LOG_OTLP",
            help="Enable OpenTelemetry OTLP logging"
        )
    ] = False,
):
    """Start the status API that provides status and monitoring functionality."""
    # Setup logging first
    setup_logging(service_name="status-api", enable_otel=log_otlp)

    _init_common_services(
        rabbitmq_host=rabbitmq_host,
        rabbitmq_port=rabbitmq_port,
        rabbitmq_username=rabbitmq_username,
        rabbitmq_password=rabbitmq_password,
        app_env=app_env,
        enable_ssl=enable_ssl,
        rabbitmq_ssl_hostname=rabbitmq_ssl_hostname,
        should_run_migration_check=should_run_migration_check,
    )

    # Create FastAPI app with status routes
    from fastapi import FastAPI

    from manman.host.api.shared import add_health_check
    from manman.host.api.status import router as status_router

    status_app = FastAPI(title="ManMan Status API", root_path="/status")
    status_app.include_router(status_router)
    add_health_check(status_app)

    # If OpenAPI generation is requested, generate spec and exit
    if generate_openapi:
        _generate_openapi_spec(status_app, ManManConfig.STATUS_API)
        return

    uvicorn.run(
        status_app,
        host="0.0.0.0",
        port=port,
        log_config=get_uvicorn_log_config("status-api"),
    )


@app.command()
def start_worker_dal_api(
    rabbitmq_host: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_HOST")],
    rabbitmq_port: Annotated[int, typer.Option(envvar="MANMAN_RABBITMQ_PORT")],
    rabbitmq_username: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_USER")],
    rabbitmq_password: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_PASSWORD")],
    app_env: Annotated[Optional[str], typer.Option(envvar="APP_ENV")] = None,
    port: int = 8000,
    should_run_migration_check: Optional[bool] = True,
    enable_ssl: Annotated[
        bool, typer.Option(envvar="MANMAN_RABBITMQ_ENABLE_SSL")
    ] = False,
    rabbitmq_ssl_hostname: Annotated[
        str, typer.Option(envvar="MANMAN_RABBITMQ_SSL_HOSTNAME")
    ] = None,
    generate_openapi: Annotated[
        bool,
        typer.Option(
            help="Generate OpenAPI spec and exit instead of running the server"
        ),
    ] = False,
    log_otlp: Annotated[
        bool, 
        typer.Option(
            envvar="MANMAN_LOG_OTLP",
            help="Enable OpenTelemetry OTLP logging"
        )
    ] = False,
):
    """Start the worker DAL API that provides data access endpoints for worker services."""
    # Setup logging first
    setup_logging(service_name="worker-dal-api", enable_otel=log_otlp)

    _init_common_services(
        rabbitmq_host=rabbitmq_host,
        rabbitmq_port=rabbitmq_port,
        rabbitmq_username=rabbitmq_username,
        rabbitmq_password=rabbitmq_password,
        app_env=app_env,
        enable_ssl=enable_ssl,
        rabbitmq_ssl_hostname=rabbitmq_ssl_hostname,
        should_run_migration_check=should_run_migration_check,
    )

    # Create FastAPI app with only worker DAL routes
    from fastapi import FastAPI

    from manman.host.api.shared import add_health_check
    from manman.host.api.worker_dal import server_router, worker_router

    worker_dal_app = FastAPI(
        title="ManMan Worker DAL API",
        root_path="/workerdal",  # Configure root path for reverse proxy
    )
    worker_dal_app.include_router(server_router)
    worker_dal_app.include_router(worker_router)
    # For worker DAL, health check should be at the root level since root_path handles the /workerdal prefix
    add_health_check(worker_dal_app)

    # If OpenAPI generation is requested, generate spec and exit
    if generate_openapi:
        _generate_openapi_spec(worker_dal_app, ManManConfig.WORKER_DAL_API)
        return

    uvicorn.run(
        worker_dal_app,
        host="0.0.0.0",
        port=port,
        log_config=get_uvicorn_log_config("worker-dal-api"),
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
            envvar="MANMAN_LOG_OTLP",
            help="Enable OpenTelemetry OTLP logging"
        )
    ] = False,
):
    """Start the status event processor that handles status-related pub/sub messages."""

    # Setup logging first - this is a standalone service (no uvicorn)
    setup_logging(service_name="status-processor", enable_otel=log_otlp)

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
        # Use our uvicorn config for the health check server too
        uvicorn.run(
            health_check_app,
            host="0.0.0.0",
            port=8000,
            # NOTE: this sets the name of the service in the logs
            log_config=get_uvicorn_log_config("status-processor"),
        )

    health_check_thread = threading.Thread(target=run_health_check_server, daemon=True)
    health_check_thread.start()

    logger.info("Health check API for status processor started on port 8000")

    processor = StatusEventProcessor(get_rabbitmq_connection())
    processor.run()


@app.command()
def generate_openapi(
    api_name: Annotated[
        str,
        typer.Argument(
            help=f"Name of the API to generate OpenAPI spec for. Options: {', '.join(ManManConfig.KNOWN_API_NAMES)}"
        ),
    ]
):
    """Generate OpenAPI specification for a specific API without requiring environment setup."""

    # Setup minimal logging for the generation process
    setup_logging(service_name="openapi-generator")

    # Validate API name
    try:
        validated_api_name = ManManConfig.validate_api_name(api_name)
        api_config = ManManConfig.get_api_config(validated_api_name)
    except ValueError as e:
        raise typer.BadParameter(str(e))

    logger.info(f"Generating OpenAPI spec for {api_name}...")

    # Create FastAPI apps with minimal dependencies (no database, no RabbitMQ)
    from fastapi import FastAPI

    if api_name == ManManConfig.EXPERIENCE_API:
        from manman.host.api.experience import router as experience_router
        from manman.host.api.shared import add_health_check

        app = FastAPI(title=api_config.title, root_path=api_config.root_path)
        app.include_router(experience_router)
        add_health_check(app)

    elif api_name == ManManConfig.STATUS_API:
        from manman.host.api.shared import add_health_check
        from manman.host.api.status import router as status_router

        app = FastAPI(title=api_config.title, root_path=api_config.root_path)
        app.include_router(status_router)
        add_health_check(app)

    elif api_name == ManManConfig.WORKER_DAL_API:
        from manman.host.api.shared import add_health_check
        from manman.host.api.worker_dal import server_router, worker_router

        app = FastAPI(
            title=api_config.title,
            root_path=api_config.root_path,
        )
        app.include_router(server_router)
        app.include_router(worker_router)
        add_health_check(app)

    else:
        # This should never happen due to validation above, but kept for safety
        raise typer.BadParameter(
            f"Unknown API name: {api_name}. "
            f"Valid options are: {', '.join(ManManConfig.KNOWN_API_NAMES)}"
        )

    # Generate and save the OpenAPI spec
    _generate_openapi_spec(app, api_name)
    logger.info(f"OpenAPI spec generation completed for {api_name}")


# TODO - should these not be ran by host?
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
