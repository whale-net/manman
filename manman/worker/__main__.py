import typer
import logging
import os
from typing import Optional
from typing_extensions import Annotated
from logging.config import fileConfig


from manman.worker.service import WorkerService
from manman.util import init_sql_alchemy_engine

app = typer.Typer()
fileConfig("logging.ini", disable_existing_loggers=False)
logger = logging.getLogger(__name__)


# TODO callback to share common boostrapping startup for easier test commands
@app.command()
def start(
    *,
    install_directory: str,
    rabbitmq_host: str,
    rabbitmq_port: int,
    rabbitmq_username: str,
    rabbitmq_password: str,
    steamcmd_override: Annotated[
        Optional[str], typer.Option(envvar="MANMAN_STEAMCMD_OVERRIDE"), None
    ] = None,
):
    install_directory = os.path.abspath(install_directory)
    logger.info(install_directory)
    service = WorkerService(
        install_directory,
        rabbitmq_host,
        rabbitmq_port,
        rabbitmq_username,
        rabbitmq_password,
    )
    # 5 = default cs config (for now)
    service.run()


@app.callback()
def callback(
    # TODO - worker will not connect to database in reality
    postgres_host: Annotated[str, typer.Option(envvar="MANMAN_POSTGRES_HOST")],
    postgres_port: Annotated[int, typer.Option(envvar="MANMAN_POSTGRES_PORT")],
    postgres_user: Annotated[str, typer.Option(envvar="MANMAN_POSTGRES_USER")],
    postgres_password: Annotated[str, typer.Option(envvar="MANMAN_POSTGRES_PASSWORD")],
):
    init_sql_alchemy_engine(
        postgres_host, postgres_port, postgres_user, postgres_password
    )


@app.command()
def localdev():
    #     logger.info("test123")
    #     install_directory = "/home/alex/manman/data/"
    #     cmd = SteamCMD(install_directory)
    #     cmd.install(730)
    pass


app()
