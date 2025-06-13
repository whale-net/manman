"""
RabbitMQ subscriber implementations.

This module contains concrete implementations of message subscribers
for receiving commands and status messages via RabbitMQ.
"""

import logging
import queue
import threading
import time
from typing import Callable, List, Union

from amqpstorm import AMQPConnectionError, Channel, Connection, Message

from manman.repository.message.abstract_interface import MessageSubscriberInterface
from manman.repository.rabbitmq.config import BindingConfig, QueueConfig

logger = logging.getLogger(__name__)

# TODO - reduce duplication with RabbitCommandPublisher


class RabbitSubscriber(MessageSubscriberInterface):
    """
    Base class for RabbitMQ subscribers with automatic channel recovery.
    This class provides common functionality for subscribing to RabbitMQ exchanges
    and automatically recovers from connection/channel failures.
    """

    def __init__(
        self,
        connection_provider: Callable[[], Connection],
        binding_configs: Union[BindingConfig, list[BindingConfig]],
        queue_config: QueueConfig,
        recovery_registry: Callable[[Callable], None] = None,
        recovery_unregistry: Callable[[Callable], None] = None,
    ) -> None:
        self._connection_provider = connection_provider
        self._queue_config = queue_config
        self._recovery_registry = recovery_registry
        self._recovery_unregistry = recovery_unregistry

        if isinstance(binding_configs, BindingConfig):
            binding_configs = [binding_configs]
        self._binding_configs: list[BindingConfig] = binding_configs

        self._channel: Channel = None
        self._consumer_tag: str = None
        self._consumer_thread: threading.Thread = None
        self._internal_message_queue = queue.Queue()

        # Thread safety
        self._lock = threading.RLock()
        self._is_shutting_down = False
        self._restart_consuming = False

        # Register for recovery notifications if available
        if self._recovery_registry:
            self._recovery_registry(self.trigger_channel_recovery)

        # Initialize the channel and start consuming
        self._initialize_channel()

        logger.info("RabbitSubscriber initialized with channel recovery support")

    def _initialize_channel(self):
        """Initialize or reinitialize the channel and start consuming."""
        with self._lock:
            if self._is_shutting_down:
                return

            try:
                # Clean up existing channel if it exists
                self._cleanup_channel()

                # Get fresh connection and create new channel
                connection = self._connection_provider()
                self._channel = connection.channel()

                # Set QoS to ensure fair dispatching of messages
                self._channel.basic.qos(prefetch_count=1)

                # Declare queue
                logger.info("declaring queue with config: %s", self._queue_config)
                result = self._channel.queue.declare(
                    queue=self._queue_config.name or "",
                    durable=self._queue_config.durable,
                    exclusive=self._queue_config.exclusive,
                    auto_delete=self._queue_config.auto_delete,
                )

                # mutate config to store actual name
                self._queue_config.actual_queue_name = result.get("queue", self._queue_config.name)
                logger.info("Queue declared %s", self._queue_config.actual_queue_name)

                # Bind queue to exchanges
                for binding_config in self._binding_configs:
                    for routing_key in binding_config.routing_keys:
                        self._channel.queue.bind(
                            exchange=binding_config.exchange,
                            queue=self._queue_config.actual_queue_name,
                            routing_key=str(routing_key),
                        )
                        logger.info(
                            "Queue %s bound to exchange %s with routing key '%s'",
                            self._queue_config.actual_queue_name,
                            binding_config.exchange,
                            routing_key,
                        )

                # Start consuming
                self._consumer_tag = self._channel.basic.consume(
                    callback=self._message_handler,
                    queue=self._queue_config.actual_queue_name,
                )

                # Start or restart consuming thread
                self._start_consuming_thread()

                logger.info("Channel initialized successfully for queue %s", self._queue_config.actual_queue_name)

            except Exception as e:
                logger.exception("Failed to initialize channel: %s", e)
                # Schedule retry
                self._schedule_channel_retry()

    def _cleanup_channel(self):
        """Clean up existing channel and consumer thread."""
        if self._consumer_tag and self._channel and self._channel.is_open:
            try:
                self._channel.basic.cancel(self._consumer_tag)
                logger.debug("Consumer cancelled")
            except Exception as e:
                logger.debug("Error cancelling consumer: %s", e)

        if self._channel and self._channel.is_open:
            try:
                self._channel.stop_consuming()
                logger.debug("Stopped consuming")
            except Exception as e:
                logger.debug("Error stopping consuming: %s", e)

            try:
                self._channel.close()
                logger.debug("Channel closed")
            except Exception as e:
                logger.debug("Error closing channel: %s", e)

        self._channel = None
        self._consumer_tag = None

    def _start_consuming_thread(self):
        """Start the consuming thread with recovery support."""
        if self._consumer_thread and self._consumer_thread.is_alive():
            # Signal thread to restart
            self._restart_consuming = True
            return

        self._consumer_thread = threading.Thread(
            target=self._consuming_loop,
            name=f"rmq-subscriber-{self._queue_config.actual_queue_name}",
            daemon=True,
        )
        self._consumer_thread.start()

    def _consuming_loop(self):
        """Main consuming loop with automatic recovery."""
        while not self._is_shutting_down:
            try:
                with self._lock:
                    if self._is_shutting_down:
                        break

                    if not self._channel or not self._channel.is_open:
                        logger.warning("Channel is not available, attempting to recover")
                        self._initialize_channel()
                        continue

                # Start consuming - this will block until an error occurs or stop_consuming is called
                self._channel.start_consuming()

                # If we reach here, consuming stopped normally or due to an error
                if not self._is_shutting_down:
                    logger.warning("Consuming stopped unexpectedly, will retry")
                    time.sleep(1)  # Brief pause before retry

            except AMQPConnectionError as e:
                if not self._is_shutting_down:
                    logger.warning("Connection error in consuming loop, will recover: %s", e)
                    time.sleep(1)
            except Exception as e:
                if not self._is_shutting_down:
                    logger.exception("Unexpected error in consuming loop: %s", e)
                    time.sleep(1)

    def _schedule_channel_retry(self):
        """Schedule a channel initialization retry."""
        def retry_after_delay():
            time.sleep(5)  # Wait 5 seconds before retry
            if not self._is_shutting_down:
                logger.info("Retrying channel initialization")
                self._initialize_channel()

        retry_thread = threading.Thread(target=retry_after_delay, daemon=True)
        retry_thread.start()

    def trigger_channel_recovery(self):
        """
        Trigger channel recovery manually.
        This can be called when the connection is restored.
        """
        logger.info("Triggering channel recovery for subscriber")
        self._initialize_channel()

    def _message_handler(self, message: Message):
        """
        Write messages to internal queue for retrieval in `consume` method.
        """
        try:
            self._internal_message_queue.put(message.body)
            message.ack()
            logger.debug("Message received and acknowledged: %s", message.delivery_tag)
        except Exception as e:
            logger.exception("Error handling message: %s", e)
            # Don't ack the message if there's an error

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
                message_body = self._internal_message_queue.get(block=False)
                messages.append(message_body)
            except queue.Empty:
                break
        return messages

    def shutdown(self) -> None:
        """
        Shutdown the subscriber by closing the channel and stopping threads.
        """
        logger.info("Shutting down RabbitSubscriber...")

        with self._lock:
            self._is_shutting_down = True

        # Unregister from recovery notifications
        if self._recovery_unregistry:
            self._recovery_unregistry(self.trigger_channel_recovery)

        # Clean up channel and consumer
        self._cleanup_channel()

        # Wait for consuming thread to finish
        if self._consumer_thread and self._consumer_thread.is_alive():
            self._consumer_thread.join(timeout=5.0)

        logger.info("RabbitSubscriber shutdown complete")

    def __del__(self) -> None:
        """
        Destructor to ensure the subscriber is shut down when the object is deleted.
        """
        try:
            self.shutdown()
        except Exception:
            # Suppress exceptions during cleanup to avoid issues during interpreter shutdown
            pass
