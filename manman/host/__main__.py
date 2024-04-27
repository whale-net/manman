import typer
import logging
from typing_extensions import Annotated
from logging.config import fileConfig

from manman.util import get_sqlalchemy_connection

app = typer.Typer()
fileConfig("logging.ini", disable_existing_loggers=False)
logger = logging.getLogger(__name__)


# TODO callback to share common boostrapping startup for easier test commands
@app.command()
def start(
    postgres_host: Annotated[str, typer.Option(envvar="MANMAN_POSTGRES_HOST")],
    postgres_port: Annotated[int, typer.Option(envvar="MANMAN_POSTGRES_PORT")],
    postgres_user: Annotated[str, typer.Option(envvar="MANMAN_POSTGRES_USER")],
    postgres_password: Annotated[str, typer.Option(envvar="MANMAN_POSTGRES_PASSWORD")],
):
    salch = get_sqlalchemy_connection(
        postgres_host, postgres_port, postgres_user, postgres_password
    )
    print(salch)


@app.command()
def localdev():
    pass


app()
