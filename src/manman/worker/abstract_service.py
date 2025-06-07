import logging
from abc import ABC, abstractmethod

from amqpstorm import Connection

from manman.models import StatusType
from manman.repository.rabbitmq.base import (
    LegacyMessagePublisher,
    LegacyMessageSubscriber,
)
from manman.repository.rabbitmq.config import (
    BindingConfig,
    EntityRegistrar,
    ExchangeRegistrar,
    MessageTypeRegistry,
    RoutingKeyConfig,
)
from manman.repository.rabbitmq.publisher import RabbitStatusPublisher

logger = logging.getLogger(__name__)


class ManManService(ABC):
    """
    Abstract base class services with lifecycle and command consumption capabilities.
    """

    RMQ_EXCHANGE: ExchangeRegistrar = ExchangeRegistrar.MANMAN_SERVICE_EVENT

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

    def _legacy_extra_status_routing_key(self) -> list[str]:
        return []

    def _legacy_extra_command_routing_key(self) -> list[str]:
        return []

    def __build_status_publisher(self) -> LegacyMessagePublisher:
        status_binding = BindingConfig(
            exchange=self.RMQ_EXCHANGE,
            routing_keys=[
                self.status_routing_key.build_key(),
                *self._legacy_extra_status_routing_key(),
            ],
        )
        return RabbitStatusPublisher(self._rmq_conn, status_binding)

    def __build_command_consumer(self) -> LegacyMessageSubscriber:
        command_binding = BindingConfig(
            exchange=self.RMQ_EXCHANGE,
            routing_keys=[
                self.command_routing_key.build_key(),
                *self._legacy_extra_command_routing_key(),
            ],
        )
        print(command_binding)
        return

    def __init__(self, rabbitmq_connection: Connection):
        """
        Initialize the service with a RabbitMQ connection.

        :param rabbitmq_connection: An AMQPStorm connection to the RabbitMQ server.
        """

        if not hasattr(self, "_identifier"):
            raise AttributeError("Service must have an 'identifier' attribute set.")

        logger.info("Creating service: %s", self.__class__.__name__)
        self.__is_started = False
        self.__is_running = False
        self.__is_stopped = False
        # keep track of whether the service has been initialized
        # this is used for deciding whether to send init status update
        self.__initialize_skipped = False

        self._rmq_conn = rabbitmq_connection

        self._status_publisher = self.__build_status_publisher()

        self._command_consumer = self.__build_command_consumer()

    def run(self):
        """
        Run the service. This method should be called to start the service.
        It will initialize the service and then start it.
        """
        logger.info("Initializing service: %s", self.__class__.__name__)
        self._initialize()
        if self.__initialize_skipped:
            logger.info(
                "Initialization was skipped for service: %s", self.__class__.__name__
            )
        else:
            self._status_publisher.publish(
                status=StatusType.CREATED,
                routing_key_suffix=self.identifier,
            )

        self.start()
        self.__is_running = True

    def _initialize(self):
        """
        Initialize the service.
        This method should set up any necessary state or resources.
        """
        self.__initialize_skipped = True

    @abstractmethod
    def start(self):
        """
        Start the service.
        """
        raise NotImplementedError("Subclasses must implement this method.")

    @abstractmethod
    def stop(self):
        """
        Stop the service.
        """
        raise NotImplementedError("Subclasses must implement this method.")
