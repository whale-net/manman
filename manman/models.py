from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime, Enum

from manman.worker.server import ServerType as ServerTypeEnum


class Base(DeclarativeBase):
    pass


class Worker(Base):
    __tablename__ = "workers"
    id: Mapped[int] = mapped_column(primary_key=True)
    ip: str = mapped_column(String(15))
    created_date: DateTime
    end_date: DateTime


# do I need server table? -> yes, but make worker manage state
# make health check contain server info for trueups
class Server(Base):
    __tablename__ = "servers"
    id: Mapped[int] = mapped_column(primary_key=True)


class ServerType(Base):
    __tablename__ = "server_types"
    id = Enum(ServerTypeEnum)
