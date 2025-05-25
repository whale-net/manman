import logging
import time
from datetime import datetime, timedelta

from amqpstorm import Connection
from sqlmodel import select

from manman.models import StatusInfo, StatusInfoBase, StatusType, Worker
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
            routing_key="worker-instance.*.status",  # Wildcard pattern for all workers
            queue_name="status-processor-queue",  # Our own queue name
        )

        # Publisher for sending worker lost notifications
        # Use "worker" exchange for consistency with worker status messages
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
                time.sleep(0.1)

        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            self._shutdown()

    def _process_status_messages(self):
        """Process available status messages from the queue."""
        try:
            status_messages = self._status_subscriber.get_status_messages()
            for status_message in status_messages:
                self._handle_status_message(
                    status_message.status_info, status_message.routing_key
                )
        except Exception as e:
            logger.exception("Error processing status messages: %s", e)

    def _handle_status_message(self, status_info: StatusInfoBase, routing_key: str):
        """Handle a single status message - logs it and writes to database."""
        logger.info(
            "Status update received: class=%s, status=%s, timestamp=%s, routing_key=%s",
            status_info.class_name,
            status_info.status_type.value,
            status_info.as_of,
            routing_key,
        )

        # For now, keep the print for debugging
        print(
            f"[STATUS] {status_info.class_name}: {status_info.status_type.value} at {status_info.as_of} (routing_key: {routing_key})"
        )

        # Write to database
        self._write_status_to_database(status_info, routing_key)

    def _write_status_to_database(self, status_info: StatusInfoBase, routing_key: str):
        """Write status message to the database."""
        try:
            # Extract worker_id from routing key
            # Expected format: worker-instance.{worker_id}.status
            worker_id = None
            if routing_key.startswith("worker-instance.") and routing_key.endswith(
                ".status"
            ):
                parts = routing_key.split(".")
                if len(parts) == 3:
                    try:
                        worker_id = int(parts[1])  # Convert to integer
                    except ValueError:
                        logger.warning(
                            "Invalid worker_id in routing key: %s", routing_key
                        )
                        return

            if not worker_id:
                logger.warning(
                    "Could not extract worker_id from routing key: %s", routing_key
                )
                return

            # Create StatusInfo object for database
            status_record = StatusInfo(
                worker_id=worker_id,
                game_server_instance_id=None,  # For now, only handling worker status
                class_name=status_info.class_name,
                status_type=status_info.status_type,
                as_of=status_info.as_of,
            )

            # Write to database
            with get_sqlalchemy_session() as session:
                session.add(status_record)
                session.commit()
                logger.debug(
                    "Status written to database: worker_id=%s, class=%s",
                    worker_id,
                    status_info.class_name,
                )

        except Exception as e:
            logger.exception("Error writing status to database: %s", e)

    def _check_worker_heartbeats(self):
        """Check for stale worker heartbeats and send worker lost notifications."""
        try:
            current_time = datetime.utcnow()
            heartbeat_threshold = current_time - timedelta(seconds=5)

            with get_sqlalchemy_session() as session:
                # Find active workers with stale heartbeats
                stale_workers = session.exec(
                    select(Worker).where(
                        Worker.last_heartbeat < heartbeat_threshold,
                        Worker.end_date.is_(None),  # Only check active workers
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
                        class_name="StatusEventProcessor",
                        status_type=StatusType.LOST,
                        as_of=current_time,
                    )
                    session.add(status_record)

                    # Send worker lost notification
                    self._send_worker_lost_notification(worker.worker_id)

                session.commit()

        except Exception as e:
            logger.exception("Error checking worker heartbeats: %s", e)

    def _send_worker_lost_notification(self, worker_id: int):
        """Send a worker lost notification via RabbitMQ."""
        try:
            # Create a status message indicating the worker is lost
            lost_status = StatusInfoBase(
                class_name="StatusEventProcessor",
                status_type=StatusType.LOST,
                as_of=datetime.utcnow(),
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
