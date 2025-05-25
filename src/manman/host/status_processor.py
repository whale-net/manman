import logging
import time
from datetime import datetime, timedelta, timezone

from amqpstorm import Connection
from sqlmodel import not_, select

from manman.models import (
    ACTIVE_STATUS_TYPES,
    OBSERVED_STATUS_TYPES,
    StatusInfo,
    StatusType,
    Worker,
)
from manman.repository.rabbitmq import RabbitStatusPublisher, RabbitStatusSubscriber
from manman.util import get_sqlalchemy_session

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
        self._internal_status_subscriber = RabbitStatusSubscriber(
            connection=self._rabbitmq_connection,
            exchange="worker",  # Same exchange that workers publish to
            # TODO - reference worker class or something for this
            routing_key="status.worker-instance.*",
            # our queue name
            queue_name="status-processor-queue",
        )

        # Publisher for sending worker lost notifications
        # Use "worker" exchange for consistency with worker status messages

        # NOTE: consumers of this data should be using the external exchagne
        # and subscribe to the topics they want
        self._external_status_publisher = RabbitStatusPublisher(
            connection=self._rabbitmq_connection,
            exchange="external",
            routing_key_base="status",
        )

        self._external_status_consumer = RabbitStatusSubscriber(
            connection=self._rabbitmq_connection,
            exchange="external",
            routing_key="status.*.*",
            queue_name="status-processor-queue-external",
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

    def _check_worker_heartbeats(self):
        """
        Check for stale worker heartbeats and mark them as lost if necessary.
        This sends a notification to the external queue if a worker is marked as lost.
        """
        try:
            current_time = datetime.now(timezone.utc)
            heartbeat_threshold = current_time - timedelta(seconds=5)
            heartbeat_max_lookback = current_time - timedelta(hours=1)

            with get_sqlalchemy_session() as session:
                inner = select(StatusInfo).alias("i")
                last_status = (
                    select(StatusInfo).where(
                        not_(StatusInfo.worker_id.is_(None)),
                        not_(
                            select(inner)
                            .where(
                                inner.c.worker_id == StatusInfo.worker_id,
                                inner.c.as_of > StatusInfo.as_of,
                            )
                            .exists()
                        ),
                    )
                ).subquery()

                candidate_workers = (
                    select(Worker, last_status.c.status_type)
                    .join(last_status)
                    .where(
                        Worker.last_heartbeat > heartbeat_max_lookback,
                        Worker.last_heartbeat < heartbeat_threshold,
                        Worker.end_date.is_(None),
                        last_status.c.status_type.in_(ACTIVE_STATUS_TYPES),
                    )
                )

                stale_workers = session.exec(candidate_workers).all()
                for worker, current_status in stale_workers:
                    logger.warning(
                        "Worker %s heartbeat is stale (last: %s, threshold: %s), marking as LOST from %s",
                        worker.worker_id,
                        worker.last_heartbeat,
                        heartbeat_threshold,
                        current_status,
                    )

                    # Send worker lost notification
                    self._send_worker_lost_notification(worker.worker_id)

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
            self._write_status_to_database(lost_status)
            logger.info("Worker lost notification sent for worker %s", worker_id)

        except Exception as e:
            logger.exception(
                "Error sending worker lost notification for worker %s: %s", worker_id, e
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
                if status_info.status_type in OBSERVED_STATUS_TYPES:
                    # If the status is in OBSERVED_STATUS_TYPES, we don't want to write it to the database
                    # as it is already being handled by the status processor and written when processed
                    continue
                else:
                    self._write_status_to_database(status_info)
        except Exception as e:
            logger.exception("Error processing external status messages: %s", e)

    def _write_status_to_database(self, status_info: StatusInfo):
        """Write status message to the database."""
        try:
            # Write to database
            with get_sqlalchemy_session() as session:
                session.add(status_info)
                session.commit()
                logger.debug(
                    "Status written to database: %s, %s, %s",
                    status_info.class_name,
                    status_info.status_type.value,
                    status_info.as_of,
                )

        except Exception as e:
            logger.exception("Error writing status to database: %s", e)

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
