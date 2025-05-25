import logging
import time
from datetime import datetime, timedelta, timezone

from amqpstorm import Connection
from sqlmodel import select

from manman.models import (
    ACTIVE_STATUS_TYPES,
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
        self._status_subscriber = RabbitStatusSubscriber(
            connection=self._rabbitmq_connection,
            exchange="worker",  # Same exchange that workers publish to
            # TODO - reference worker class or something for this
            routing_key="worker-instance.*.status",
            # our queue name
            queue_name="status-processor-queue",
        )

        # Publisher for sending worker lost notifications
        # Use "worker" exchange for consistency with worker status messages

        # TODO 5/25 - use different status pblisher for sending worker lost notifications
        # this should send StatusNotification messages which include worker or instnace id
        self._status_publisher = RabbitStatusPublisher(
            connection=self._rabbitmq_connection,
            exchange="worker",
            routing_key="status-processor.notifications",
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

                # Check for stale worker heartbeats
                self._check_worker_heartbeats()

                # Small sleep to avoid busy waiting
                time.sleep(0.5)

        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            self._shutdown()

    def _process_status_messages(self):
        """Process available status messages from the queue."""
        try:
            status_messages = self._status_subscriber.get_status_messages()
            for status_message in status_messages:
                print(status_message.status_info)
                print(status_message.status_info.status_type)
                self._handle_status_message(
                    status_message.status_info,
                )
        except Exception as e:
            logger.exception("Error processing status messages: %s", e)

    def _handle_status_message(self, status_info: StatusInfo):
        """Handle a single status message - logs it and writes to database."""
        logger.info(
            "Status update received: class=%s, status=%s, timestamp=%s",
            status_info.class_name,
            status_info.status_type,
            status_info.as_of,
        )

        # For now, keep the print for debugging
        print(
            f"[STATUS] {status_info.class_name}: {status_info.status_type.value} at {status_info.as_of}"
        )

        # Write to database
        self._write_status_to_database(status_info)

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

    def _check_worker_heartbeats(self):
        """Check for stale worker heartbeats and send worker lost notifications."""
        try:
            current_time = datetime.now(timezone.utc)
            heartbeat_threshold = current_time - timedelta(seconds=5)

            with get_sqlalchemy_session() as session:
                # Common Table Expression to get the latest status for each worker
                from sqlalchemy import and_, func

                # CTE to get the latest status timestamp for each worker
                latest_status_cte = (
                    select(
                        StatusInfo.worker_id,
                        func.max(StatusInfo.as_of).label("latest_as_of"),
                    )
                    .where(StatusInfo.worker_id.is_not(None))
                    .group_by(StatusInfo.worker_id)
                ).cte("latest_status_times")

                # Join back to get the actual status records for the latest timestamps
                latest_status_subquery = (
                    select(
                        StatusInfo.worker_id, StatusInfo.status_type, StatusInfo.as_of
                    )
                    .join(
                        latest_status_cte,
                        and_(
                            StatusInfo.worker_id == latest_status_cte.c.worker_id,
                            StatusInfo.as_of == latest_status_cte.c.latest_as_of,
                        ),
                    )
                    .where(StatusInfo.worker_id.is_not(None))
                ).subquery()

                # Find workers with stale heartbeats that are currently in an active status
                stale_workers = session.exec(
                    select(Worker)
                    .join(
                        latest_status_subquery,
                        Worker.worker_id == latest_status_subquery.c.worker_id,
                    )
                    .where(
                        Worker.last_heartbeat < heartbeat_threshold,
                        # Only check active workers
                        Worker.end_date.is_(None),
                        # who have active status types.
                        # If it's completed, or lost/crashed we don't care about it
                        latest_status_subquery.c.status_type.in_(ACTIVE_STATUS_TYPES),
                    )
                ).all()

                for worker in stale_workers:
                    logger.warning(
                        "Worker %s heartbeat is stale (last: %s, threshold: %s), marking as LOST",
                        worker.worker_id,
                        worker.last_heartbeat,
                        heartbeat_threshold,
                    )

                    # Create status record for tracking the lost worker
                    status_record = StatusInfo(
                        worker_id=worker.worker_id,
                        game_server_instance_id=None,
                        # this is currently status_event_processor, but should probably be the
                        # worker class name. For now, going to keep this as-is, because this may end up
                        # working better for us in the long run
                        class_name="StatusEventProcessor",
                        status_type=StatusType.LOST,
                        as_of=current_time,
                    )
                    # write asap, do not batch. unsure if good idea but it's how
                    # it's being done for now
                    self._write_status_to_database(status_record)

                    # Send worker lost notification
                    self._send_worker_lost_notification(worker.worker_id)

        except Exception as e:
            logger.exception("Error checking worker heartbeats: %s", e)

    def _send_worker_lost_notification(self, worker_id: int):
        """Send a worker lost notification via RabbitMQ."""
        try:
            # Create a status message indicating the worker is lost
            lost_status = StatusInfo(
                class_name="StatusEventProcessor",
                status_type=StatusType.LOST,
                as_of=datetime.now(timezone.utc),
                worker_id=worker_id,
            )

            # Publish the worker lost status message to the status exchange
            # This will be picked up by any system monitoring worker status
            self._status_publisher.publish(lost_status)

            logger.info("Worker lost notification sent for worker %s", worker_id)

        except Exception as e:
            logger.exception(
                "Error sending worker lost notification for worker %s: %s", worker_id, e
            )

    def _shutdown(self):
        """Clean shutdown of the processor."""
        logger.info("Shutting down Status Event Processor")
        self._is_running = False

        if self._status_subscriber:
            self._status_subscriber.shutdown()

        logger.info("Status Event Processor shutdown complete")
