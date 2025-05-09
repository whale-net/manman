from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (  # using postgres.ARRAY I guess; MetaData,; ForeignKey,
    ARRAY,
    Column,
    Index,
    String,
)

# , UniqueConstraint
from sqlalchemy.sql.functions import current_timestamp

# from sqlalchemy.dialects import postgresql
from sqlmodel import Field, MetaData, SQLModel

# SQLModel.metadata = MetaData(schema="manman")


class ServerType(Enum):
    STEAM = 1


class Base(SQLModel):
    metadata = MetaData(schema="manman")
    # type_annotation_map = {
    #     dict[str, Any]: JSON,
    #     list[str]: ARRAY(String),
    # }


class Worker(Base, table=True):
    __tablename__ = "workers"
    worker_id: int = Field(primary_key=True)
    # ip_addr: Mapped[str] = mapped_column(String(15))
    created_date: datetime = Field(default=current_timestamp())
    end_date: Optional[datetime] = Field(nullable=True)

    last_heartbeat: Optional[datetime] = Field(nullable=True)
    # TODO FIGURE THIS OUT
    # game_server_instances: Mapped["GameServerInstance"] = relationship(


# do I need server table? -> yes, but make worker manage state
# make health check contain server info for trueups
class GameServerInstance(Base, table=True):
    __tablename__ = "game_server_instances"
    game_server_instance_id: int = Field(primary_key=True)
    game_server_config_id: int = Field(
        foreign_key="game_server_configs.game_server_config_id", index=True
    )
    created_date: datetime = Field(default=current_timestamp(), exclude=True)
    end_date: Optional[datetime] = Field(nullable=True)

    # should not be nullable, but for now it is
    worker_id: int = Field(foreign_key="workers.worker_id", index=True, nullable=True)
    # todo investigate this
    # worker: Mapped["Worker"] = relationship(back_populates="game_server_instances")

    def get_thread_name(self, extra: Optional[str] = None) -> str:
        extra_str = "-" + extra if extra is not None else ""
        return f"server[{self.game_server_instance_id}{extra_str}]"


class GameServer(Base, table=True):
    __tablename__ = "game_servers"
    game_server_id: int = Field(primary_key=True)
    name: str = Field()
    server_type: ServerType = Field()
    # for now only steam, everything is app_id
    # in the future, not sure what will be supported, so for now going to ignore it
    app_id: int = Field()

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


class GameServerConfig(Base, table=True):
    __tablename__ = "game_server_configs"
    game_server_config_id: int = Field(primary_key=True)
    game_server_id: int = Field(foreign_key="game_servers.game_server_id", index=True)
    is_default: bool = Field(default=False)

    name: str = Field()
    executable: str = Field()
    args: list[str] = Field(sa_column=Column(ARRAY(String()), nullable=False))
    env_var: list[str] = Field(sa_column=Column(ARRAY(String()), nullable=False))

    __table_args__ = (
        Index(
            "ixuf_game_server_configs_default_config",
            "game_server_id",
            "is_default",
            unique=True,
            postgresql_where=("is_default"),
        ),
        Index(
            "ixu_game_server_configs_game_server_id_name",
            "game_server_id",
            "name",
            unique=True,
        ),
    )


### NON TABLES # unsure if this is good idea


class CommandType(Enum):
    START = "START"
    STDIN = "STDIN"
    STOP = "STOP"


# {"command_type":"START", "command_args": ["1"]}
# {"command_type":"START", "command_args": ["3"]}
# {"command_type":"START", "command_args": []}
# {"command_type":"STOP", "command_args": []}
# TODO subclass for each comamnd type + parent class factory based on enum
class Command(Base):
    command_type: CommandType = Field()
    command_args: list[str] = Field(default=[])
