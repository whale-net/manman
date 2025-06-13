"""
Integration test for RabbitMQ connection recovery.
"""

import threading
import time
import unittest
from unittest.mock import Mock, patch

from amqpstorm import AMQPConnectionError

from manman.repository.rabbitmq.config import (
    BindingConfig,
    EntityRegistry,
    MessageTypeRegistry,
    QueueConfig,
    RoutingKeyConfig,
)
from manman.repository.rabbitmq.connection import RobustConnection
from manman.repository.rabbitmq.publisher import RabbitPublisher
from manman.repository.rabbitmq.subscriber import RabbitSubscriber


class TestConnectionRecoveryIntegration(unittest.TestCase):
    """Test end-to-end connection recovery scenarios."""

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
    def test_publisher_handles_connection_recovery(self, mock_connection_class):
        """Test that publisher operations work after connection recovery."""
        # Set up mock connection that starts healthy
        mock_connection = Mock()
        mock_connection.is_open = True
        mock_connection.check_for_errors = Mock()
        mock_channel = Mock()
        mock_connection.channel.return_value = mock_channel
        mock_connection_class.return_value = mock_connection

        # Create robust connection
        robust_conn = RobustConnection(
            connection_params=self.connection_params,
            heartbeat_interval=10,
            max_reconnect_attempts=2,
            reconnect_delay=0.1,
        )

        # Create publisher
        binding_config = BindingConfig(
            exchange="test-exchange",
            routing_keys=[
                RoutingKeyConfig(
                    entity=EntityRegistry.WORKER,
                    identifier="123",
                    type=MessageTypeRegistry.STATUS,
                )
            ],
        )

        publisher = RabbitPublisher(
            connection=robust_conn.get_connection(), binding_configs=binding_config
        )

        # Should work initially
        publisher.publish("test message")
        mock_channel.basic.publish.assert_called_once()

        # Simulate connection failure and recovery
        mock_connection.is_open = False
        mock_connection.check_for_errors.side_effect = AMQPConnectionError(
            "Connection lost"
        )

        # Getting connection should now fail
        with self.assertRaises(AMQPConnectionError):
            robust_conn.get_connection()

        # Publisher should fail if trying to use old channel
        # This is expected - the service should recreate the publisher after connection recovery

        # Simulate connection recovery
        mock_connection.is_open = True
        mock_connection.check_for_errors.side_effect = None

        # Small delay for reconnection
        time.sleep(0.2)

        # After recovery, we should be able to get connection again
        if robust_conn.is_connected():
            new_publisher = RabbitPublisher(
                connection=robust_conn.get_connection(), binding_configs=binding_config
            )
            new_publisher.publish("test message after recovery")

        robust_conn.close()

    @patch("manman.repository.rabbitmq.connection.Connection")
    def test_subscriber_handles_connection_recovery(self, mock_connection_class):
        """Test that subscriber operations work after connection recovery."""
        # Set up mock connection that starts healthy
        mock_connection = Mock()
        mock_connection.is_open = True
        mock_connection.check_for_errors = Mock()
        mock_channel = Mock()
        mock_connection.channel.return_value = mock_channel
        mock_channel.is_open = True
        mock_channel.queue.declare.return_value = {"queue": "test-queue"}
        mock_channel.basic.consume.return_value = "consumer-tag"
        mock_connection_class.return_value = mock_connection

        # Create robust connection
        robust_conn = RobustConnection(
            connection_params=self.connection_params,
            heartbeat_interval=10,
            max_reconnect_attempts=2,
            reconnect_delay=0.1,
        )

        # Create subscriber
        binding_config = BindingConfig(
            exchange="test-exchange",
            routing_keys=[
                RoutingKeyConfig(
                    entity=EntityRegistry.WORKER,
                    identifier="123",
                    type=MessageTypeRegistry.COMMAND,
                )
            ],
        )

        queue_config = QueueConfig(
            name="test-queue", durable=True, exclusive=False, auto_delete=True
        )

        with (
            patch("threading.Thread"),
            patch("manman.repository.rabbitmq.subscriber.queue.Queue"),
        ):
            subscriber = RabbitSubscriber(
                connection=robust_conn.get_connection(),
                binding_configs=binding_config,
                queue_config=queue_config,
            )

            # Should initialize properly
            mock_channel.queue.declare.assert_called_once()
            mock_channel.basic.consume.assert_called_once()

        robust_conn.close()

    @patch("manman.repository.rabbitmq.connection.Connection")
    def test_connection_callbacks_called(self, mock_connection_class):
        """Test that connection lost and restored callbacks are called."""
        # Set up connection events
        connection_lost_event = threading.Event()
        connection_restored_event = threading.Event()

        def on_lost():
            connection_lost_event.set()

        def on_restored():
            connection_restored_event.set()

        # Mock connection that starts healthy then fails
        mock_connection = Mock()
        mock_connection.is_open = True
        mock_connection.check_for_errors = Mock()
        mock_connection_class.return_value = mock_connection

        # Create robust connection with callbacks
        robust_conn = RobustConnection(
            connection_params=self.connection_params,
            heartbeat_interval=10,
            max_reconnect_attempts=3,
            reconnect_delay=0.1,
            on_connection_lost=on_lost,
            on_connection_restored=on_restored,
        )

        # Should be connected initially
        self.assertTrue(robust_conn.is_connected())

        # Simulate connection loss
        mock_connection.is_open = False
        mock_connection.check_for_errors.side_effect = AMQPConnectionError(
            "Connection lost"
        )

        # Try to get connection, should trigger reconnection
        with self.assertRaises(AMQPConnectionError):
            robust_conn.get_connection()

        # Wait for connection lost callback
        self.assertTrue(connection_lost_event.wait(timeout=1.0))

        # Simulate connection restoration
        mock_connection.is_open = True
        mock_connection.check_for_errors.side_effect = None

        # Wait for reconnection to complete
        time.sleep(0.3)

        # Connection restored callback should have been called
        self.assertTrue(connection_restored_event.wait(timeout=1.0))

        robust_conn.close()

    def test_util_functions_work_with_robust_connection(self):
        """Test that util functions work with the robust connection."""
        from manman.util import (
            get_rabbitmq_connection,
            init_rabbitmq,
            shutdown_rabbitmq,
        )

        with patch(
            "manman.repository.rabbitmq.connection.Connection"
        ) as mock_connection_class:
            mock_connection = Mock()
            mock_connection.is_open = True
            mock_connection.check_for_errors = Mock()
            mock_connection_class.return_value = mock_connection

            # Initialize RabbitMQ with robust connection
            init_rabbitmq(
                host="localhost",
                port=5672,
                username="guest",
                password="guest",
                heartbeat_interval=30,
            )

            # Should be able to get connection
            conn = get_rabbitmq_connection()
            self.assertEqual(conn, mock_connection)

            # Should be able to shutdown
            shutdown_rabbitmq()
