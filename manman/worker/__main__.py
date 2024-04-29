import typer
import logging
import os
from typing_extensions import Annotated
from logging.config import fileConfig
import pika

from manman.worker.service import WorkerService
from manman.util import init_rabbitmq, get_rabbitmq_connection

app = typer.Typer()
fileConfig("logging.ini", disable_existing_loggers=False)
logger = logging.getLogger(__name__)


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
    service = WorkerService(install_directory)
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
    init_rabbitmq(
        pika.ConnectionParameters(
            host=rabbitmq_host, port=rabbitmq_port, credentials=credentials
        )
    )


@app.command()
def localdev(key: int):
    connection = get_rabbitmq_connection()
    chan = connection.channel()
    chan.exchange_declare("server")
    chan.basic_publish(exchange="server", routing_key=str(key), body="test123")
    return


app()
