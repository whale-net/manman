import logging
import os
from typing import Optional

import sqlalchemy
import typer
import uvicorn
from typing_extensions import Annotated

import alembic
import alembic.command
import alembic.config
from manman.util import (
    get_rabbitmq_ssl_options,
    get_sqlalchemy_engine,
    init_rabbitmq,
    init_sql_alchemy_engine,
)

app = typer.Typer()
# fileConfig("logging.ini", disable_existing_loggers=False)
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
):
    """Start the experience API (host layer) that provides game server management and user-facing functionality."""
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

    experience_app = FastAPI(title="ManMan Experience API")
    experience_app.include_router(experience_router)

    uvicorn.run(experience_app, host="0.0.0.0", port=port)


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
):
    """Start the status API that provides status and monitoring functionality."""
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

    from manman.host.api.status import router as status_router

    status_app = FastAPI(title="ManMan Status API")
    status_app.include_router(status_router)

    uvicorn.run(status_app, host="0.0.0.0", port=port)


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
):
    """Start the worker DAL API that provides data access endpoints for worker services."""
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

    from manman.host.api.worker_dal import server_router, worker_router

    worker_dal_app = FastAPI(
        title="ManMan Worker DAL API",
        root_path="/workerdal",  # Configure root path for reverse proxy
    )
    worker_dal_app.include_router(server_router)
    worker_dal_app.include_router(worker_router)

    uvicorn.run(worker_dal_app, host="0.0.0.0", port=port)


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
