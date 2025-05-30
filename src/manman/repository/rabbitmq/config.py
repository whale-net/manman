"""
Concrete implementations of exchange and routing key configurations.

This module provides standard configurations for exchanges and routing keys
used by ManMan services.
"""

from .base import ExchangeConfig, RoutingKeyStrategy
from .util import add_routing_key_prefix


class WorkerExchangeConfig(ExchangeConfig):
    """Exchange configuration for worker services."""

    @property
    def exchange_name(self) -> str:
        return "worker"


class ServerExchangeConfig(ExchangeConfig):
    """Exchange configuration for server services."""

    @property
    def exchange_name(self) -> str:
        return "server"


class WorkerRoutingKeyStrategy(RoutingKeyStrategy):
    """Routing key strategy for worker services."""

    def generate_command_routing_key(self, worker_id: int) -> str:
        """Generate command routing key for a worker instance."""
        common_name = f"worker-instance.{worker_id}"
        return add_routing_key_prefix(common_name, "cmd")

    def generate_status_routing_key(self, worker_id: int) -> str:
        """Generate status routing key for a worker instance."""
        common_name = f"worker-instance.{worker_id}"
        return add_routing_key_prefix(common_name, "status")


class ServerRoutingKeyStrategy(RoutingKeyStrategy):
    """Routing key strategy for server services."""

    def generate_command_routing_key(self, game_server_instance_id: int) -> str:
        """Generate command routing key for a game server instance."""
        common_name = f"game-server-instance.{game_server_instance_id}"
        return add_routing_key_prefix(common_name, "cmd")

    def generate_status_routing_key(self, game_server_instance_id: int) -> str:
        """Generate status routing key for a game server instance."""
        common_name = f"game-server-instance.{game_server_instance_id}"
        return add_routing_key_prefix(common_name, "status")