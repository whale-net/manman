"""
RabbitMQ publisher implementations.

This module contains concrete implementations of message publishers
for sending status messages via RabbitMQ.
"""

import logging

from amqpstorm import Connection

from manman.models import StatusInfo

from .base import MessagePublisher

logger = logging.getLogger(__name__)


class RabbitStatusPublisher(MessagePublisher):
    """
    A message publisher that sends status messages to a RabbitMQ queue.

    This class sets up a connection to RabbitMQ, declares an exchange and
    a queue, and provides a method to publish messages to the queue.
    """

    @staticmethod
    def get_internal_queue_name(queue_name: str) -> str:
        """
        Generate a unique internal queue name based on the provided queue name.
        This is used to ensure that the queue name is unique across different instances.
        """
        return f"{queue_name}"

    def __init__(self, connection: Connection, exchange: str, routing_key: str) -> None:
        """
        :param connection: An AMQPStorm connection to the RabbitMQ server.
        :param exchange: Exchange to bind to
        :param routing_key: Routing key for message publishing
        """
        self._exchange = exchange
        self._channel = connection.channel()
        self._queue_name = routing_key

        # Declare queue
        result = self._channel.queue.declare(
            queue=self._queue_name,
            auto_delete=True,
        )
        self._channel.queue.bind(
            exchange=exchange, queue=self._queue_name, routing_key=routing_key
        )
        if not result:
            logger.error("Unable to declare queue with name %s", self._queue_name)
            raise RuntimeError("Failed to create queue")
        self._queue_name = result["queue"]
        logger.info("Queue declared %s", self._queue_name)
        logger.info("Rabbit message publisher created %s", self._exchange)

    def publish(self, status: StatusInfo) -> None:
        message = status.model_dump_json()
        self._channel.basic.publish(
            body=message,
            exchange=self._exchange,
            routing_key=self._queue_name,
        )
        logger.info("Message published to exchange %s", self._exchange)
        logger.debug("Message: %s", message)

    def shutdown(self) -> None:
        logger.info("Shutting down RabbitMessagePublisher...")
        try:
            # Close the channel
            if self._channel.is_open:
                self._channel.close()
                logger.info("Channel closed.")
        except Exception as e:
            logger.exception("Error closing channel: %s", e)
