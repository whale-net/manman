import abc
import logging
import queue
import threading
from typing import Optional

import pika
import pika.channel
import pika.frame

from manman.models import Command

logger = logging.getLogger(__name__)


class MessageProvider(abc.ABC):
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


class RabbitMessageProvider(MessageProvider):
    """
    A message provider that retrieves commands from a RabbitMQ queue.

    This class sets up a connection to RabbitMQ, declares an exchange and
    a queue, and starts consuming messages from the queue in a separate
    thread.  It uses a blocking connection internally, managed in its own
    thread, to continuously listen for messages. Received messages are
    parsed as `Command` objects and placed in an internal queue for retrieval
    by the `get_commands` method.

    """

    def __init__(
        self,
        connection: pika.connection.Connection,
        exchange: str,
        queue_name: Optional[str] = None,
    ) -> None:
        self._queue_name = queue_name
        if self._queue_name is not None:
            # TODO - routing-keys in queue-bind
            raise NotImplementedError()
        self._exchange = exchange
        self._channel: pika.channel.Channel = connection.channel()
        self._channel.exchange_declare(exchange=self._exchange, exchange_type="direct")
        self._method: pika.frame.Method = self._channel.queue_declare(
            self._queue_name or "", exclusive=True
        )
        if self._method.method.queue is None:
            logger.error("unable to declare queue with name %s", self._queue_name)
            raise RuntimeError("failed to create queue")
        self._queue_name = self._method.method.queue
        logger.info("queue declared %s", self._queue_name)

        # TODO - should ideally use something other than a blocking connection in a thread
        #   but this will work for mvp
        self._name = f"rmq-{self._exchange}-{self._queue_name}"

        self._rabbit_thread = threading.Thread(
            target=self._start_consuming,
            name=self._name,
            daemon=True,
        )

        self._command_queue = queue.Queue()

        # this is non-blocking
        # this is also likely non-optimal, but good for mvp
        self._channel.basic_consume(
            queue=self._queue_name,
            on_message_callback=self._message_handler,
            auto_ack=True,
            # TODO consumer tag?
        )

        self._rabbit_thread.start()
        logger.info("rabbit message provider created %s", self._name)

    def _start_consuming(self):
        logger.info("starting to consume")
        self._channel.start_consuming()

    def _message_handler(self, ch, method, properties, body: bytes):  # noqa: F841
        command = Command.model_validate_json(body)
        self._command_queue.put(command)
        # auto-ack is set to true, so no need to ack

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
        # TODO - consumer tag?
        self._channel.basic_cancel()

        # TODO: no need to join, but whatever. it was in the old code
        self._rabbit_thread.join()
