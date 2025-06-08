import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone

from amqpstorm import Connection

from manman.models import Command, InternalStatusInfo, StatusType
from manman.repository.message.pub import (
    StatusInfoPubService,
)
from manman.repository.message.sub import CommandSubService
from manman.repository.rabbitmq.config import (
    BindingConfig,
    EntityRegistrar,
    ExchangeRegistrar,
    MessageTypeRegistry,
    QueueConfig,
    RoutingKeyConfig,
)
from manman.repository.rabbitmq.publisher import RabbitPublisher
from manman.repository.rabbitmq.subscriber import RabbitSubscriber

logger = logging.getLogger(__name__)


class ManManService(ABC):
    """
    Abstract base class services with lifecycle and command consumption capabilities.
    """

    RMQ_EXCHANGE: ExchangeRegistrar = ExchangeRegistrar.INTERNAL_SERVICE_EVENT

    # this is surely too short, but it is just a heartbeat
    HEARTBEAT_INTERVAL: timedelta = timedelta(seconds=2)
    RUN_LOOP_INTERVAL: timedelta = timedelta(milliseconds=100)

    @property
    @abstractmethod
    def service_entity_type(self) -> EntityRegistrar:
        """
        Get the entity type for the service.
        """
        raise NotImplementedError(
            "Subclasses must implement the 'service_entity_type' property."
        )

    @property
    @abstractmethod
    def identifier(self) -> str:
        """
        Get the identifier for the service.

        NOTE: this will be called in the constructor, so it must be defined before the constructor is called.

        :return: The identifier string.
        """
        raise NotImplementedError(
            "Subclasses must implement the 'identifier' property."
        )

    @property
    def status_routing_key(self) -> RoutingKeyConfig:
        """
        Generate the routing key for status messages.
        """
        return RoutingKeyConfig(
            entity=self.service_entity_type,
            identifier=self.identifier,
            type=MessageTypeRegistry.STATUS,
        )

    @property
    def command_routing_key(self) -> RoutingKeyConfig:
        """
        Generate the routing key for command messages.
        """
        return RoutingKeyConfig(
            entity=self.service_entity_type,
            identifier=self.identifier,
            type=MessageTypeRegistry.COMMAND,
        )

    @property
    def command_queue_config(self) -> QueueConfig:
        """
        Generate the queue configuration for command messages.
        """
        return QueueConfig(
            name=f"dev-queue-name-{self.service_entity_type.name}-{self.identifier}",
            durable=True,
            exclusive=False,
            auto_delete=True,
        )

    def _legacy_extra_status_routing_key(self) -> list[str]:
        return []

    def _legacy_extra_command_routing_key(self) -> list[str]:
        return []

    def __build_status_publisher(self) -> StatusInfoPubService:
        status_binding = BindingConfig(
            exchange=self.RMQ_EXCHANGE,
            routing_keys=[
                self.status_routing_key.build_key(),
                *self._legacy_extra_status_routing_key(),
            ],
        )
        rabbit_publisher = RabbitPublisher(
            connection=self._rmq_conn,
            binding_configs=status_binding,
        )
        return StatusInfoPubService(publisher=rabbit_publisher)

    def __build_command_consumer(self) -> CommandSubService:
        command_binding = BindingConfig(
            exchange=self.RMQ_EXCHANGE,
            routing_keys=[
                self.command_routing_key.build_key(),
                *self._legacy_extra_command_routing_key(),
            ],
        )
        rabbit_subscriber = RabbitSubscriber(
            connection=self._rmq_conn,
            binding_configs=command_binding,
            queue_config=self.command_queue_config,
        )
        return CommandSubService(subscriber=rabbit_subscriber)

    def __create_internal_status_info(
        self,
        status_type: StatusType,
    ) -> InternalStatusInfo:
        """
        Create an InternalStatusInfo object for the service.

        :param status_type: The status type to set.
        :return: An InternalStatusInfo object with the service name and status type.
        """
        return InternalStatusInfo.create(
            entity_type=self.service_entity_type,
            identifier=self.identifier,
            status_type=status_type,
        )

    def __init__(self, rabbitmq_connection: Connection, **kwargs) -> None:
        """
        Initialize the service with a RabbitMQ connection.

        :param rabbitmq_connection: An AMQPStorm connection to the RabbitMQ server.
        """

        if len(kwargs) > 0:
            logger.warning(
                "Unused keyword arguments in %s: %s",
                self.__class__.__name__,
                ", ".join(kwargs.keys()),
            )

        logger.info("Creating service: %s", self.__class__.__name__)
        self.__is_stopped = False

        self._rmq_conn = rabbitmq_connection
        self._status_pub_service = self.__build_status_publisher()
        self._command_sub_service = self.__build_command_consumer()

        self._status_pub_service.publish_status(
            internal_status=self.__create_internal_status_info(StatusType.CREATED),
        )

    def run(self):
        """
        Run the service.

        This is the main entry point for the service lifecycle.
        It initializes the service, starts it, and handles any necessary setup.
        """
        logger.info("Initializing service: %s", self.__class__.__name__)
        self._status_pub_service.publish_status(
            internal_status=self.__create_internal_status_info(StatusType.INITIALIZING),
        )

        self._initialize_service()

        # TODO - this gives no time for the service to start running
        # this will be problematic for game servers that take a while to start
        self._status_pub_service.publish_status(
            internal_status=self.__create_internal_status_info(StatusType.RUNNING),
        )

        loop_log_time = datetime.now(timezone.utc)
        loop_heartbeat_time = datetime.now(timezone.utc)
        while not self.__is_stopped:
            # timing
            run_loop_start_time = datetime.now(timezone.utc)
            if (run_loop_start_time - loop_log_time) > timedelta(seconds=30):
                logger.info("Service %s is running", self.__class__.__name__)
                loop_log_time = run_loop_start_time
            if (run_loop_start_time - loop_heartbeat_time) > self.HEARTBEAT_INTERVAL:
                self._send_heartbeat()
                loop_heartbeat_time = run_loop_start_time

            # Perform the main work of the service
            self._do_work()

            # Handle any commands received from the command queue
            commands = self._command_sub_service.get_commands()
            self._handle_commmands(commands)

            # Sleep to avoid busy waiting
            run_loop_end_time = datetime.now(timezone.utc)
            run_loop_run_time = run_loop_end_time - run_loop_start_time
            remaining_loop_time = (
                self.RUN_LOOP_INTERVAL - run_loop_run_time
            ).total_seconds()
            if remaining_loop_time > 0:
                time.sleep(remaining_loop_time)

        self._status_pub_service.publish_status(
            internal_status=self.__create_internal_status_info(StatusType.COMPLETE),
        )

    @abstractmethod
    def _send_heartbeat(self):
        """
        Send a heartbeat message to indicate the service is running.
        """
        pass

    @abstractmethod
    def _initialize_service(self):
        """
        Initialize the service.

        Do extra non-init setup here, such as installing service runtime dependencies
        """
        pass

    @abstractmethod
    def _do_work(self):
        """
        Do work in a loop
        """
        pass

    @abstractmethod
    def _handle_commmands(self, commands: list[Command]):
        """
        Handle commands received from the command queue.
        """
        pass
