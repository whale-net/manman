import typer
from typing_extensions import Annotated

from manman.worker.steamcmd import SteamCMD

app = typer.Typer()

@app.command()
def start(
    install_directory: str,
    steamcmd_override: Annotated[str, typer.Argument(envvar='MANMAN_STEAMCMD_OVERRIDE'), None] = None,
):
    print(f"running")

@app.command()
def test():
    install_directory = '/home/alex/manman/data/'
    cmd = SteamCMD(install_directory, steamcmd_executable="/usr/games/steamcmd")
    cmd.install(730)
    
# just in case this ever gets imported
if __name__ == '__main__':
    app()