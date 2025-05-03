from manman.models import Base


class StdinCommandRequest(Base):
    """
    Request to send to the worker to start a game server instance.
    """

    commands: list[str]
