import typer
import logging
from typing_extensions import Annotated
from logging.config import fileConfig

from manman.worker.steamcmd import SteamCMD

app = typer.Typer()
fileConfig("logging.ini", disable_existing_loggers=False)
logger = logging.getLogger(__name__)

# TODO - how does an env var work with this? what takes precedence?
# also lol just keeping logging on by default this was a trap (although interesting)
# @app.callback()
# def callback(enable_logging: bool = Annotated[str, typer.Option(True, '--logging')]):
    

@app.command()
def start(
    install_directory: str,
    steamcmd_override: Annotated[str, typer.Argument(envvar='MANMAN_STEAMCMD_OVERRIDE'), None] = None,
):
    print(f"running")

@app.command()
def test():
    logger.info('test123')
    install_directory = '/home/alex/manman/data/'
    cmd = SteamCMD(install_directory)
    cmd.install(730)
    
app()
