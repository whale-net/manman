"""
RabbitMQ publisher implementations.

This module contains concrete implementations of message publishers
for sending status messages via RabbitMQ.
"""

import logging
from typing import Optional

from amqpstorm import Connection

from manman.models import StatusInfo

from .base import MessagePublisher
from .util import add_routing_key_suffix

logger = logging.getLogger(__name__)


class RabbitStatusPublisher(MessagePublisher):
    """
    A message publisher that sends status messages to a RabbitMQ queue.

    This class sets up a connection to RabbitMQ, declares an exchange and
    a queue, and provides a method to publish messages to the queue.
    """

    def __init__(
        self, connection: Connection, exchange: str, routing_key_base: str
    ) -> None:
        """
        :param connection: An AMQPStorm connection to the RabbitMQ server.
        :param exchange: Exchange to bind to
        :param routing_key: Routing key for message publishing
        """
        self._exchange = exchange
        self._channel = connection.channel()
        self._routing_key = routing_key_base

        # Declare the exchange
        self._channel.exchange.declare(
            exchange=self._exchange,
            exchange_type="topic",
            durable=True,
            auto_delete=False,
        )

        logger.info("Rabbit message publisher created %s", self._exchange)

    def publish_external(self, status: StatusInfo) -> None:
        is_worker = status.worker_id is not None
        is_server = status.game_server_instance_id is not None

        if is_worker:
            class_type = "worker-instance"
            id = status.worker_id
        elif is_server:
            class_type = "game-server-instance"
            id = status.game_server_instance_id
        else:
            raise ValueError("worker or server must be set")

        suffix = f"{class_type}.{id}"
        self.publish(status, routing_key_suffix=suffix)

    def publish(
        self, status: StatusInfo, routing_key_suffix: Optional[str] = None
    ) -> None:
        message = status.model_dump_json()
        self._channel.basic.publish(
            body=message,
            exchange=self._exchange,
            routing_key=add_routing_key_suffix(self._routing_key, routing_key_suffix),
        )
        logger.info(
            "Message published to exchange %s with routing_key %s",
            self._exchange,
            self._routing_key,
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
