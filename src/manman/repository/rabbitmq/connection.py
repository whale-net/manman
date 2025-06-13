"""
RabbitMQ connection wrapper with automatic reconnection capabilities.

This module provides a connection wrapper that handles connection drops
and automatic reconnection to prevent services from becoming unreachable.
"""

import logging
import threading
import time
from typing import Callable, Optional

from amqpstorm import AMQPConnectionError, Connection

logger = logging.getLogger(__name__)


class RobustConnection:
    """
    A robust connection wrapper that handles connection drops and automatic reconnection.

    This wrapper monitors the connection health and automatically reconnects when
    the connection is lost, preventing services from becoming unreachable.
    """

    def __init__(
        self,
        connection_params: dict,
        heartbeat_interval: int = 30,
        max_reconnect_attempts: int = 5,
        reconnect_delay: float = 1.0,
        on_connection_lost: Optional[Callable] = None,
        on_connection_restored: Optional[Callable] = None,
    ):
        """
        Initialize the robust connection wrapper.

        :param connection_params: Connection parameters for AMQPStorm
        :param heartbeat_interval: AMQP heartbeat interval in seconds
        :param max_reconnect_attempts: Maximum number of reconnection attempts
        :param reconnect_delay: Delay between reconnection attempts in seconds
        :param on_connection_lost: Optional callback when connection is lost
        :param on_connection_restored: Optional callback when connection is restored
        :raises AMQPConnectionError: If initial connection fails
        """
        self._connection_params = connection_params.copy()
        self._connection_params["heartbeat"] = heartbeat_interval
        self._max_reconnect_attempts = max_reconnect_attempts
        self._reconnect_delay = reconnect_delay
        self._on_connection_lost = on_connection_lost
        self._on_connection_restored = on_connection_restored

        self._connection: Optional[Connection] = None
        self._lock = threading.RLock()
        self._reconnect_thread: Optional[threading.Thread] = None
        self._is_reconnecting = False
        self._should_stop = False

        # Initial connection - should fail fast if connection cannot be established
        if not self._connect():
            raise AMQPConnectionError("Failed to establish initial RabbitMQ connection")

    def _connect(self) -> bool:
        """
        Establish the initial connection.

        :return: True if connection was successful, False otherwise
        """
        try:
            with self._lock:
                if self._connection and self._connection.is_open:
                    return True

                logger.info(
                    "Establishing RabbitMQ connection with heartbeat=%s",
                    self._connection_params.get("heartbeat", 60),
                )
                self._connection = Connection(**self._connection_params)

                if self._connection.is_open:
                    logger.info("RabbitMQ connection established successfully")
                    return True
                else:
                    logger.error("Failed to establish RabbitMQ connection")
                    return False

        except Exception as e:
            logger.exception("Error establishing RabbitMQ connection: %s", e)
            self._connection = None
            return False

    def _start_reconnect_thread(self):
        """Start the reconnection thread if not already running."""
        with self._lock:
            if self._is_reconnecting or self._should_stop:
                return

            self._is_reconnecting = True
            self._reconnect_thread = threading.Thread(
                target=self._reconnect_loop, name="rmq-reconnect-thread", daemon=True
            )
            self._reconnect_thread.start()

    def _reconnect_loop(self):
        """Main reconnection loop."""
        logger.warning("Connection lost, starting reconnection process")

        if self._on_connection_lost:
            try:
                self._on_connection_lost()
            except Exception as e:
                logger.exception("Error in connection lost callback: %s", e)

        attempt = 0
        current_delay = self._reconnect_delay
        while attempt < self._max_reconnect_attempts and not self._should_stop:
            attempt += 1
            logger.info(
                "Reconnection attempt %d/%d", attempt, self._max_reconnect_attempts
            )

            try:
                if self._connect():
                    logger.info("Reconnection successful after %d attempts", attempt)

                    if self._on_connection_restored:
                        try:
                            self._on_connection_restored()
                        except Exception as e:
                            logger.exception(
                                "Error in connection restored callback: %s", e
                            )

                    with self._lock:
                        self._is_reconnecting = False
                    return

            except Exception as e:
                logger.exception("Reconnection attempt %d failed: %s", attempt, e)

            if attempt < self._max_reconnect_attempts and not self._should_stop:
                time.sleep(current_delay)
                # Exponential backoff with jitter
                current_delay = min(current_delay * 1.5, 30.0)

        logger.error(
            "Failed to reconnect after %d attempts", self._max_reconnect_attempts
        )
        with self._lock:
            self._is_reconnecting = False

    def get_connection(self) -> Connection:
        """
        Get the current connection, ensuring it's healthy.

        :return: Active connection
        :raises AMQPConnectionError: If connection is not available
        """
        with self._lock:
            if not self._connection:
                raise AMQPConnectionError("No connection available")

            # Check if connection is healthy
            try:
                if not self._connection.is_open:
                    logger.warning("Connection is not open, attempting to reconnect")
                    self._start_reconnect_thread()
                    raise AMQPConnectionError("Connection is not open")

                # Additional health check
                self._connection.check_for_errors()

                return self._connection

            except AMQPConnectionError:
                logger.warning("Connection health check failed, starting reconnection")
                self._start_reconnect_thread()
                raise
            except Exception as e:
                logger.exception(
                    "Unexpected error during connection health check: %s", e
                )
                self._start_reconnect_thread()
                raise AMQPConnectionError(f"Connection health check failed: {e}")

    def is_connected(self) -> bool:
        """
        Check if the connection is currently healthy.

        :return: True if connection is healthy, False otherwise
        """
        try:
            with self._lock:
                if not self._connection:
                    return False

                if not self._connection.is_open:
                    return False

                self._connection.check_for_errors()
                return True

        except Exception:
            return False

    def close(self):
        """Close the connection and stop reconnection attempts."""
        logger.info("Closing robust connection")

        with self._lock:
            self._should_stop = True

            if self._connection and self._connection.is_open:
                try:
                    self._connection.close()
                except Exception as e:
                    logger.exception("Error closing connection: %s", e)

            self._connection = None

        # Wait for reconnection thread to finish
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            self._reconnect_thread.join(timeout=5.0)

        logger.info("Robust connection closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
