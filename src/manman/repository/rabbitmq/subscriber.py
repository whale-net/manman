"""
RabbitMQ subscriber implementations.

This module contains concrete implementations of message subscribers
for receiving commands and status messages via RabbitMQ.
"""

import logging
import queue
import threading
from typing import Dict, List, Optional, Union

from amqpstorm import Connection, Message

from manman.models import Command, StatusInfo

from .base import LegacyMessageSubscriber, StatusMessage

logger = logging.getLogger(__name__)


class LegacyRabbitCommandSubscriber(LegacyMessageSubscriber):
    """
    A message subscriber that retrieves commands from a RabbitMQ queue.

    This class sets up a connection to RabbitMQ, declares an exchange and
    a queue, and starts consuming messages from the queue in a separate
    thread.  It uses AMQPStorm's thread-safe connection internally, managed
    in its own thread, to continuously listen for messages. Received messages are
    parsed as `Command` objects and placed in an internal queue for retrieval
    by the `get_commands` method.
    """

    def __init__(
        self,
        connection: Connection,
        exchange: str,
        queue_name: Optional[str] = None,
    ) -> None:
        """
        :param connection: An AMQPStorm connection to the RabbitMQ server.
        :param exchange: Exchange to bind to
        :param queue_name: Name of queue to bind to the exchange. If None, a random name will be generated.
        """
        self._queue_name = queue_name
        self._exchange = exchange
        self._channel = connection.channel()

        # Declare queue
        result = self._channel.queue.declare(
            queue=self._queue_name or "",
            # exclusive=True,
            auto_delete=True,
        )
        if not result:
            logger.error("Unable to declare queue with name %s", self._queue_name)
            raise RuntimeError("Failed to create queue")

        self._queue_name = result["queue"]
        logger.info("Queue declared %s", self._queue_name)

        # Bind the queue to the exchange
        self._channel.queue.bind(
            exchange=self._exchange,
            queue=self._queue_name,
        )
        logger.info(
            "Queue %s bound to exchange %s",
            self._queue_name,
            self._exchange,
        )

        self._name = f"rmq-{self._exchange}-{self._queue_name}"
        self._command_queue = queue.Queue()
        self._consumer_tag = None

        # Set up consumption
        self._consumer_tag = self._channel.basic.consume(
            callback=self._message_handler,
            queue=self._queue_name,
            no_ack=True,  # equivalent to auto_ack=True in pika
        )

        # Start consuming in a separate thread
        self._rabbit_thread = threading.Thread(
            target=self._start_consuming,
            name=self._name,
            daemon=True,
        )
        self._rabbit_thread.start()

        logger.info("Rabbit message subscriber created %s", self._name)

    def _start_consuming(self):
        logger.info("Starting to consume")
        self._channel.start_consuming()

    def _message_handler(self, message: Message):
        try:
            command = Command.model_validate_json(message.body)
            self._command_queue.put(command)
            # No need to ack as no_ack=True is set
        except Exception as e:
            logger.exception("Error processing message: %s", e)

    def get_commands(self) -> list[Command]:
        commands = []
        while not self._command_queue.empty():
            try:
                command: Command = self._command_queue.get(timeout=1)
                commands.append(command)
            except queue.Empty:
                break
        return commands

    def shutdown(self) -> None:
        logger.info("Shutting down RabbitMessageSubscriber...")

        try:
            # Cancel the consumer
            if self._consumer_tag and self._channel.is_open:
                self._channel.basic.cancel(self._consumer_tag)
                logger.info("Consumer cancelled.")
        except Exception as e:
            logger.exception("Error cancelling consumer: %s", e)

        try:
            # Stop consuming
            if self._channel.is_open:
                self._channel.stop_consuming()
                logger.info("Stopped consuming.")
        except Exception as e:
            logger.exception("Error stopping consuming: %s", e)

        try:
            # Close the channel
            if self._channel.is_open:
                self._channel.close()
                logger.info("Channel closed.")
        except Exception as e:
            logger.exception("Error closing channel: %s", e)


