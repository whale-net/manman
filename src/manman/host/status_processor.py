import logging
import time
from datetime import datetime, timedelta

from amqpstorm import Connection

from manman.models import Command, CommandType
from manman.repository.rabbit import RabbitMessageProvider

logger = logging.getLogger(__name__)


class StatusEventProcessor:
    """
    Status Event Processor - handles pub/sub status events.

    This service is responsible for:
    - Processing worker heartbeats
    - Handling server lifecycle events
    - Updating status information in database
    - Generating alerts/notifications
    - Maintaining status metrics
    """

    RMQ_EXCHANGE = "status"

    def __init__(self, rabbitmq_connection: Connection):
        self._rabbitmq_connection = rabbitmq_connection
        self._is_running = False

        # Set up message provider for status events
        self._message_provider = RabbitMessageProvider(
            connection=self._rabbitmq_connection,
            exchange=self.RMQ_EXCHANGE,
            queue_name="status.processor",
        )

        logger.info("Status Event Processor initialized")

    def run(self):
        """Main event processing loop."""
        self._is_running = True
        loop_log_time = datetime.now()

        try:
            logger.info("Status Event Processor starting")
            while self._is_running:
                if datetime.now() - loop_log_time > timedelta(seconds=30):
                    logger.info("Status processor still running")
                    loop_log_time = datetime.now()

                # Process incoming status events
                self._process_status_events()

                # Add periodic status checks here if needed
                self._check_worker_health()

                # No need to spin too fast
                time.sleep(1.0)

        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            self._shutdown()

    def _process_status_events(self):
        """Process incoming status-related messages."""
        commands = self._message_provider.get_commands()

        if commands:
            for command in commands:
                logger.info("Processing status event: %s", command)

                if command.command_type == CommandType.HEARTBEAT:
                    self._handle_heartbeat_event(command)
                elif command.command_type == CommandType.SERVER_STARTED:
                    self._handle_server_started_event(command)
                elif command.command_type == CommandType.SERVER_STOPPED:
                    self._handle_server_stopped_event(command)
                else:
                    logger.warning(
                        "Unknown status event type: %s", command.command_type
                    )

    def _handle_heartbeat_event(self, command: Command):
        """Handle worker heartbeat events."""
        # TODO: Extract worker_id from command and update last_seen timestamp
        logger.info("Processing heartbeat event: %s", command)

        # Example implementation:
        # with get_sqlalchemy_session() as session:
        #     worker_id = int(command.command_args[0])
        #     # Update worker last_heartbeat timestamp
        #     pass

    def _handle_server_started_event(self, command: Command):
        """Handle server started events."""
        logger.info("Processing server started event: %s", command)

        # TODO: Update server instance status in database
        # Could also trigger notifications, metrics updates, etc.

    def _handle_server_stopped_event(self, command: Command):
        """Handle server stopped events."""
        logger.info("Processing server stopped event: %s", command)

        # TODO: Update server instance status in database
        # Could also trigger cleanup, notifications, etc.

    def _check_worker_health(self):
        """Periodically check worker health and mark stale workers as offline."""
        # TODO: Query database for workers that haven't sent heartbeats recently
        # Mark them as offline/unhealthy
        pass

    def _shutdown(self):
        """Clean shutdown of the processor."""
        logger.info("Shutting down Status Event Processor")
        self._is_running = False

        if self._message_provider:
            self._message_provider.shutdown()

        logger.info("Status Event Processor shutdown complete")
