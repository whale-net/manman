import abc
import logging
import queue
import threading
from typing import Optional

from amqpstorm import Connection, Message

from manman.models import Command, StatusInfo

logger = logging.getLogger(__name__)


class MessagePublisher(abc.ABC):
    """
    Abstract base class for message providers.
    This class defines the interface for sending messages.
    """

    @abc.abstractmethod
    def publish(self, command: Command) -> None:
        """
        Publish a message to the message provider.

        :param command: The command to be published.
        """
        pass

    @abc.abstractmethod
    def shutdown(self) -> None:
        """
        Shutdown the message provider.
        This method should clean up any resources used by the message provider.
        """
        pass


class MessageSubscriber(abc.ABC):
    """
    Abstract base class for message providers.
    This class defines the interface for receiving messages.
    """

    @abc.abstractmethod
    def get_commands(self) -> list[Command]:
        """
        Retrieve a list of messages from the message provider.
        This method should return a list of messages.

        Non-blocking

        """
        pass

    @abc.abstractmethod
    def shutdown(self) -> None:
        """
        Shutdown the message provider.
        This method should clean up any resources used by the message provider.
        """
        pass


class RabbitStatusPublisher(MessagePublisher):
    """
    A message provider that sends commands to a RabbitMQ queue.

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


class RabbitCommandSubscriber(MessageSubscriber):
    """
    A message provider that retrieves commands from a RabbitMQ queue.

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
