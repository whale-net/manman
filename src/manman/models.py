import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (  # using postgres.ARRAY I guess; MetaData,; ForeignKey,
    ARRAY,
    CheckConstraint,  # Add CheckConstraint
    Column,
    Index,
    String,
)

# , UniqueConstraint
from sqlalchemy.sql.functions import current_timestamp

# from sqlalchemy.dialects import postgresql
from sqlmodel import Field, MetaData, Relationship, SQLModel

# SQLModel.metadata = MetaData(schema="manman")


class ServerType(Enum):
    STEAM = 1


class ManManBase(SQLModel):
    metadata = MetaData(schema="manman")
    # type_annotation_map = {
    #     dict[str, Any]: JSON,
    #     list[str]: ARRAY(String),
    # }


class Worker(ManManBase, table=True):
    __tablename__ = "workers"
    worker_id: int = Field(primary_key=True)
    # ip_addr: Mapped[str] = mapped_column(String(15))
    created_date: datetime.datetime = Field(default=current_timestamp())
    end_date: Optional[datetime.datetime] = Field(nullable=True)

    last_heartbeat: Optional[datetime.datetime] = Field(nullable=True)
    # TODO FIGURE THIS OUT
    # game_server_instances: Mapped["GameServerInstance"] = relationship(

    game_server_instances: list["GameServerInstance"] = Relationship(
        back_populates="worker"
        # TODO - lazy? make everything lazy? probably yes, in most situations I'd think
    )


# do I need server table? -> yes, but make worker manage state
# make health check contain server info for trueups
class GameServerInstance(ManManBase, table=True):
    __tablename__ = "game_server_instances"
    game_server_instance_id: int = Field(primary_key=True)

    game_server_config_id: int = Field(
        foreign_key="game_server_configs.game_server_config_id", index=True
    )

    game_server_config: "GameServerConfig" = Relationship()

    created_date: datetime.datetime = Field(default=current_timestamp(), exclude=True)
    end_date: Optional[datetime.datetime] = Field(nullable=True)

    # should not be nullable, but for now it is
    worker_id: int = Field(foreign_key="workers.worker_id", index=True, nullable=True)
    worker: Optional[Worker] = Relationship(back_populates="game_server_instances")

    # todo investigate this
    # worker: Mapped["Worker"] = relationship(back_populates="game_server_instances")

    def get_thread_name(self, extra: Optional[str] = None) -> str:
        extra_str = "-" + extra if extra is not None else ""
        return f"server[{self.game_server_instance_id}{extra_str}]"


class GameServer(ManManBase, table=True):
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


class GameServerConfig(ManManBase, table=True):
    __tablename__ = "game_server_configs"
    game_server_config_id: int = Field(primary_key=True)
    game_server_id: int = Field(foreign_key="game_servers.game_server_id", index=True)
    is_default: bool = Field(default=False)
    is_visible: bool = Field(default=True)

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
class Command(ManManBase):
    command_type: CommandType = Field()
    command_args: list[str] = Field(default=[])


# See https://github.com/whale-net/friendly-computing-machine/blob/main/docs/manman_subscribe.md
class StatusType(Enum):
    CREATED = "CREATED"
    # Optional, can go from CREATED -> RUNNING
    INITIALIZING = "INITIALIZING"
    RUNNING = "RUNNING"
    LOST = "LOST"
    COMPLETE = "COMPLETE"
    CRASHED = "CRASHED"


ACTIVE_STATUS_TYPES = {
    StatusType.CREATED,
    StatusType.INITIALIZING,
    StatusType.RUNNING,
}


class StatusInfoBase(ManManBase):
    class_name: str = Field()
    status_type: StatusType = Field()
    as_of: datetime.datetime = Field(default=current_timestamp())

    @classmethod
    def create(
        cls,
        class_name: str,
        status_type: StatusType,
    ) -> "StatusInfoBase":
        as_of = datetime.datetime.now(datetime.timezone.utc)
        return cls(class_name=class_name, status_type=status_type, as_of=as_of)


### BACK TO TABLES


class StatusInfo(StatusInfoBase, table=True):
    __tablename__ = "status_info"
    status_info_id: int = Field(primary_key=True)

    worker_id: Optional[int] = Field(  # Made Optional
        default=None, foreign_key="workers.worker_id", index=True
    )
    worker: Optional[Worker] = Relationship()  # Made Optional

    game_server_instance_id: Optional[int] = Field(  # Made Optional
        default=None,
        foreign_key="game_server_instances.game_server_instance_id",
        index=True,
    )
    game_server_instance: Optional[GameServerInstance] = Relationship()  # Made Optional

    __table_args__ = (
        CheckConstraint(
            "(worker_id IS NULL AND game_server_instance_id IS NOT NULL) OR "
            "(worker_id IS NOT NULL AND game_server_instance_id IS NULL)",
            name="chk_status_info_target_not_null",
        ),
        Index(
            "ix_status_info_as_of_game_server_instance_worker",
            "as_of",
            "game_server_instance_id",
            "worker_id",
        ),
        # Preserve existing indexes if any, or add them here if needed
        # e.g., Index("ix_status_info_worker_id", "worker_id"),
        # Index("ix_status_info_game_server_instance_id", "game_server_instance_id"),
    )
