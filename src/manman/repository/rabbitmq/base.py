"""
Abstract base classes and common types for RabbitMQ messaging.

This module defines the interfaces for message publishers and subscribers,
along with common data structures used across the RabbitMQ implementation.
"""

import abc
from typing import NamedTuple

from manman.models import Command, StatusInfo


class StatusMessage(NamedTuple):
    """Container for status message with routing information."""

    status_info: StatusInfo
    routing_key: str


class MessagePublisher(abc.ABC):
    """
    Abstract base class for message publishers.
    This class defines the interface for sending messages.
    """

    @abc.abstractmethod
    def publish(self, status: StatusInfo, **kwargs) -> None:
        """
        Publish a status message to the message provider.

        :param status: The status information to be published.
        :param kwargs: Additional arguments specific to the implementation.
        """
        pass

    @abc.abstractmethod
    def shutdown(self) -> None:
        """
        Shutdown the message publisher.
        This method should clean up any resources used by the message publisher.
        """
        pass


class MessageSubscriber(abc.ABC):
    """
    Abstract base class for message subscribers.
    This class defines the interface for receiving messages.
    """

    @abc.abstractmethod
    def get_commands(self) -> list[Command]:
        """
        Retrieve a list of commands from the message provider.
        This method should return a list of commands.

        Non-blocking
        """
        pass

    @abc.abstractmethod
    def shutdown(self) -> None:
        """
        Shutdown the message subscriber.
        This method should clean up any resources used by the message subscriber.
        """
        pass


class ExchangeConfig(abc.ABC):
    """
    Abstract base class for exchange configuration.
    This class defines the interface for managing exchange names and types.
    """

    @property
    @abc.abstractmethod
    def exchange_name(self) -> str:
        """Get the exchange name for this configuration."""
        pass

    @property
    def exchange_type(self) -> str:
        """Get the exchange type. Defaults to 'topic'."""
        return "topic"

    @property
    def durable(self) -> bool:
        """Whether the exchange should be durable. Defaults to True."""
        return True

    @property
    def auto_delete(self) -> bool:
        """Whether the exchange should auto-delete. Defaults to False."""
        return False


class RoutingKeyStrategy(abc.ABC):
    """
    Abstract base class for routing key generation strategies.
    This class defines the interface for generating routing keys for different message types.
    """

    @abc.abstractmethod
    def generate_command_routing_key(self, instance_id: int) -> str:
        """
        Generate a routing key for commands targeting a specific instance.
        
        :param instance_id: The ID of the target instance
        :return: The routing key for commands
        """
        pass

    @abc.abstractmethod
    def generate_status_routing_key(self, instance_id: int) -> str:
        """
        Generate a routing key for status messages from a specific instance.
        
        :param instance_id: The ID of the source instance
        :return: The routing key for status messages
        """
        pass
