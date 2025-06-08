"""
RabbitMQ subscriber implementations.

This module contains concrete implementations of message subscribers
for receiving commands and status messages via RabbitMQ.
"""

import logging
import queue
import threading
from typing import List, Optional, Union

from amqpstorm import Channel, Connection, Message

from manman.models import Command
from manman.repository.message.abstract_interface import MessageSubscriberInterface
from manman.repository.rabbitmq.config import BindingConfig, QueueConfig

from .abstract_legacy import LegacyMessageSubscriber

logger = logging.getLogger(__name__)

# TODO - reduce duplication with RabbitCommandPublisher


class RabbitSubscriber(MessageSubscriberInterface):
    """
    Base class for RabbitMQ subscribers
    This class provides common functionality for subscribing to RabbitMQ exchanges.
    """

    def __init__(
        self,
        connection: Connection,
        binding_configs: Union[BindingConfig, list[BindingConfig]],
        queue_config: QueueConfig,
    ) -> None:
        self._channel: Channel = connection.channel()
        # Set QoS to ensure fair dispatching of messages
        self._channel.basic.qos(prefetch_count=1)

        if isinstance(binding_configs, BindingConfig):
            binding_configs = [binding_configs]
        self._binding_configs: list[BindingConfig] = binding_configs

        # exchange already declared

        # Declare queue
        logger.info("declaring queue with config: %s", queue_config)
        result = self._channel.queue.declare(
            queue=queue_config.name or "",
            durable=queue_config.durable,
            exclusive=queue_config.exclusive,
            auto_delete=queue_config.auto_delete,
        )

        # mutate config to store actual name. kind of a hack, but want to keep name stored
        queue_config.actual_queue_name = result.get("queue", queue_config.name)
        logger.info("Queue declared %s", queue_config.actual_queue_name)

        for binding_config in self._binding_configs:
            for routing_key in binding_config.routing_keys:
                self._channel.queue.bind(
                    exchange=binding_config.exchange,
                    queue=queue_config.actual_queue_name,
                    routing_key=str(routing_key),
                )
                logger.info(
                    "Queue %s bound to exchange %s with routing key '%s'",
                    queue_config.actual_queue_name,
                    binding_config.exchange,
                    routing_key,
                )

        self._internal_message_queue = queue.Queue()
        self._consumer_tag = self._channel.basic.consume(
            callback=self._message_handler,
            queue=queue_config.actual_queue_name,
            # no_ack=True,  # enable for at most, but message loss
        )

        self._consumer_thread = threading.Thread(
            target=self._channel.start_consuming,
            name=f"rmq-subscriber-{queue_config.actual_queue_name}",
            daemon=True,
        )
        self._consumer_thread.start()

        logger.info("RabbitSubscriber initialized with channel %s", self._channel)

    def _message_handler(self, message: Message):
        """
        Write messages to internal queue for retrieval in `consume` method.
        """
        self._internal_message_queue.put(message.body)
        message.ack()
        logger.info("Message received and acknowledged: %s", message.delivery_tag)

    def consume(self) -> List[str]:
        """
        Consume messages from the internal queue.
        This method retrieves all available messages and is non-blocking.

        :return: List of message bodies as strings.
        """
        messages = []
        while not self._internal_message_queue.empty():
            try:
                # don't block - will return immediately if no messages are available
                message_body = self._internal_message_queue.get(block=True)
                messages.append(message_body)
            except queue.Empty:
                break
        return messages

    # TODO - move this to common base rabbit connection wrapper class or something
    # feels bad having pub and sub
    # when eventually probably will have a pubsub
    def shutdown(self) -> None:
        """
        Shutdown the publisher by closing the channel.
        """
        logger.info("Shutting down RabbitPublisher...")

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
            if self._channel.is_open:
                self._channel.close()
                logger.info("Channel closed.")
        except Exception as e:
            logger.exception("Error closing channel: %s", e)

    def __del__(self) -> None:
        """
        Destructor to ensure the channel is closed when the object is deleted.
        """
        try:
            self.shutdown()
        except Exception:
            # Suppress exceptions during cleanup to avoid issues during interpreter shutdown
            pass


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
