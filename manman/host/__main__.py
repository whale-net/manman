import logging
import os
import pathlib
from logging.config import fileConfig
from typing import Optional

import sqlalchemy
import typer
import uvicorn
from typing_extensions import Annotated

import alembic
import alembic.command
import alembic.config
from manman.host.api import fastapp
from manman.util import (
    get_sqlalchemy_engine,
    init_auth_api_client,
    init_sql_alchemy_engine,
)

app = typer.Typer()
fileConfig("logging.ini", disable_existing_loggers=False)
logger = logging.getLogger(__name__)


@app.command()
def start(
    auth_url: Annotated[str, typer.Option(envvar="MANMAN_AUTH_URL")],
    port: int = 8000,
    # workers: int = 1,
    # auto_reload: bool = False,
    run_migration_check: Optional[bool] = True,
):
    # TODO - get connection properly
    if run_migration_check and _need_migration(get_sqlalchemy_engine("", 0, "", "")):
        raise RuntimeError("migration needs to be ran before starting")

    init_auth_api_client(auth_url)

    # TODO running via string doesn't initialize engine because separate process
    # this would be a nice development enhancement, but may not matter if we scale out. TBD
    # gunicorn + uvicorn worker is preferred if need to scale local api instance
    # uvicorn.run("manman.host.api:fastapp", port=port, workers=workers, reload=auto_reload)
    uvicorn.run(fastapp, port=port)


# TODO - should these not be ran by host?
@app.command()
def run_migration():
    # TODO - get connection properly
    _run_migration(get_sqlalchemy_engine("", 0, "", ""))


@app.command()
def create_migration(migration_message: Optional[str] = None):
    if os.environ.get("ENVIRONMENT", "DEV") == "PROD":
        raise RuntimeError("cannot create revisions in production")
    # TODO - get connection properly
    _create_migration(get_sqlalchemy_engine("", 0, "", ""), message=migration_message)


@app.callback()
def callback(
    # TODO - envar global for alembic import
    postgres_host: Annotated[str, typer.Option(envvar="MANMAN_POSTGRES_HOST")],
    postgres_port: Annotated[int, typer.Option(envvar="MANMAN_POSTGRES_PORT")],
    postgres_user: Annotated[str, typer.Option(envvar="MANMAN_POSTGRES_USER")],
    postgres_password: Annotated[str, typer.Option(envvar="MANMAN_POSTGRES_PASSWORD")],
):
    # __global_state["postgres_host"] = postgres_host
    # __global_state["postgres_port"] = postgres_port
    # __global_state["postgres_user"] = postgres_user
    # __global_state["postgres_password"] = postgres_password
    init_sql_alchemy_engine(
        postgres_host, postgres_port, postgres_user, postgres_password
    )
    # __global_state["sqlalchemy_engine"] = engine
    # sessionmaker(bind=engine)


# alembic helpers
# TODO context manager to reduce duplication
def _get_alembic_config() -> alembic.config.Config:
    current_path = pathlib.Path(__file__).parent.resolve()
    alembic_path = os.path.join(current_path, "../../", "alembic.ini")
    config = alembic.config.Config(alembic_path)
    return config


def _need_migration(engine: sqlalchemy.Engine) -> bool:
    config = _get_alembic_config()
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
    with engine.begin() as conn:
        # TODO remove connection from env and use this?
        config.attributes["connection"] = conn
        alembic.command.upgrade(config, "head")


def _create_migration(engine: sqlalchemy.Engine, message: Optional[str] = None):
    if not _need_migration(engine):
        raise RuntimeError("no migration creation required")

    config = _get_alembic_config()
    with engine.begin() as conn:
        config.attributes["connection"] = conn
        alembic.command.revision(config, message=message, autogenerate=True)


if __name__ == "__main__":
    app()
