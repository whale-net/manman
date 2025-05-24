import logging
import time
from datetime import datetime, timedelta

from amqpstorm import Connection

logger = logging.getLogger(__name__)


class StatusEventProcessor:
    """
    Status Event Processor - minimal starting point for status processing.

    This service will be completely separate from how other server and worker
    services handle their status. Currently just runs an infinite loop as a
    foundation for future status processing logic.
    """

    def __init__(self, rabbitmq_connection: Connection):
        self._rabbitmq_connection = rabbitmq_connection
        self._is_running = False
        logger.info("Status Event Processor initialized")

    def run(self):
        """Main event processing loop - minimal implementation."""
        self._is_running = True
        loop_log_time = datetime.now()

        try:
            logger.info("Status Event Processor starting")
            while self._is_running:
                if datetime.now() - loop_log_time > timedelta(seconds=30):
                    logger.info("Status processor still running")
                    loop_log_time = datetime.now()

                # Minimal loop - no processing yet
                time.sleep(1.0)

        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            self._shutdown()

    def _shutdown(self):
        """Clean shutdown of the processor."""
        logger.info("Shutting down Status Event Processor")
        self._is_running = False
        logger.info("Status Event Processor shutdown complete")
