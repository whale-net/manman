import logging
import os
import ssl

import amqpstorm
import typer
from typing_extensions import Annotated, Optional

from manman.util import get_rabbitmq_connection, init_rabbitmq
from manman.worker.service import WorkerService

app = typer.Typer()
logger = logging.getLogger(__name__)


@app.command()
def start(
    # sa_client_id: Annotated[str, typer.Option(envvar="MANMAN_WORKER_SA_CLIENT_ID")],
    # sa_client_secret: Annotated[
    #     str, typer.Option(envvar="MANMAN_WORKER_SA_CLIENT_SECRET")
    # ],
    host_url: Annotated[str, typer.Option(envvar="MANMAN_HOST_URL")],
    install_directory: Annotated[
        str, typer.Option(envvar="MANMAN_WORKER_INSTALL_DIRECTORY")
    ] = "./data",
    # steamcmd_override: Annotated[
    #     Optional[str], typer.Option(envvar="MANMAN_STEAMCMD_OVERRIDE"), None
    # ] = None,
):
    install_directory = os.path.abspath(install_directory)
    # todo - re-add authcz
    service = WorkerService(
        install_directory,
        host_url,
        None,
        None,
        rabbitmq_connection=get_rabbitmq_connection(),
    )
    service.run()


@app.callback()
def callback(
    # auth_url: Annotated[str, typer.Option(envvar="MANMAN_AUTH_URL")],
    rabbitmq_host: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_HOST")],
    rabbitmq_port: Annotated[int, typer.Option(envvar="MANMAN_RABBITMQ_PORT")],
    rabbitmq_username: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_USER")],
    rabbitmq_password: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_PASSWORD")],
    app_env: Annotated[Optional[str], typer.Option(envvar="APP_ENV")] = None,
):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_default_certs(purpose=ssl.Purpose.SERVER_AUTH)
    virtual_host = f"manman-{app_env}" if app_env else "/"

    # Initialize with AMQPStorm connection parameters
    init_rabbitmq(
        host=rabbitmq_host,
        port=rabbitmq_port,
        username=rabbitmq_username,
        password=rabbitmq_password,
        virtual_host=virtual_host,
        # ssl_enabled=True,  # Enable SSL based on original intent
        ssl_enabled=False,  # Disable SSL for local development
        ssl_context=context,
    )

    # init basic logging config
    logging.basicConfig(level=logging.INFO)


@app.command()
def localdev_send_queue(key: int):
    connection = get_rabbitmq_connection()
    chan = connection.channel()
    chan.exchange.declare(exchange="server", exchange_type="direct")

    from manman.models import Command, CommandType

    shutdown_command = Command(command_type=CommandType.STOP)
    message = amqpstorm.Message.create(
        chan,
        body=shutdown_command.model_dump_json(),
        properties={"content_type": "application/json"},
    )
    message.publish(exchange="server", routing_key=str(key))
    return
