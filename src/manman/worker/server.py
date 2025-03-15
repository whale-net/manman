import logging
import os
from typing import Self

from manman.api_client import WorkerAPIClient

# import sqlalchemy
# from sqlalchemy.orm import Session
# from pydantic import BaseModel
from manman.models import (
    Command,
    CommandType,
    GameServerConfig,
    GameServerInstance,
    ServerType,
)
from manman.processbuilder import ProcessBuilder, ProcessBuilderStatus
from manman.repository.rabbit import RabbitMessageProvider
from manman.util import get_rabbitmq_connection
from manman.worker.steamcmd import SteamCMD

logger = logging.getLogger(__name__)


# TODO logging
class Server:
    RMQ_EXCHANGE = "server"

    def __init__(
        self,
        wapi: WorkerAPIClient,
        root_install_directory: str,
        config: GameServerConfig,
    ) -> None:
        # Extra status trackers to handle shutdown
        # and to provide expected state which may be useful for debugging later
        self.__is_started = False
        self.__is_stopped = False

        self._wapi = wapi
        self._config = config

        self._instance = self._wapi.game_server_instance_create(config)
        self._game_server = self._wapi.game_server(self._config.game_server_id)
        logger.info("starting instance %s", self._instance.model_dump_json())

        self._message_provider = RabbitMessageProvider(
            connection=get_rabbitmq_connection(),
            exchange=Server.RMQ_EXCHANGE,
            # queue_name=str(self._instance.game_server_instance_id),
        )

        self._root_install_directory = root_install_directory
        self._server_directory = os.path.join(
            self._root_install_directory,
            # game_server is unique on server_type_appid
            ServerType(self._game_server.server_type).name.lower(),
            str(self._game_server.app_id),
            # and then config is unique on game_server_id, name
            self._config.name,
        )

        executable_path = os.path.join(self._server_directory, self._config.executable)
        pb = ProcessBuilder(executable=executable_path)
        for arg in self._config.args:
            pb.add_parameter(arg)
        self._proc = pb

    @property
    def instance(self) -> GameServerInstance:
        return self._instance

    # def add_stdin(self, input: str):
    #     # TODO check if pb is running
    #     self._pb.stdin_queue.put(input)

    # def stop(self):
    #     status = self._pb.status
    #     if status not in (ProcessBuilderStatus.INIT, ProcessBuilderStatus.RUNNING):
    #         logger.info("invalid stop received, current_status = %s", status)
    #         return

    @property
    def is_shutdown(self) -> bool:
        return self._instance.end_date is not None

    def shutdown(self):
        # TODO kill
        if not self.is_shutdown:
            logger.info(
                "shutting down instance %s", self._instance.game_server_instance_id
            )
            self._proc.stop()
            self._instance = self._wapi.game_server_instance_shutdown(self._instance)
            self._message_provider.shutdown()
            logger.info(
                "shutdown complete for instance %s",
                self._instance.game_server_instance_id,
            )

    def execute_command(self, command: Command) -> None:
        if command.command_type == CommandType.STOP:
            if self.__is_started:
                logger.info(
                    "killing server instance %s", self._instance.game_server_instance_id
                )
                # main run loop will handle shutdown gracefully, just set this
                self.__is_stopped = True
            else:
                logger.warning(
                    "server stopped before it was started, ignoring shutdown command"
                )
        elif command.command_type == CommandType.START:
            # do nothing, started through service
            logger.info(
                "received unnecessary start command for instance %s, ignoring",
                self._instance.game_server_instance_id,
            )
            pass
        elif command.command_type == CommandType.STDIN:
            # TODO - send to process builder
            pass
        else:
            logger.warning("unknown command type %s", command.command_type)

    def run(self, should_update: bool = True) -> Self:
        if self.__is_started:
            logger.error(
                "duplicate start command received, current_status = %s",
                self._proc.status,
            )
            raise RuntimeError("server already started, cannot start again")
        self.__is_started = True
        logger.info("instance %s starting", self._instance.game_server_instance_id)

        if should_update:
            steam = SteamCMD(self._server_directory)
            steam.install(app_id=self._game_server.app_id)

        try:
            # TODO - temp workaround for env var, need to come from config
            self._proc.execute(
                extra_env={"LD_LIBRARY_PATH": "./linux64:$LD_LIBRARY_PATH"}
            )
            # self._pb.execute()
        except Exception as e:
            logger.exception(e)
            self.shutdown()
            raise

        status = self._proc.status
        while status != ProcessBuilderStatus.STOPPED and self.__is_started:
            # TODO - make this available through property or something
            self._proc.read_output()
            commands = self._message_provider.get_commands()
            if len(commands) > 0:
                logger.info("commands received: %s", commands)
                for command in commands:
                    self.execute_command(command)

            status = self._proc.status

        # do it one more time to clean up anything leftover
        self._proc.read_output()
        logger.info(
            "instance %s has exited normally", self._instance.game_server_instance_id
        )
        self.shutdown()

        return self
