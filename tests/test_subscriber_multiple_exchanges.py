"""
Test RabbitStatusSubscriber multiple exchanges functionality.

This module tests the enhanced RabbitStatusSubscriber that supports
consuming from multiple exchanges with different routing keys.
"""

import unittest
from unittest.mock import Mock, call, patch

from manman.models import StatusInfo, StatusType
from manman.repository.rabbitmq.base import StatusMessage
from manman.repository.rabbitmq.subscriber import RabbitStatusSubscriber


class TestRabbitStatusSubscriberMultipleExchanges(unittest.TestCase):
    """Test cases for RabbitStatusSubscriber with multiple exchanges."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_connection = Mock()
        self.mock_channel = Mock()
        self.mock_connection.channel.return_value = self.mock_channel

        # Mock queue declaration response
        self.mock_channel.queue.declare.return_value = {"queue": "test-queue-123"}
        self.mock_channel.basic.consume.return_value = "consumer-tag-123"

    @patch("manman.repository.rabbitmq.subscriber.threading.Thread")
    def test_single_exchange_legacy_compatibility(self, mock_thread):
        """Test that single exchange parameters still work (backward compatibility)."""
        # Arrange
        exchange = "worker-status"
        routing_key = "worker.*"

        # Act
        subscriber = RabbitStatusSubscriber(
            connection=self.mock_connection,
            exchange=exchange,
            routing_key=routing_key,
            queue_name="test-queue",
        )

        # Assert
        self.assertEqual(subscriber._exchanges_config, {exchange: routing_key})

        # Verify queue binding was called correctly
        self.mock_channel.queue.bind.assert_called_once_with(
            exchange=exchange, queue="test-queue-123", routing_key=routing_key
        )

    @patch("manman.repository.rabbitmq.subscriber.threading.Thread")
    def test_multiple_exchanges_with_single_routing_keys(self, mock_thread):
        """Test multiple exchanges each with a single routing key."""
        # Arrange
        exchanges_config = {"worker-status": "worker.*", "server-status": "server.*"}

        # Act
        subscriber = RabbitStatusSubscriber(
            connection=self.mock_connection,
            exchanges_config=exchanges_config,
            queue_name="test-queue",
        )

        # Assert
        self.assertEqual(subscriber._exchanges_config, exchanges_config)

        # Verify queue binding was called for each exchange
        expected_calls = [
            call(
                exchange="worker-status", queue="test-queue-123", routing_key="worker.*"
            ),
            call(
                exchange="server-status", queue="test-queue-123", routing_key="server.*"
            ),
        ]
        self.mock_channel.queue.bind.assert_has_calls(expected_calls, any_order=True)

    @patch("manman.repository.rabbitmq.subscriber.threading.Thread")
    def test_multiple_exchanges_with_multiple_routing_keys(self, mock_thread):
        """Test multiple exchanges with multiple routing keys each."""
        # Arrange
        exchanges_config = {
            "worker-status": ["worker.created", "worker.running", "worker.complete"],
            "server-status": ["server.initializing", "server.running"],
        }

        # Act
        subscriber = RabbitStatusSubscriber(
            connection=self.mock_connection,
            exchanges_config=exchanges_config,
            queue_name="test-queue",
        )

        # Assert
        self.assertEqual(subscriber._exchanges_config, exchanges_config)

        # Verify queue binding was called for each exchange/routing_key combination
        expected_calls = [
            call(
                exchange="worker-status",
                queue="test-queue-123",
                routing_key="worker.created",
            ),
            call(
                exchange="worker-status",
                queue="test-queue-123",
                routing_key="worker.running",
            ),
            call(
                exchange="worker-status",
                queue="test-queue-123",
                routing_key="worker.complete",
            ),
            call(
                exchange="server-status",
                queue="test-queue-123",
                routing_key="server.initializing",
            ),
            call(
                exchange="server-status",
                queue="test-queue-123",
                routing_key="server.running",
            ),
        ]
        self.mock_channel.queue.bind.assert_has_calls(expected_calls, any_order=True)

    @patch("manman.repository.rabbitmq.subscriber.threading.Thread")
    def test_mixed_routing_key_types(self, mock_thread):
        """Test exchanges with mix of single strings and lists of routing keys."""
        # Arrange
        exchanges_config = {
            "worker-status": "worker.*",  # Single string
            "server-status": ["server.initializing", "server.running"],  # List
            "game-status": "game.complete",  # Single string
        }

        # Act
        RabbitStatusSubscriber(
            connection=self.mock_connection,
            exchanges_config=exchanges_config,
            queue_name="test-queue",
        )

        # Assert
        expected_calls = [
            call(
                exchange="worker-status", queue="test-queue-123", routing_key="worker.*"
            ),
            call(
                exchange="server-status",
                queue="test-queue-123",
                routing_key="server.initializing",
            ),
            call(
                exchange="server-status",
                queue="test-queue-123",
                routing_key="server.running",
            ),
            call(
                exchange="game-status",
                queue="test-queue-123",
                routing_key="game.complete",
            ),
        ]
        self.mock_channel.queue.bind.assert_has_calls(expected_calls, any_order=True)

    @patch("manman.repository.rabbitmq.subscriber.threading.Thread")
    def test_exchanges_config_takes_precedence(self, mock_thread):
        """Test that exchanges_config parameter takes precedence over legacy parameters."""
        # Arrange
        exchanges_config = {"new-exchange": "new.routing.key"}

        # Act
        subscriber = RabbitStatusSubscriber(
            connection=self.mock_connection,
            exchange="old-exchange",  # This should be ignored
            routing_key="old.key",  # This should be ignored
            exchanges_config=exchanges_config,
            queue_name="test-queue",
        )

        # Assert
        self.assertEqual(subscriber._exchanges_config, exchanges_config)

        # Verify only the new exchange was bound
        self.mock_channel.queue.bind.assert_called_once_with(
            exchange="new-exchange",
            queue="test-queue-123",
            routing_key="new.routing.key",
        )

    @patch("manman.repository.rabbitmq.subscriber.threading.Thread")
    def test_no_exchange_configuration_raises_error(self, mock_thread):
        """Test that missing both exchange and exchanges_config raises ValueError."""
        # Act & Assert
        with self.assertRaises(ValueError) as context:
            RabbitStatusSubscriber(
                connection=self.mock_connection, queue_name="test-queue"
            )

        self.assertIn(
            "Either 'exchange' or 'exchanges_config' must be provided",
            str(context.exception),
        )

    @patch("manman.repository.rabbitmq.subscriber.threading.Thread")
    def test_subscriber_name_includes_all_exchanges(self, mock_thread):
        """Test that subscriber name includes all exchange names."""
        # Arrange
        exchanges_config = {
            "worker-status": "worker.*",
            "server-status": "server.*",
            "game-status": "game.*",
        }

        # Act
        subscriber = RabbitStatusSubscriber(
            connection=self.mock_connection,
            exchanges_config=exchanges_config,
            queue_name="test-queue",
        )

        # Assert
        expected_name = (
            "rmq-status-worker-status-server-status-game-status-test-queue-123"
        )
        self.assertEqual(subscriber._name, expected_name)

    @patch("manman.repository.rabbitmq.subscriber.threading.Thread")
    def test_message_handling_with_routing_key(self, mock_thread):
        """Test that messages are handled correctly and routing keys are captured."""
        # Arrange
        subscriber = RabbitStatusSubscriber(
            connection=self.mock_connection,
            exchanges_config={"test-exchange": "test.*"},
            queue_name="test-queue",
        )

        # Create a test status message
        status_info = StatusInfo.create(
            "TestClass", StatusType.RUNNING, game_server_instance_id=123
        )

        # Mock message
        mock_message = Mock()
        mock_message.body = status_info.model_dump_json()
        mock_message.method = {"routing_key": "test.running"}

        # Act
        subscriber._message_handler(mock_message)

        # Assert
        status_messages = subscriber.get_status_messages()
        self.assertEqual(len(status_messages), 1)

        status_message = status_messages[0]
        self.assertIsInstance(status_message, StatusMessage)
        self.assertEqual(status_message.status_info.game_server_instance_id, 123)
        self.assertEqual(status_message.status_info.class_name, "TestClass")
        self.assertEqual(status_message.status_info.status_type, StatusType.RUNNING)
        self.assertEqual(status_message.routing_key, "test.running")


if __name__ == "__main__":
    unittest.main()
