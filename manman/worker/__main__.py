import typer
import logging
import os
from typing_extensions import Annotated
from logging.config import fileConfig

from manman.worker.service import WorkerService

app = typer.Typer()
fileConfig("logging.ini", disable_existing_loggers=False)
logger = logging.getLogger(__name__)

# TODO - how does an env var work with this? what takes precedence?
# also lol just keeping logging on by default this was a trap (although interesting)
# @app.callback()
# def callback(enable_logging: bool = Annotated[str, typer.Option(True, '--logging')]):


# TODO callback to share common boostrapping startup for easier test commands
@app.command()
def start(
    install_directory: str,
    steamcmd_override: Annotated[
        str, typer.Argument(envvar="MANMAN_STEAMCMD_OVERRIDE"), None
    ] = None,
):
    install_directory = os.path.abspath(install_directory)
    logger.info(install_directory)
    service = WorkerService(install_directory)
    service.start_server(730, "cs2test")


@app.command()
def localdev():
    #     logger.info("test123")
    #     install_directory = "/home/alex/manman/data/"
    #     cmd = SteamCMD(install_directory)
    #     cmd.install(730)
    pass


app()
