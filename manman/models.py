from datetime import datetime

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, MetaData, UniqueConstraint

from manman.worker.server import ServerTypeEnum as ServerTypeEnum


class Base(DeclarativeBase):
    metadata: MetaData = MetaData(schema="manman")
    pass


class Worker(
    Base,
):
    __tablename__ = "workers"
    id: Mapped[int] = mapped_column(primary_key=True)
    ip: Mapped[str] = mapped_column(String(15))
    created_date: Mapped[datetime]
    end_date: Mapped[datetime]


# do I need server table? -> yes, but make worker manage state
# make health check contain server info for trueups
class Server(Base):
    __tablename__ = "servers"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_date: Mapped[datetime]
    end_date: Mapped[datetime]


class ServerType(Base):
    __tablename__ = "server_types"
    __table_args__ = (UniqueConstraint("server_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    server_type: Mapped[ServerTypeEnum]
