"""
Tests for idle connection handling improvements.

This test validates that the RabbitMQ connection wrapper properly detects
and handles stale connections that can occur during idle periods.
"""

import unittest
from unittest.mock import Mock, patch

from amqpstorm import AMQPConnectionError

from manman.repository.rabbitmq.connection import RobustConnection


class TestIdleConnectionHandling(unittest.TestCase):
    """Test idle connection handling fixes."""

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
    def test_stale_connection_detected_during_get_connection(
        self, mock_connection_class
    ):
        """Test that stale connections are detected during get_connection()."""
        mock_connection = Mock()
        mock_connection.is_open = True
        mock_connection.check_for_errors = Mock()

        # Simulate stale connection: appears open but channel creation fails
        mock_connection.channel.side_effect = Exception("Connection stale")

        mock_connection_class.return_value = mock_connection

        robust_conn = RobustConnection(
            connection_params=self.connection_params,
            heartbeat_interval=30,
            max_reconnect_attempts=1,
            reconnect_delay=0.1,
        )

        # Should fail and trigger reconnection due to stale connection
        with self.assertRaises(AMQPConnectionError):
            robust_conn.get_connection()

        # Verify channel creation was attempted for validation
        mock_connection.channel.assert_called()

        robust_conn.close()

    @patch("manman.repository.rabbitmq.connection.Connection")
    def test_stale_connection_detected_during_is_connected(self, mock_connection_class):
        """Test that stale connections are detected during is_connected()."""
        mock_connection = Mock()
        mock_connection.is_open = True
        mock_connection.check_for_errors = Mock()

        # Simulate stale connection: appears open but channel creation fails
        mock_connection.channel.side_effect = Exception("Connection stale")

        mock_connection_class.return_value = mock_connection

        robust_conn = RobustConnection(
            connection_params=self.connection_params,
            heartbeat_interval=30,
        )

        # Should return False due to stale connection
        self.assertFalse(robust_conn.is_connected())

        robust_conn.close()

    @patch("manman.repository.rabbitmq.connection.Connection")
    def test_healthy_connection_validation_passes(self, mock_connection_class):
        """Test that healthy connections pass validation."""
        mock_connection = Mock()
        mock_connection.is_open = True
        mock_connection.check_for_errors = Mock()

        # Mock healthy channel
        mock_channel = Mock()
        mock_channel.is_open = True
        mock_channel.close = Mock()
        mock_connection.channel.return_value = mock_channel

        mock_connection_class.return_value = mock_connection

        robust_conn = RobustConnection(
            connection_params=self.connection_params,
            heartbeat_interval=30,
        )

        # Should work with healthy connection
        conn = robust_conn.get_connection()
        self.assertEqual(conn, mock_connection)

        # Should validate by creating and closing a channel
        mock_connection.channel.assert_called()
        mock_channel.close.assert_called()

        # is_connected should also return True
        self.assertTrue(robust_conn.is_connected())

        robust_conn.close()

    @patch("manman.repository.rabbitmq.connection.Connection")
    def test_non_open_channel_triggers_reconnection(self, mock_connection_class):
        """Test that channels that are not open trigger reconnection."""
        mock_connection = Mock()
        mock_connection.is_open = True
        mock_connection.check_for_errors = Mock()

        # Mock channel that's created but not open (indicates stale connection)
        mock_channel = Mock()
        mock_channel.is_open = False
        mock_connection.channel.return_value = mock_channel

        mock_connection_class.return_value = mock_connection

        robust_conn = RobustConnection(
            connection_params=self.connection_params,
            heartbeat_interval=30,
            max_reconnect_attempts=1,
            reconnect_delay=0.1,
        )

        # Should fail due to channel not being open
        with self.assertRaises(AMQPConnectionError):
            robust_conn.get_connection()

        # is_connected should also return False
        self.assertFalse(robust_conn.is_connected())

        robust_conn.close()


if __name__ == "__main__":
    unittest.main()
