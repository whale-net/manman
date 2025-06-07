"""
RabbitMQ publisher implementations.

This module contains concrete implementations of message publishers
for sending status messages via RabbitMQ.
"""

import logging
from typing import Dict, List, Optional, Union

from amqpstorm import Connection

from manman.models import StatusInfo

from .base import MessagePublisher
from .util import add_routing_key_suffix, declare_exchange, ExchangesConfig, generate_name_from_exchanges

logger = logging.getLogger(__name__)


class RabbitStatusPublisher(MessagePublisher):
    """
    A message publisher that sends status messages to RabbitMQ exchanges.

    This class sets up a connection to RabbitMQ, declares exchanges and
    provides methods to publish messages to one or more exchanges with
    different routing keys.

    Supports both single exchange configuration (for backward compatibility)
    and multiple exchanges configuration using a dictionary mapping exchanges
    to lists of routing keys.
    """

    def __init__(
        self,
        connection: Connection,
        exchange: Optional[str] = None,
        routing_key_base: Optional[str] = None,
        exchanges_config: Optional[Dict[str, Union[str, List[str]]]] = None,
    ) -> None:
        """
        :param connection: An AMQPStorm connection to the RabbitMQ server.
        :param exchange: Single exchange to bind to (legacy parameter)
        :param routing_key_base: Base routing key for single exchange (legacy parameter)
        :param exchanges_config: Dictionary mapping exchanges to routing keys
                                Format: {exchange_name: routing_key} or {exchange_name: [routing_key1, routing_key2]}
        """
        self._channel = connection.channel()

        # Handle both old single exchange and new multiple exchanges configuration
        if exchanges_config:
            self._exchanges_config = ExchangesConfig.from_dict(exchanges_config)
        elif exchange and routing_key_base is not None:
            # Legacy single exchange support
            self._exchanges_config = ExchangesConfig.from_legacy(exchange, routing_key_base)
        else:
            raise ValueError(
                "Either 'exchange' and 'routing_key_base' or 'exchanges_config' must be provided"
            )

        # Declare all exchanges using helper function
        for exchange_obj in self._exchanges_config.exchanges:
            declare_exchange(self._channel, exchange_obj.name)

        # Generate a descriptive name based on all exchanges using helper function
        exchange_names = generate_name_from_exchanges(self._exchanges_config)
        logger.info(
            "Rabbit message publisher created for exchanges: %s", exchange_names
        )

    # TODO- make publish external its own class
    def publish_external(self, status: StatusInfo) -> None:
        is_worker = status.worker_id is not None
        is_server = status.game_server_instance_id is not None

        if is_worker:
            class_type = "worker-instance"
            id = status.worker_id
        elif is_server:
            class_type = "game-server-instance"
            id = status.game_server_instance_id
            logger.info("TEST IT WAS SERVER")
        else:
            raise ValueError("worker or server must be set")

        suffix = f"{class_type}.{id}"
        self.publish(status, routing_key_suffix=suffix)

    def publish(
        self, status: StatusInfo, routing_key_suffix: Optional[str] = None
    ) -> None:
        """
        Publish a status message to all configured exchanges with their routing keys.

        :param status: The status information to be published.
        :param routing_key_suffix: Optional suffix to add to all routing keys.
        """
        message = status.model_dump_json()

        # Publish to all configured exchanges with their routing keys
        for exchange_obj in self._exchanges_config.exchanges:
            for routing_key in exchange_obj.routing_keys:
                final_routing_key = add_routing_key_suffix(
                    routing_key, routing_key_suffix
                )
                self._channel.basic.publish(
                    body=message,
                    exchange=exchange_obj.name,
                    routing_key=final_routing_key,
                )
                logger.debug(
                    "Message published to exchange %s with routing_key %s",
                    exchange_obj.name,
                    final_routing_key,
                )

    def shutdown(self) -> None:
        logger.info("Shutting down RabbitMessagePublisher...")
        try:
            # Close the channel
            if self._channel.is_open:
                self._channel.close()
                logger.info("Channel closed.")
        except Exception as e:
            logger.exception("Error closing channel: %s", e)
