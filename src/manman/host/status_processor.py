import logging
import time
from datetime import datetime, timedelta

from amqpstorm import Connection

from manman.models import StatusInfoBase
from manman.repository.rabbitmq import RabbitStatusSubscriber

logger = logging.getLogger(__name__)


class StatusEventProcessor:
    """
    Status Event Processor - consumes status messages from worker queues.

    This service subscribes to a generic status queue pattern and processes
    status updates from workers. Currently logs all received status information
    for debugging purposes.
    """

    def __init__(self, rabbitmq_connection: Connection):
        self._rabbitmq_connection = rabbitmq_connection
        self._is_running = False

        # Subscribe to status messages from the worker exchange
        # Using a wildcard pattern to consume all worker status messages
        self._status_subscriber = RabbitStatusSubscriber(
            connection=self._rabbitmq_connection,
            exchange="worker",  # Same exchange that workers publish to
            routing_key="worker-instance.*.status",  # Wildcard pattern for all workers
            queue_name="status-processor-queue",  # Our own queue name
        )

        logger.info("Status Event Processor initialized")

    def run(self):
        """Main event processing loop - consumes and processes status messages."""
        self._is_running = True
        loop_log_time = datetime.now()

        try:
            logger.info("Status Event Processor starting")
            while self._is_running:
                if datetime.now() - loop_log_time > timedelta(seconds=30):
                    logger.info("Status processor still running")
                    loop_log_time = datetime.now()

                # Process any available status messages
                self._process_status_messages()

                # Small sleep to avoid busy waiting
                time.sleep(0.1)

        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            self._shutdown()

    def _process_status_messages(self):
        """Process available status messages from the queue."""
        try:
            status_messages = self._status_subscriber.get_status_messages()
            for status_info in status_messages:
                self._handle_status_message(status_info)
        except Exception as e:
            logger.exception("Error processing status messages: %s", e)

    def _handle_status_message(self, status_info: StatusInfoBase):
        """Handle a single status message - currently just logs it."""
        logger.info(
            "Status update received: class=%s, status=%s, timestamp=%s",
            status_info.class_name,
            status_info.status_type.value,
            status_info.as_of,
        )

        # For now, just print the information for debugging
        print(
            f"[STATUS] {status_info.class_name}: {status_info.status_type.value} at {status_info.as_of}"
        )

        # TODO: Future enhancements:
        # - Update database with status information
        # - Trigger alerts for critical status changes
        # - Maintain metrics and aggregations
        # - Send notifications to external systems

    def _shutdown(self):
        """Clean shutdown of the processor."""
        logger.info("Shutting down Status Event Processor")
        self._is_running = False

        if self._status_subscriber:
            self._status_subscriber.shutdown()

        logger.info("Status Event Processor shutdown complete")
