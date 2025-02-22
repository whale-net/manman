import logging
import os
import ssl

import pika
import typer
from typing_extensions import Annotated

from manman.util import get_rabbitmq_connection, init_auth_api_client, init_rabbitmq
from manman.worker.service import WorkerService

app = typer.Typer()
# fileConfig("logging.ini", disable_existing_loggers=False)
logger = logging.getLogger(__name__)


# TODO callback to share common boostrapping startup for easier test commands
@app.command()
def start(
    sa_client_id: Annotated[str, typer.Option(envvar="MANMAN_WORKER_SA_CLIENT_ID")],
    sa_client_secret: Annotated[
        str, typer.Option(envvar="MANMAN_WORKER_SA_CLIENT_SECRET")
    ],
    host_url: Annotated[str, typer.Option(envvar="MANMAN_HOST_URL")],
    install_directory: Annotated[
        str, typer.Option(envvar="MANMAN_WORKER_INSTALL_DIRECTORY")
    ] = "./data",
    # steamcmd_override: Annotated[
    #     Optional[str], typer.Option(envvar="MANMAN_STEAMCMD_OVERRIDE"), None
    # ] = None,
):
    install_directory = os.path.abspath(install_directory)
    service = WorkerService(install_directory, host_url, sa_client_id, sa_client_secret)
    service.run()


@app.callback()
def callback(
    auth_url: Annotated[str, typer.Option(envvar="MANMAN_AUTH_URL")],
    rabbitmq_host: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_HOST")],
    rabbitmq_port: Annotated[int, typer.Option(envvar="MANMAN_RABBITMQ_PORT")],
    rabbitmq_username: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_USER")],
    rabbitmq_password: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_PASSWORD")],
):
    credentials = pika.credentials.PlainCredentials(
        username=rabbitmq_username, password=rabbitmq_password
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    # TODO - what does this really do?
    # server auth is used to create clients
    context.load_default_certs(purpose=ssl.Purpose.SERVER_AUTH)
    init_rabbitmq(
        pika.ConnectionParameters(
            host=rabbitmq_host,
            port=rabbitmq_port,
            credentials=credentials,
            # TODO - should we share or specify the SSL context somewhere?
            ssl_options=pika.SSLOptions(context),
        )
    )
    init_auth_api_client(auth_url)


@app.command()
def localdev_send_queue(key: int):
    connection = get_rabbitmq_connection()
    chan = connection.channel()
    chan.exchange_declare("server")
    # chan.basic_publish(exchange="server", routing_key=str(key), body="test123")
    from manman.models import Command, CommandType

    shutdown_command = Command(command_type=CommandType.STOP)
    chan.basic_publish(
        exchange="server", routing_key=str(key), body=shutdown_command.model_dump_json()
    )
    return


# @app.command()
# def localdev_auth(
#     auth_url: Annotated[str, typer.Option(envvar="MANMAN_AUTH_URL")],
#     sa_client_id: Annotated[str, typer.Option(envvar="MANMAN_WORKER_SA_CLIENT_ID")],
#     sa_client_secret: Annotated[
#         str, typer.Option(envvar="MANMAN_WORKER_SA_CLIENT_SECRET")
#     ],
# ):
#     from manman.api_client import AuthAPIClient

#     auth_client = AuthAPIClient(base_url=auth_url)
#     token_response = auth_client.get_access_token(sa_client_id, sa_client_secret)

#     is_valid_offline = auth_client.validate_token(
#         token_response.access_token, do_online_check=False
#     )
#     is_valid_online = auth_client.validate_token(
#         token_response.access_token, do_online_check=True
#     )
#     print(is_valid_offline, is_valid_online)
#     print(token_response.access_token.jwt)


# app()
