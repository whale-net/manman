from datetime import datetime
from typing import Any

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import (
    String,
    MetaData,
    ForeignKey,
    JSON,
    Index,
    ARRAY,
)  # , UniqueConstraint

from manman.worker.server import ServerType


class Base(DeclarativeBase):
    metadata: MetaData = MetaData(schema="manman")
    type_annotation_map = {
        dict[str, Any]: JSON,
        list[str]: ARRAY(String),
    }


class Worker(
    Base,
):
    __tablename__ = "workers"
    worker_id: Mapped[int] = mapped_column(primary_key=True)
    # ip_addr: Mapped[str] = mapped_column(String(15))
    created_date: Mapped[datetime]
    end_date: Mapped[datetime]


# do I need server table? -> yes, but make worker manage state
# make health check contain server info for trueups
class GameServerInstance(Base):
    __tablename__ = "servers"
    game_sever_instance_id: Mapped[int] = mapped_column(primary_key=True)
    game_server_id: Mapped[int] = mapped_column(
        ForeignKey("game_servers.game_server_id"), index=True
    )
    # TODO - is there some type of constraint I could use to avoid the name
    name: Mapped[str]
    created_date: Mapped[datetime]
    end_date: Mapped[datetime]


class GameServer(Base):
    __tablename__ = "game_servers"
    game_server_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    server_type: Mapped[ServerType]
    # for now only steam, everything is app_id
    # in the future, not sure what will be supported, so for now going to ignore it
    app_id: Mapped[int]

    __table_args__ = (
        # this should really be on app_id
        Index(
            "ixu_game_server_name_server_type",
            "name",
            "server_type",
            unique=True,
        ),
        Index(
            "ixu_game_server_app_id_server_type",
            "app_id",
            "server_type",
            unique=True,
        ),
    )


class GameServerConfig(Base):
    __tablename__ = "game_server_configs"
    game_server_config_id: Mapped[int] = mapped_column(primary_key=True)
    game_server_id: Mapped[int] = mapped_column(
        ForeignKey("game_servers.game_server_id"), index=True
    )
    is_default: Mapped[bool] = mapped_column(default=False)

    executable: Mapped[str]
    args: Mapped[list[str]]

    __table_args__ = (
        Index(
            "ixuf_game_server_configs_default_config",
            "game_server_id",
            is_default,
            unique=True,
            postgresql_where=(is_default.column),
        ),
    )
