import logging
import time
from datetime import datetime, timedelta, timezone

from amqpstorm import Connection

from manman.models import (
    StatusInfo,
    StatusType,
)
from manman.repository.database import DatabaseRepository
from manman.repository.rabbitmq import RabbitStatusPublisher, RabbitStatusSubscriber

logger = logging.getLogger(__name__)


class StatusEventProcessor:
    """
    Status Event Processor - consumes status messages from worker queues.

    This service subscribes to a generic status queue pattern and processes
    status updates from workers. Currently logs all received status information
    for debugging purposes.

    TODO - this module is a bit strange in that we ferry internal statuses to extenral to be logged
    whereas the true external statues are observed by the status processor and written before sendign to external queue
    ideally this is improved, but for now it works
    and external consumers should be able to subscribe to status.
    """

    def __init__(self, rabbitmq_connection: Connection):
        self._rabbitmq_connection = rabbitmq_connection
        self._is_running = False

        # Initialize database repository
        self._db_repository = DatabaseRepository()

        # Subscribe to status messages from both worker and server exchanges
        # Using the enhanced RabbitStatusSubscriber to consume from multiple exchanges
        self._internal_status_subscriber = RabbitStatusSubscriber(
            connection=self._rabbitmq_connection,
            exchanges_config={
                "worker": "status.worker-instance.*",
                "server": "status.game-server-instance.*",
            },
            queue_name="status-processor-internal-queue",
        )

        # Publisher for sending worker lost notifications
        # Use "worker" exchange for consistency with worker status messages

        # NOTE: consumers of this data should be using the external exchagne
        # and subscribe to the topics they want
        self._external_status_publisher = RabbitStatusPublisher(
            connection=self._rabbitmq_connection,
            exchange="external",
            routing_key_base="external.status",
        )

        self._external_status_consumer = RabbitStatusSubscriber(
            connection=self._rabbitmq_connection,
            exchange="external",
            routing_key="external.status.*.*",
            queue_name="status-processor-external-queue",
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
                self._process_internal_status_messages()

                # Check for stale worker heartbeats
                self._check_worker_heartbeats()

                # Process extenral status messages
                self._process_external_status_messages()

                # Small sleep to avoid busy waiting
                time.sleep(0.5)

        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            self._shutdown()

    # TODO - check for workers that are lost and have an end date so we can crash them

    def _check_worker_heartbeats(self):
        """
        Check for stale worker heartbeats and mark them as lost if necessary.
        This sends a notification to the external queue if a worker is marked as lost.
        """
        try:
            # Get workers with stale heartbeats using the database repository
            stale_workers = self._db_repository.get_workers_with_stale_heartbeats()

            for worker, current_status in stale_workers:
                logger.warning(
                    "Worker %s heartbeat is stale (last: %s), marking as LOST from %s",
                    worker.worker_id,
                    worker.last_heartbeat,
                    current_status,
                )

                # Send worker lost notification
                self._send_worker_lost_notification(worker.worker_id)

                # Get all active game server instances for this worker
                active_instances = self._db_repository.get_active_game_server_instances(
                    worker.worker_id
                )

                # Send lost notifications for all active game server instances
                for instance in active_instances:
                    logger.warning(
                        "Marking game server instance %s as LOST due to worker %s being lost",
                        instance.game_server_instance_id,
                        worker.worker_id,
                    )
                    self._send_game_server_lost_notification(
                        instance.game_server_instance_id
                    )

        except Exception as e:
            logger.exception("Error checking worker heartbeats: %s", e)

    def _send_worker_lost_notification(self, worker_id: int):
        """Send a worker lost notification to external queue"""
        try:
            # Create a status message indicating the worker is lost
            lost_status = StatusInfo(
                class_name="StatusEventProcessor",
                status_type=StatusType.LOST,
                as_of=datetime.now(timezone.utc),
                worker_id=worker_id,
            )

            self._external_status_publisher.publish_external(lost_status)
            self._db_repository.write_status_to_database(lost_status)
            logger.info("Worker lost notification sent for worker %s", worker_id)

        except Exception as e:
            logger.exception(
                "Error sending worker lost notification for worker %s: %s", worker_id, e
            )

    def _send_game_server_lost_notification(self, game_server_instance_id: int):
        """Send a game server lost notification to external queue"""
        try:
            # Create a status message indicating the game server instance is lost
            lost_status = StatusInfo(
                class_name="StatusEventProcessor",
                status_type=StatusType.LOST,
                as_of=datetime.now(timezone.utc),
                game_server_instance_id=game_server_instance_id,
            )

            self._external_status_publisher.publish_external(lost_status)
            self._db_repository.write_status_to_database(lost_status)
            logger.info(
                "Game server lost notification sent for instance %s",
                game_server_instance_id,
            )

        except Exception as e:
            logger.exception(
                "Error sending game server lost notification for instance %s: %s",
                game_server_instance_id,
                e,
            )

    def _process_internal_status_messages(self):
        """
        Process available status messages from the internal queue
        and route them to the external queue.

        This is not the best way to do this, but it's the way it's being done for now.
        """
        try:
            status_messages = self._internal_status_subscriber.get_status_messages()
            for status_message in status_messages:
                status_info = status_message.status_info
                logger.info(
                    "Status update received: class=%s, status=%s, timestamp=%s",
                    status_info.class_name,
                    status_info.status_type,
                    status_info.as_of,
                )
                self._external_status_publisher.publish_external(status_info)
                self._db_repository.write_status_to_database(status_info)
        except Exception as e:
            logger.exception("Error processing status messages: %s", e)

    def _process_external_status_messages(self):
        """Process available status messages from the external queue."""
        try:
            status_messages = self._external_status_consumer.get_status_messages()
            for status_message in status_messages:
                status_info = status_message.status_info
                logger.info(
                    "External status update received: class=%s, status=%s, timestamp=%s",
                    status_info.class_name,
                    status_info.status_type,
                    status_info.as_of,
                )
                # do not write to database here, just consume it as an example
                # should match DB
                logger.info("processing external status message %s", status_info)
        except Exception as e:
            logger.exception("Error processing external status messages: %s", e)

    def _shutdown(self):
        """Clean shutdown of the processor."""
        logger.info("Shutting down Status Event Processor")
        self._is_running = False

        if self._internal_status_subscriber:
            self._internal_status_subscriber.shutdown()
        if self._external_status_publisher:
            self._external_status_publisher.shutdown()
        if self._external_status_consumer:
            self._external_status_consumer.shutdown()

        logger.info("Status Event Processor shutdown complete")
