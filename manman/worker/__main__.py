import typer
import logging
import os
from typing_extensions import Annotated
from logging.config import fileConfig
import pika

from manman.worker.service import WorkerService

app = typer.Typer()
fileConfig("logging.ini", disable_existing_loggers=False)
logger = logging.getLogger(__name__)

__GLOBAL = {}


# TODO callback to share common boostrapping startup for easier test commands
@app.command()
def start(
    install_directory: Annotated[
        str, typer.Option(envvar="MANMAN_WORKER_INSTALL_DIRECTORY")
    ] = "./data",
    # steamcmd_override: Annotated[
    #     Optional[str], typer.Option(envvar="MANMAN_STEAMCMD_OVERRIDE"), None
    # ] = None,
):
    install_directory = os.path.abspath(install_directory)
    service = WorkerService(
        install_directory,
        __GLOBAL["rmq_parms"],
    )
    service.run()


@app.callback()
def callback(
    # TODO - worker will not connect to database in reality
    rabbitmq_host: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_HOST")],
    rabbitmq_port: Annotated[int, typer.Option(envvar="MANMAN_RABBITMQ_PORT")],
    rabbitmq_username: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_USER")],
    rabbitmq_password: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_PASSWORD")],
):
    credentials = pika.credentials.PlainCredentials(
        username=rabbitmq_username, password=rabbitmq_password
    )
    __GLOBAL["rmq_parms"] = pika.ConnectionParameters(
        host=rabbitmq_host, port=rabbitmq_port, credentials=credentials
    )


@app.command()
def localdev():
    #     logger.info("test123")
    #     install_directory = "/home/alex/manman/data/"
    #     cmd = SteamCMD(install_directory)
    #     cmd.install(730)
    return


app()
