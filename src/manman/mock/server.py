"""Mock Server implementation that simulates server lifecycle without actual processes."""
import logging
import os
import time
from typing import Self

from amqpstorm import Connection

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
from manman.mock.processbuilder import MockProcessBuilder
from manman.worker.processbuilder import ProcessBuilderStatus

logger = logging.getLogger(__name__)


class MockServer:
    """A mock server that simulates server lifecycle without executing real processes."""
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
        logger.info("starting mock instance %s", self._instance.model_dump_json())

        self._command_message_provider = RabbitCommandSubscriber(
            connection=rabbitmq_connection,
            exchange=MockServer.RMQ_EXCHANGE,
            queue_name=self.command_routing_key,
        )

        self._status_publisher = RabbitStatusPublisher(
            connection=rabbitmq_connection,
            exchange=MockServer.RMQ_EXCHANGE,
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

        # Use mock ProcessBuilder instead of real one
        executable_path = os.path.join(self._server_directory, self._config.executable)
        pb = MockProcessBuilder(executable=executable_path)
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

    @property
    def is_shutdown(self) -> bool:
        return self.__is_stopped

    @staticmethod
    def _generate_common_queue_prefix(game_server_instance_id: int) -> str:
        return f"game-server-instance.{game_server_instance_id}"

    @staticmethod
    def generate_command_queue_name(game_server_instance_id: int):
        return add_routing_key_prefix(
            MockServer._generate_common_queue_prefix(game_server_instance_id),
            "cmd",
        )

    @staticmethod
    def generate_status_queue_name(game_server_instance_id: int):
        return add_routing_key_prefix(
            MockServer._generate_common_queue_prefix(game_server_instance_id), "status"
        )

    @property
    def command_routing_key(self) -> str:
        return self.generate_command_queue_name(self._instance.game_server_instance_id)

    @property
    def status_routing_key(self) -> str:
        return self.generate_status_queue_name(self._instance.game_server_instance_id)

    def execute_command(self, command: Command):
        """Execute a command on the mock server."""
        logger.info("mock server received command %s", command)
        if command.command_type == CommandType.STOP:
            self.stop()
        elif command.command_type == CommandType.STDIN:
            if len(command.command_args) > 1:
                stdin_input = " ".join(command.command_args[1:])
                self._proc.write_stdin(stdin_input)
        else:
            logger.warning("unsupported command for mock server %s", command)

    def stop(self):
        """Stop the mock server."""
        logger.info("stopping mock server %s", self._instance.game_server_instance_id)
        self._proc.stop()
        self._shutdown()

    def run(self, should_update: bool = True) -> Self:
        """Run the mock server through its lifecycle."""
        if self.__is_started:
            logger.error(
                "duplicate start command received, current_status = %s",
                self._proc.status,
            )
            raise RuntimeError("mock server already started, cannot start again")
        self.__is_started = True
        logger.info("mock instance %s starting", self._instance.game_server_instance_id)

        # Publish INITIALIZING status
        self._status_publisher.publish(
            status=StatusInfo.create(
                self.__class__.__name__,
                StatusType.INITIALIZING,
                game_server_instance_id=self._instance.game_server_instance_id,
            ),
        )

        try:
            # Mock server doesn't need steamcmd installation
            if should_update:
                logger.info("Mock server skipping steamcmd installation")

            # Start the mock process
            self._proc.run()

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
        while status != ProcessBuilderStatus.STOPPED and not self.__is_stopped:
            # Mock reading output
            self._proc.read_output()
            commands = self._command_message_provider.get_commands()
            if len(commands) > 0:
                logger.info("commands received: %s", commands)
                for command in commands:
                    self.execute_command(command)

            status = self._proc.status
            # Sleep briefly to simulate processing time
            time.sleep(0.1)

        # do it one more time to clean up anything leftover
        self._proc.read_output()
        logger.info("mock instance %s has exited", self._instance.game_server_instance_id)

        self._shutdown()
        return self

    def _shutdown(self):
        """Shutdown the mock server and clean up resources."""
        if self.__is_stopped:
            return

        logger.info("shutting down mock server %s", self._instance.game_server_instance_id)

        # Publish COMPLETE status
        self._status_publisher.publish(
            status=StatusInfo.create(
                self.__class__.__name__,
                StatusType.COMPLETE,
                game_server_instance_id=self._instance.game_server_instance_id,
            ),
        )

        self._command_message_provider.shutdown()
        self._status_publisher.shutdown()
        self.__is_stopped = True