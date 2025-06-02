"""
RabbitMQ messaging implementation.

This module provides a complete RabbitMQ-based messaging system with
separate publishers and subscribers for commands and status messages.

Public API:
    - MessagePublisher, MessageSubscriber: Abstract base classes
    - ExchangeConfig, RoutingKeyStrategy: Abstract base classes for messaging configuration
    - StatusMessage: Container for status messages with routing info
    - RabbitStatusPublisher: Publishes status messages to RabbitMQ
    - RabbitCommandSubscriber: Subscribes to commands from RabbitMQ
    - RabbitStatusSubscriber: Subscribes to status messages from RabbitMQ
    - WorkerExchangeConfig, ServerExchangeConfig: Standard exchange configurations
    - WorkerRoutingKeyStrategy, ServerRoutingKeyStrategy: Standard routing key strategies
"""

from .base import (
    ExchangeConfig,
    MessagePublisher,
    MessageSubscriber,
    RoutingKeyStrategy,
    StatusMessage,
)
from .config import (
    ServerExchangeConfig,
    ServerRoutingKeyStrategy,
    WorkerExchangeConfig,
    WorkerRoutingKeyStrategy,
)
from .publisher import RabbitStatusPublisher
from .subscriber import RabbitCommandSubscriber, RabbitStatusSubscriber

__all__ = [
    # Abstract base classes
    "MessagePublisher",
    "MessageSubscriber",
    "ExchangeConfig",
    "RoutingKeyStrategy",
    # Data types
    "StatusMessage",
    # Concrete implementations - messaging
    "RabbitStatusPublisher",
    "RabbitCommandSubscriber",
    "RabbitStatusSubscriber",
    # Concrete implementations - configurations
    "WorkerExchangeConfig",
    "ServerExchangeConfig",
    "WorkerRoutingKeyStrategy",
    "ServerRoutingKeyStrategy",
]
