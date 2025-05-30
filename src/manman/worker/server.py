import logging
import os
from typing import Self

from amqpstorm import Connection

# import sqlalchemy
# from sqlalchemy.orm import Session
# from pydantic import BaseModel
from manman.models import (
    Command,
    CommandType,
    GameServerConfig,
    GameServerInstance,
    ServerType,
    StatusInfo,
    StatusType,
)
from manman.repository.api_client import WorkerAPIClient
from manman.repository.rabbitmq import RabbitCommandSubscriber, RabbitStatusPublisher
from manman.repository.rabbitmq.util import add_routing_key_prefix
from manman.util import env_list_to_dict
from manman.worker.processbuilder import ProcessBuilder, ProcessBuilderStatus
from manman.worker.steamcmd import SteamCMD

logger = logging.getLogger(__name__)


# TODO logging
class Server:
    RMQ_EXCHANGE = "server"

    def __init__(
        self,
        wapi: WorkerAPIClient,
        rabbitmq_connection: Connection,
        root_install_directory: str,
        config: GameServerConfig,
        worker_id: int,
    ) -> None:
        # Extra status trackers to handle shutdown
        # and to provide expected state which may be useful for debugging later
        self.__is_started = False
        self.__is_stopped = False

        self._wapi = wapi
        self._config = config
        self._worker_id = worker_id

        self._instance = self._wapi.game_server_instance_create(config, self._worker_id)
        self._game_server = self._wapi.game_server(self._config.game_server_id)
        logger.info("starting instance %s", self._instance.model_dump_json())

        self._command_message_provider = RabbitCommandSubscriber(
            connection=rabbitmq_connection,
            exchange=Server.RMQ_EXCHANGE,
            queue_name=self.command_routing_key,
        )

        self._status_publisher = RabbitStatusPublisher(
            connection=rabbitmq_connection,
            exchange=Server.RMQ_EXCHANGE,
            routing_key_base=self.status_routing_key,
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

        # Publish CREATED status
        self._status_publisher.publish(
            status=StatusInfo.create(
                self.__class__.__name__,
                StatusType.CREATED,
                game_server_instance_id=self._instance.game_server_instance_id,
            ),
        )

    @property
    def instance(self) -> GameServerInstance:
        return self._instance

    @staticmethod
    def _generate_common_queue_prefix(game_server_instance_id: int) -> str:
        return f"game-server-instance.{game_server_instance_id}"

    @staticmethod
    def generate_command_queue_name(game_server_instance_id: int):
        return add_routing_key_prefix(
            Server._generate_common_queue_prefix(game_server_instance_id),
            "cmd",
        )

    @staticmethod
    def generate_status_queue_name(game_server_instance_id: int):
        return add_routing_key_prefix(
            Server._generate_common_queue_prefix(game_server_instance_id), "status"
        )

    @property
    def command_routing_key(self) -> str:
        return self.generate_command_queue_name(self._instance.game_server_instance_id)

    @property
    def status_routing_key(self) -> str:
        return self.generate_status_queue_name(self._instance.game_server_instance_id)

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

    def __handle_stop_command(self) -> None:
        if not self.__is_started:
            logger.error(
                "stop command received before start command, current_status = %s",
                self._proc.status,
            )
            raise RuntimeError("server not started, cannot stop")
        if self.__is_stopped:
            logger.error(
                "stop command received after stop command, current_status = %s",
                self._proc.status,
            )
            raise RuntimeError("server already stopped, cannot stop again")
        logger.info(
            "stop command received for instance %s",
            self._instance.game_server_instance_id,
        )
        self.__is_stopped = True

    def __handle_stdin_command(self, command: Command) -> None:
        if len(command.command_args) < 2:
            logger.warning(
                "too few args, need config ID and commands %s",
                command.command_args,
            )
            return

        # for now going to merge them all together blindly
        stdin_command = " ".join(command.command_args[1:])
        logger.info(
            "stdin command received for instance %s: %s",
            self._instance.game_server_instance_id,
            stdin_command,
        )
        self._proc.write_stdin(stdin_command)

    def _shutdown(self):
        # TODO kill
        if not self.is_shutdown:
            if not self.__is_stopped:
                logger.warning("shutdown called before stop command")
            logger.info(
                "shutting down instance %s", self._instance.game_server_instance_id
            )

            # Capture instance ID before shutdown for status publishing
            instance_id = self._instance.game_server_instance_id

            self._proc.stop()
            self._instance = self._wapi.game_server_instance_shutdown(self._instance)
            self._command_message_provider.shutdown()

            # Publish COMPLETE status
            self._status_publisher.publish(
                status=StatusInfo.create(
                    self.__class__.__name__,
                    StatusType.COMPLETE,
                    game_server_instance_id=instance_id,
                ),
            )
            self._status_publisher.shutdown()

            logger.info(
                "shutdown complete for instance %s",
                instance_id,
            )

    def execute_command(self, command: Command) -> None:
        if command.command_type == CommandType.STOP:
            self.__handle_stop_command()
        elif command.command_type == CommandType.START:
            # do nothing, started through service
            logger.info(
                "received unnecessary start command for instance %s, ignoring",
                self._instance.game_server_instance_id,
            )
            pass
        elif command.command_type == CommandType.STDIN:
            self.__handle_stdin_command(command)
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

        # Publish INITIALIZING status
        self._status_publisher.publish(
            status=StatusInfo.create(
                self.__class__.__name__,
                StatusType.INITIALIZING,
                game_server_instance_id=self._instance.game_server_instance_id,
            ),
        )

        if should_update:
            steam = SteamCMD(self._server_directory)
            steam.install(app_id=self._game_server.app_id)

        try:
            # TODO - temp workaround for env var, need to come from config
            extra_env = env_list_to_dict(self._config.env_var)
            logger.info("extra_env=%s", extra_env)
            self._proc.run(extra_env=extra_env)

            # Publish RUNNING status once process is started
            self._status_publisher.publish(
                status=StatusInfo.create(
                    self.__class__.__name__,
                    StatusType.RUNNING,
                    game_server_instance_id=self._instance.game_server_instance_id,
                ),
            )
        except Exception as e:
            logger.exception(e)
            self._shutdown()
            raise

        status = self._proc.status
        while status not in (ProcessBuilderStatus.STOPPED, ProcessBuilderStatus.FAILED) and not self.__is_stopped:
            # TODO - make this available through property or something
            self._proc.read_output()
            commands = self._command_message_provider.get_commands()
            if len(commands) > 0:
                logger.info("commands received: %s", commands)
                for command in commands:
                    self.execute_command(command)

            status = self._proc.status

        # do it one more time to clean up anything leftover
        self._proc.read_output()
        logger.info("instance %s has exited", self._instance.game_server_instance_id)
        self._shutdown()

        return self