class RabbitStatusSubscriber:
    """
    A message subscriber that retrieves status messages from a RabbitMQ queue.

    This class sets up a connection to RabbitMQ, declares an exchange and
    a queue, and starts consuming messages from the queue in a separate
    thread. It uses AMQPStorm's thread-safe connection internally, managed
    in its own thread, to continuously listen for messages. Received messages are
    parsed as `StatusInfo` objects and placed in an internal queue for retrieval
    by the `get_status_messages` method.

    Supports both exact routing key matches and wildcard patterns when used with topic exchanges.
    Can consume from multiple exchanges with different routing keys.
    """

    def __init__(
        self,
        connection: Connection,
        exchange: Optional[str] = None,
        routing_key: str = "",
        queue_name: Optional[str] = None,
        exchanges_config: Optional[Dict[str, Union[str, List[str]]]] = None,
    ) -> None:
        """
        :param connection: An AMQPStorm connection to the RabbitMQ server.
        :param exchange: Single exchange to bind to (legacy parameter, use exchanges_config for multiple)
        :param routing_key: Single routing key pattern (legacy parameter, use exchanges_config for multiple)
        :param queue_name: Name of queue to bind to the exchange. If None, a random name will be generated.
        :param exchanges_config: Dictionary mapping exchange names to routing key(s).
                               Format: {"exchange1": "routing.key", "exchange2": ["key1", "key2"]}
                               If provided, takes precedence over exchange/routing_key parameters.
        """
        self._queue_name = queue_name
        self._channel = connection.channel()

        # Handle both old single exchange and new multiple exchanges configuration
        if exchanges_config:
            self._exchanges_config = exchanges_config
        elif exchange:
            # Legacy single exchange support
            self._exchanges_config = {exchange: routing_key}
        else:
            raise ValueError("Either 'exchange' or 'exchanges_config' must be provided")

        # Declare queue
        result = self._channel.queue.declare(
            queue=self._queue_name or "",
            auto_delete=False,
        )
        if not result:
            logger.error("Unable to declare queue with name %s", self._queue_name)
            raise RuntimeError("Failed to create queue")

        self._queue_name = result["queue"]
        logger.info("Status queue declared %s", self._queue_name)

        # Bind the queue to all configured exchanges with their routing keys
        for exchange_name, routing_keys in self._exchanges_config.items():
            # Ensure routing_keys is always a list
            if isinstance(routing_keys, str):
                routing_keys = [routing_keys]

            for routing_key in routing_keys:
                self._channel.queue.bind(
                    exchange=exchange_name,
                    queue=self._queue_name,
                    routing_key=routing_key,
                )
                logger.info(
                    "Queue %s bound to exchange %s with routing key '%s'",
                    self._queue_name,
                    exchange_name,
                    routing_key,
                )

        # Generate a descriptive name based on all exchanges
        exchange_names = "-".join(self._exchanges_config.keys())
        self._name = f"rmq-status-{exchange_names}-{self._queue_name}"
        self._status_queue = queue.Queue()
        self._consumer_tag = None

        # Set up consumption
        self._consumer_tag = self._channel.basic.consume(
            callback=self._message_handler,
            queue=self._queue_name,
            no_ack=True,  # equivalent to auto_ack=True in pika
        )

        # Start consuming in a separate thread
        self._rabbit_thread = threading.Thread(
            target=self._start_consuming,
            name=self._name,
            daemon=True,
        )
        self._rabbit_thread.start()

        logger.info("Rabbit status subscriber created %s", self._name)

    def _start_consuming(self):
        logger.info("Starting to consume status messages")
        self._channel.start_consuming()

    def _message_handler(self, message: Message):
        try:
            status_info = StatusInfo.model_validate_json(message.body)

            # Capture routing key from the message
            routing_key = message.method.get("routing_key", "")
            status_message = StatusMessage(
                status_info=status_info, routing_key=routing_key
            )
            self._status_queue.put(status_message)
            logger.debug(
                "Status message received and queued: %s from routing key: %s",
                status_info.class_name,
                routing_key,
            )
            # No need to ack as no_ack=True is set
        except Exception as e:
            logger.exception("Error processing status message: %s", e)
            logger.error("Message body was: %s", message.body)

    def get_status_messages(self) -> list[StatusMessage]:
        """
        Retrieve a list of status messages from the subscriber.
        This method returns all available messages and is non-blocking.

        :return: List of StatusMessage objects containing status info and routing key
        """
        status_messages = []
        while not self._status_queue.empty():
            try:
                status_message: StatusMessage = self._status_queue.get(timeout=1)
                status_messages.append(status_message)
            except queue.Empty:
                break
        return status_messages

    def shutdown(self) -> None:
        logger.info("Shutting down RabbitStatusSubscriber...")

        try:
            # Cancel the consumer
            if self._consumer_tag and self._channel.is_open:
                self._channel.basic.cancel(self._consumer_tag)
                logger.info("Status consumer cancelled.")
        except Exception as e:
            logger.exception("Error cancelling status consumer: %s", e)

        try:
            # Stop consuming
            if self._channel.is_open:
                self._channel.stop_consuming()
                logger.info("Stopped consuming status messages.")
        except Exception as e:
            logger.exception("Error stopping consuming: %s", e)

        try:
            # Close the channel
            if self._channel.is_open:
                self._channel.close()
                logger.info("Status channel closed.")
        except Exception as e:
            logger.exception("Error closing status channel: %s", e)
