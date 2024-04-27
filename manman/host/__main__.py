import alembic.command
import typer
import logging
import os
import alembic
import alembic.config
import pathlib
from typing_extensions import Annotated
from logging.config import fileConfig
from typing import Optional

import sqlalchemy

from manman.util import get_sqlalchemy_engine

app = typer.Typer()
fileConfig("logging.ini", disable_existing_loggers=False)
logger = logging.getLogger(__name__)

# probably a better way to do this but \(o.0)/
__global_state = {
    "sqlalchemy_engine": None,
}


# TODO callback to share common boostrapping startup for easier test commands
@app.command()
def start(run_migration_check: Optional[bool] = True):
    engine = __global_state["sqlalchemy_engine"]

    if run_migration_check and _need_migration(engine):
        raise RuntimeError("migration needs to be ran before starting")


@app.command()
def run_migration():
    engine = __global_state["sqlalchemy_engine"]
    _run_migration(engine)


@app.command()
def create_migration(migration_message: Optional[str] = None):
    if os.environ.get("ENVIRONMENT", "DEV") == "PROD":
        raise RuntimeError("cannot create revisions in production")
    engine = __global_state["sqlalchemy_engine"]
    _create_migration(engine, message=migration_message)


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
    __global_state["sqlalchemy_engine"] = get_sqlalchemy_engine(
        postgres_host, postgres_port, postgres_user, postgres_password
    )


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
