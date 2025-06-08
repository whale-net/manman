"""
Abstract base classes and common types for RabbitMQ messaging.

This module defines the interfaces for message publishers and subscribers,
along with common data structures used across the RabbitMQ implementation.
"""

import abc
from typing import NamedTuple

from manman.models import Command, ExternalStatusInfo


class StatusMessage(NamedTuple):
    """Container for status message with routing information."""

    status_info: ExternalStatusInfo
    routing_key: str


class LegacyMessagePublisher(abc.ABC):
    """
    Abstract base class for message publishers.
    This class defines the interface for sending messages.
    """

    @abc.abstractmethod
    def publish(self, status: ExternalStatusInfo, **kwargs) -> None:
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


class LegacyMessageSubscriber(abc.ABC):
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
