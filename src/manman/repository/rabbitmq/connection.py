"""
RabbitMQ connection wrapper with automatic reconnection capabilities.

This module provides a connection wrapper that handles connection drops
and automatic reconnection to prevent services from becoming unreachable.
"""

import logging
import threading
import time
from typing import Callable, List, Optional

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

        # Registry for subscribers that need to be notified of reconnection
        self._subscriber_callbacks: List[Callable] = []

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

                # Prepare connection parameters with fresh SSL context if needed
                connection_params = self._connection_params.copy()

                # Reset SSL context for each connection attempt to prevent SSL context reuse issues
                if connection_params.get("ssl") and connection_params.get(
                    "ssl_options"
                ):
                    ssl_options = connection_params["ssl_options"]
                    if isinstance(ssl_options, dict) and "context" in ssl_options:
                        # Create a fresh SSL context to avoid "bad record mac" errors during reconnection
                        import ssl

                        fresh_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                        fresh_context.load_default_certs(
                            purpose=ssl.Purpose.SERVER_AUTH
                        )

                        # Copy SSL options with fresh context
                        fresh_ssl_options = ssl_options.copy()
                        fresh_ssl_options["context"] = fresh_context
                        connection_params["ssl_options"] = fresh_ssl_options

                        logger.debug("Created fresh SSL context for connection attempt")

                logger.info(
                    "Establishing RabbitMQ connection with heartbeat=%s SSL=%s",
                    connection_params.get("heartbeat", 60),
                    connection_params.get("ssl", False),
                )
                self._connection = Connection(**connection_params)

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

            # Check if previous thread is still alive and wait for it to finish
            if self._reconnect_thread and self._reconnect_thread.is_alive():
                logger.debug("Previous reconnection thread still running, skipping")
                return

            self._is_reconnecting = True

        # Create and start thread outside the lock to prevent potential deadlock
        try:
            self._reconnect_thread = threading.Thread(
                target=self._reconnect_loop, name="rmq-reconnect-thread", daemon=True
            )
            self._reconnect_thread.start()
            logger.debug("Reconnection thread started")
        except Exception as e:
            logger.exception("Failed to start reconnection thread: %s", e)
            with self._lock:
                self._is_reconnecting = False

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

                    # Notify all registered subscribers to recover their channels
                    self._notify_subscribers_of_recovery()

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

    def register_subscriber_callback(self, callback: Callable) -> None:
        """
        Register a callback to be called when connection is restored.

        :param callback: Function to call when connection is restored
        """
        with self._lock:
            if callback not in self._subscriber_callbacks:
                self._subscriber_callbacks.append(callback)
                logger.debug("Registered subscriber callback")

    def unregister_subscriber_callback(self, callback: Callable) -> None:
        """
        Unregister a subscriber callback.

        :param callback: Function to remove from callbacks
        """
        with self._lock:
            if callback in self._subscriber_callbacks:
                self._subscriber_callbacks.remove(callback)
                logger.debug("Unregistered subscriber callback")

    def _notify_subscribers_of_recovery(self) -> None:
        """Notify all registered subscribers that connection has been restored."""
        with self._lock:
            callbacks = self._subscriber_callbacks.copy()

        for callback in callbacks:
            try:
                callback()
            except Exception as e:
                logger.exception("Error notifying subscriber of recovery: %s", e)

    def get_connection(self) -> Connection:
        """
        Get the current connection, ensuring it's healthy.

        :return: Active connection
        :raises AMQPConnectionError: If connection is not available
        """
        needs_reconnect = False
        connection = None

        with self._lock:
            if not self._connection:
                raise AMQPConnectionError("No connection available")

            # Check if connection is healthy
            try:
                if not self._connection.is_open:
                    logger.warning("Connection is not open, attempting to reconnect")
                    needs_reconnect = True
                else:
                    # Additional health check
                    self._connection.check_for_errors()
                    connection = self._connection

            except AMQPConnectionError:
                logger.warning("Connection health check failed, starting reconnection")
                needs_reconnect = True
            except Exception as e:
                logger.exception(
                    "Unexpected error during connection health check: %s", e
                )
                needs_reconnect = True

        # Start reconnection outside the lock to avoid deadlock
        if needs_reconnect:
            self._start_reconnect_thread()
            if connection is None:
                raise AMQPConnectionError("Connection is not available")

        if connection is None:
            raise AMQPConnectionError("Connection health check failed")

        return connection

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
