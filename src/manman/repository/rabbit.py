import abc
import threading
import logging
import queue
from typing import Optional

import pika
import pika.channel
import pika.frame

from manman.models import Command, CommandType

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
    def __init__(self, connection: pika.connection.Connection, exchange: str, queue_name: Optional[str] = None) -> None:
        self._queue_name = queue_name
        self._exchange = exchange
        self._channel: pika.channel.Channel = connection.channel()
        self._channel.exchange_declare(exchange=self._exchange, exchange_type="direct")
        self._method: pika.frame.Method = self._channel.queue_declare(self._queue_name, exclusive=True)  # noqa - bad hint
        if self._method.method.queue is None:
            logger.error("unable to declare queue with name %s", self._queue_name)
            raise RuntimeError("failed to create queue")
        self._queue_name = self._method.method.queue
        logger.info("queue declared %s", self._queue_name)

        # TODO - should ideally use something other than a blocking connection in a thread
        #   but this will work for mvp
        self._name = f"rmq-{self._exchange}-{self._queue_name}"

        self._rabbit_thread = threading.Thread(
            target=self._blocking_wrapper,
            name=self._name,
            daemon=True,
        )

        self._command_queue = queue.Queue()
        self._rabbit_thread.start()
        logger.info("rabbit message provider created %s", self._name)

    def _blocking_wrapper(self):
        self._channel.queue_bind(
            exchange=self._exchange,
            queue=self._queue_name,
            routing_key=str(self._instance.game_server_instance_id),
        )

    def _process_queue(self):
            logger.info("starting to read queue")
        # while True:
        #     for message in self._rmq_channel.consume()
        self._rmq_channel.basic_consume(
            self._rmq_queue_name,
            on_message_callback=self._queue_message_handler,
            auto_ack=True,
            consumer_tag=str(self.instance.game_server_instance_id),
        )
        self._rmq_channel.start_consuming()
        logger.info("done consuming queue")

    def _queue_message_handler(self, ch, method, properties, body: bytes):
        command = Command.model_validate_json(body)
        self._command_queue.put(command)

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
        self._channel.basic_cancel(str(self.instance.game_server_instance_id))

        # TODO: JOIN????? - this is a blocking call???
        self._pq_thread.join()
