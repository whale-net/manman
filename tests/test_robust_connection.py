"""
Tests for RabbitMQ robust connection handling.
"""

import threading
import time
import unittest
from unittest.mock import Mock, patch

from amqpstorm import AMQPConnectionError

from manman.repository.rabbitmq.connection import RobustConnection


class TestRobustConnection(unittest.TestCase):
    """Test RabbitMQ robust connection functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.connection_params = {
            "hostname": "localhost",
            "port": 5672,
            "username": "guest",
            "password": "guest",
            "virtual_host": "/",
        }

    @patch("manman.repository.rabbitmq.connection.Connection")
    def test_initial_connection_success(self, mock_connection_class):
        """Test successful initial connection."""
        mock_connection = Mock()
        mock_connection.is_open = True
        mock_connection_class.return_value = mock_connection

        robust_conn = RobustConnection(
            connection_params=self.connection_params, heartbeat_interval=10
        )

        # Should establish connection with heartbeat
        mock_connection_class.assert_called_once()
        call_args = mock_connection_class.call_args
        self.assertEqual(call_args[1]["heartbeat"], 10)
        self.assertEqual(call_args[1]["hostname"], "localhost")

        # Should return the connection
        conn = robust_conn.get_connection()
        self.assertEqual(conn, mock_connection)

        robust_conn.close()

    @patch("manman.repository.rabbitmq.connection.Connection")
    def test_initial_connection_failure(self, mock_connection_class):
        """Test handling of initial connection failure."""
        mock_connection_class.side_effect = AMQPConnectionError("Connection failed")

        with self.assertRaises(Exception):
            # Should fail during initialization
            RobustConnection(
                connection_params=self.connection_params, heartbeat_interval=10
            )

    @patch("manman.repository.rabbitmq.connection.Connection")
    def test_connection_health_check(self, mock_connection_class):
        """Test connection health checking."""
        mock_connection = Mock()
        mock_connection.is_open = True
        mock_connection.check_for_errors = Mock()
        mock_connection_class.return_value = mock_connection

        robust_conn = RobustConnection(
            connection_params=self.connection_params, heartbeat_interval=10
        )

        # Should perform health check
        robust_conn.get_connection()
        mock_connection.check_for_errors.assert_called_once()

        robust_conn.close()

    @patch("manman.repository.rabbitmq.connection.Connection")
    def test_connection_lost_detection(self, mock_connection_class):
        """Test detection of lost connection."""
        mock_connection = Mock()
        mock_connection.is_open = True  # Start with open connection
        mock_connection.check_for_errors = Mock()
        mock_connection_class.return_value = mock_connection

        robust_conn = RobustConnection(
            connection_params=self.connection_params,
            heartbeat_interval=10,
            max_reconnect_attempts=1,
        )

        # Now simulate connection loss
        mock_connection.is_open = False  # Connection becomes closed

        # Should detect connection is not open and raise error
        with self.assertRaises(AMQPConnectionError):
            robust_conn.get_connection()

        robust_conn.close()

    @patch("manman.repository.rabbitmq.connection.Connection")
    def test_reconnection_callbacks(self, mock_connection_class):
        """Test reconnection callbacks are called."""
        mock_connection = Mock()
        mock_connection.is_open = True
        mock_connection_class.return_value = mock_connection

        connection_lost_called = threading.Event()
        connection_restored_called = threading.Event()

        def on_lost():
            connection_lost_called.set()

        def on_restored():
            connection_restored_called.set()

        robust_conn = RobustConnection(
            connection_params=self.connection_params,
            heartbeat_interval=10,
            max_reconnect_attempts=1,
            reconnect_delay=0.1,
            on_connection_lost=on_lost,
            on_connection_restored=on_restored,
        )

        # Simulate connection failure
        mock_connection.is_open = False
        mock_connection.check_for_errors.side_effect = AMQPConnectionError(
            "Connection lost"
        )

        # Try to get connection, should trigger reconnection
        with self.assertRaises(AMQPConnectionError):
            robust_conn.get_connection()

        # Wait for callbacks to be called
        self.assertTrue(connection_lost_called.wait(timeout=1.0))

        # Simulate successful reconnection
        mock_connection.is_open = True
        mock_connection.check_for_errors.side_effect = None

        # This should work after reconnection
        time.sleep(0.2)  # Give reconnection thread time

        robust_conn.close()

    @patch("manman.repository.rabbitmq.connection.Connection")
    def test_is_connected_method(self, mock_connection_class):
        """Test is_connected method."""
        mock_connection = Mock()
        mock_connection.is_open = True
        mock_connection.check_for_errors = Mock()
        mock_connection_class.return_value = mock_connection

        robust_conn = RobustConnection(
            connection_params=self.connection_params, heartbeat_interval=10
        )

        # Should return True for healthy connection
        self.assertTrue(robust_conn.is_connected())

        # Should return False for unhealthy connection
        mock_connection.is_open = False
        self.assertFalse(robust_conn.is_connected())

        robust_conn.close()

    @patch("manman.repository.rabbitmq.connection.Connection")
    def test_connection_close(self, mock_connection_class):
        """Test proper connection closing."""
        mock_connection = Mock()
        mock_connection.is_open = True
        mock_connection.close = Mock()
        mock_connection_class.return_value = mock_connection

        robust_conn = RobustConnection(
            connection_params=self.connection_params, heartbeat_interval=10
        )

        robust_conn.close()

        # Should close the underlying connection
        mock_connection.close.assert_called_once()

    @patch("manman.repository.rabbitmq.connection.Connection")
    def test_context_manager(self, mock_connection_class):
        """Test context manager functionality."""
        mock_connection = Mock()
        mock_connection.is_open = True
        mock_connection.close = Mock()
        mock_connection_class.return_value = mock_connection

        with RobustConnection(
            connection_params=self.connection_params, heartbeat_interval=10
        ) as robust_conn:
            self.assertIsNotNone(robust_conn)

        # Should close connection when exiting context
        mock_connection.close.assert_called_once()
