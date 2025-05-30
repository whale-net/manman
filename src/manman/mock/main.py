"""Main entry points for mock worker and server services."""
import logging
import os

import typer
from typing_extensions import Annotated, Optional

from manman.logging_config import setup_logging
from manman.util import get_rabbitmq_connection, get_rabbitmq_ssl_options, init_rabbitmq
from manman.mock.worker_service import MockWorkerService

app = typer.Typer()
logger = logging.getLogger(__name__)


@app.command()
def start_mock_worker(
    host_url: Annotated[str, typer.Option(envvar="MANMAN_HOST_URL")],
    install_directory: Annotated[
        str, typer.Option(envvar="MANMAN_WORKER_INSTALL_DIRECTORY")
    ] = "./data",
):
    """Start a mock worker service that simulates worker behavior without real work."""
    install_directory = os.path.abspath(install_directory)
    # Create directory if it doesn't exist for mock purposes
    os.makedirs(install_directory, exist_ok=True)
    
    service = MockWorkerService(
        install_directory,
        host_url,
        None,
        None,
        rabbitmq_connection=get_rabbitmq_connection(),
    )
    service.run()


@app.command() 
def start_mock_server(
    host_url: Annotated[str, typer.Option(envvar="MANMAN_HOST_URL")],
    game_server_config_id: Annotated[int, typer.Option(help="Game server config ID to mock")],
    worker_id: Annotated[int, typer.Option(help="Worker ID to associate with this mock server")] = 1,
    install_directory: Annotated[
        str, typer.Option(envvar="MANMAN_WORKER_INSTALL_DIRECTORY")
    ] = "./data",
):
    """Start a mock server that simulates server behavior without real processes."""
    from manman.mock.server import MockServer
    from manman.repository.api_client import WorkerAPIClient
    from manman.util import get_auth_api_client
    
    install_directory = os.path.abspath(install_directory)
    os.makedirs(install_directory, exist_ok=True)
    
    # Create API client to get configuration
    wapi = WorkerAPIClient(
        host_url,
        auth_api_client=get_auth_api_client(),
        sa_client_id=None,
        sa_client_secret=None,
    )
    
    config = wapi.game_server_config(game_server_config_id)
    
    # Create and run mock server
    server = MockServer(
        wapi=wapi,
        rabbitmq_connection=get_rabbitmq_connection(),
        root_install_directory=install_directory,
        config=config,
        worker_id=worker_id,
    )
    
    logger.info("Starting standalone mock server for config %s", game_server_config_id)
    server.run(should_update=False)


@app.callback()
def callback(
    rabbitmq_host: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_HOST")],
    rabbitmq_port: Annotated[int, typer.Option(envvar="MANMAN_RABBITMQ_PORT")],
    rabbitmq_username: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_USER")],
    rabbitmq_password: Annotated[str, typer.Option(envvar="MANMAN_RABBITMQ_PASSWORD")],
    app_env: Annotated[Optional[str], typer.Option(envvar="APP_ENV")] = None,
    enable_ssl: Annotated[
        bool, typer.Option(envvar="MANMAN_RABBITMQ_ENABLE_SSL")
    ] = False,
    rabbitmq_ssl_hostname: Annotated[
        str, typer.Option(envvar="MANMAN_RABBITMQ_SSL_HOSTNAME")
    ] = None,
):
    """Initialize mock services with common configuration."""
    # Setup logging first
    setup_logging(service_name="mock")

    virtual_host = f"manman-{app_env}" if app_env else "/"

    # Initialize with AMQPStorm connection parameters
    init_rabbitmq(
        host=rabbitmq_host,
        port=rabbitmq_port,
        username=rabbitmq_username,
        password=rabbitmq_password,
        virtual_host=virtual_host,
        ssl_enabled=enable_ssl,
        ssl_options=get_rabbitmq_ssl_options(rabbitmq_ssl_hostname)
        if enable_ssl
        else None,
    )