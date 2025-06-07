"""
RabbitMQ messaging implementation.

This module provides a complete RabbitMQ-based messaging system with
separate publishers and subscribers for commands and status messages.

Public API:
    - MessagePublisher, MessageSubscriber: Abstract base classes
    - StatusMessage: Container for status messages with routing info
    - RabbitStatusPublisher: Publishes status messages to RabbitMQ
    - RabbitCommandSubscriber: Subscribes to commands from RabbitMQ
    - RabbitStatusSubscriber: Subscribes to status messages from RabbitMQ
"""

from .base import LegacyMessagePublisher, LegacyMessageSubscriber, StatusMessage
from .publisher import LegacyRabbitStatusPublisher
from .subscriber import LegacyRabbitCommandSubscriber, RabbitStatusSubscriber

__all__ = [
    # Abstract base classes
    "LegacyMessagePublisher",
    "LegacyMessageSubscriber",
    # Data types
    "StatusMessage",
    # Concrete implementations
    "LegacyRabbitStatusPublisher",
    "LegacyRabbitCommandSubscriber",
    "RabbitStatusSubscriber",
]
