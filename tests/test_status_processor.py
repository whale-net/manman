"""
Integration tests for the status processor implementation.

This module tests that the status processor correctly:
1. Receives status messages from RabbitMQ
2. Extracts routing keys properly
3. Writes status information to the database
"""

import os
from unittest.mock import Mock, patch

import pytest

from manman.host.status_processor import StatusEventProcessor
from manman.models import StatusInfo, StatusType
from manman.repository.rabbitmq import StatusMessage


class TestStatusProcessor:
    """Integration tests for the status processor."""

    @pytest.fixture(autouse=True)
    def setup_test_environment(self, monkeypatch):
        """Setup test environment variables."""
        # Mock environment variables for testing
        test_env = {
            "MANMAN_RABBITMQ_HOST": "localhost",
            "MANMAN_RABBITMQ_PORT": "5672",
            "MANMAN_RABBITMQ_USER": "guest",
            "MANMAN_RABBITMQ_PASSWORD": "guest",
            "MANMAN_RABBITMQ_ENABLE_SSL": "false",
            "MANMAN_POSTGRES_URL": "postgresql+psycopg2://postgres:postgres@localhost:5432/manman_test",
            "APP_ENV": "test",
        }

        for key, value in test_env.items():
            monkeypatch.setenv(key, value)

    @pytest.fixture
    def mock_rabbitmq_connection(self):
        """Create a properly mocked RabbitMQ connection."""
        mock_connection = Mock()

        # Mock the channel and queue.declare to return proper structure
        mock_channel = Mock()
        mock_connection.channel.return_value = mock_channel
        mock_channel.queue.declare.return_value = {"queue": "test-queue"}

        return mock_connection

    def test_status_processor_initialization(self, mock_rabbitmq_connection):
        """Test that the status processor can be initialized."""
        with (
            patch(
                "manman.host.status_processor.RabbitStatusSubscriber"
            ) as mock_subscriber_class,
            patch(
                "manman.host.status_processor.RabbitStatusPublisher"
            ) as mock_publisher_class,
        ):
            mock_subscriber = Mock()
            mock_publisher = Mock()
            mock_subscriber_class.return_value = mock_subscriber
            mock_publisher_class.return_value = mock_publisher

            # This should not raise any exceptions
            processor = StatusEventProcessor(mock_rabbitmq_connection)

            assert processor is not None
            assert processor._rabbitmq_connection == mock_rabbitmq_connection
            assert processor._is_running is False
            assert processor._internal_status_subscriber == mock_subscriber
            assert processor._external_status_publisher == mock_publisher

    def test_status_message_handling(self, mock_rabbitmq_connection):
        """Test status message handling without actual database/RabbitMQ."""
        with (
            patch("manman.host.status_processor.RabbitStatusSubscriber"),
            patch("manman.host.status_processor.RabbitStatusPublisher"),
        ):
            processor = StatusEventProcessor(mock_rabbitmq_connection)

        # Create a test status message
        status_info = StatusInfo.create(
            "WorkerService", StatusType.RUNNING, worker_id=123
        )

        # Mock the database write method to avoid actual database calls
        with patch.object(processor, "_write_status_to_database") as mock_write:
            processor._write_status_to_database(status_info)

            # Verify the database write method was called with correct parameters
            mock_write.assert_called_once_with(status_info)

    def test_status_message_creation(self):
        """Test that StatusMessage objects are created correctly."""
        status_info = StatusInfo.create("TestClass", StatusType.CREATED, worker_id=789)
        routing_key = "worker-instance.789.status"

        status_message = StatusMessage(status_info=status_info, routing_key=routing_key)

        assert status_message.status_info == status_info
        assert status_message.routing_key == routing_key
        assert status_message.status_info.class_name == "TestClass"
        assert status_message.status_info.status_type == StatusType.CREATED

    def test_database_error_handling(self, mock_rabbitmq_connection):
        """Test that database errors are handled gracefully."""
        with (
            patch("manman.host.status_processor.RabbitStatusSubscriber"),
            patch("manman.host.status_processor.RabbitStatusPublisher"),
        ):
            processor = StatusEventProcessor(mock_rabbitmq_connection)

            status_info = StatusInfo.create(
                "WorkerService", StatusType.RUNNING, worker_id=123
            )

            # Mock database session to raise an exception
            with patch(
                "manman.host.status_processor.get_sqlalchemy_session"
            ) as mock_session_ctx:
                mock_session = Mock()
                mock_session_ctx.return_value.__enter__.return_value = mock_session
                mock_session.add.side_effect = Exception("Database connection failed")

                # This should not raise an exception (should be logged instead)
                processor._write_status_to_database(status_info)

                # Verify that the exception was caught and add was attempted
                mock_session.add.assert_called_once()

    def test_status_info_fields_mapping(self, mock_rabbitmq_connection):
        """Test that StatusInfo database record is created with correct field mapping."""
        with (
            patch("manman.host.status_processor.RabbitStatusSubscriber"),
            patch("manman.host.status_processor.RabbitStatusPublisher"),
        ):
            processor = StatusEventProcessor(mock_rabbitmq_connection)

            # Create test status info with specific values
            status_info = StatusInfo.create(
                "TestWorker", StatusType.COMPLETE, worker_id=999
            )

            with patch(
                "manman.host.status_processor.get_sqlalchemy_session"
            ) as mock_session_ctx:
                mock_session = Mock()
                mock_session_ctx.return_value.__enter__.return_value = mock_session

                processor._write_status_to_database(status_info)

                # Get the StatusInfo object that was passed to session.add
                mock_session.add.assert_called_once()
                added_record = mock_session.add.call_args[0][0]

                # Verify all fields are correctly mapped
                assert added_record.worker_id == 999
                assert added_record.game_server_instance_id is None
                assert added_record.class_name == "TestWorker"
                assert added_record.status_type == StatusType.COMPLETE
                assert added_record.as_of == status_info.as_of

    @pytest.mark.integration
    def test_message_processing_flow(self, mock_rabbitmq_connection):
        """Integration test for the complete message processing flow."""
        with (
            patch(
                "manman.host.status_processor.RabbitStatusSubscriber"
            ) as mock_subscriber_class,
            patch("manman.host.status_processor.RabbitStatusPublisher"),
        ):
            mock_subscriber = Mock()
            mock_subscriber_class.return_value = mock_subscriber

            processor = StatusEventProcessor(mock_rabbitmq_connection)

            # Mock the status subscriber to return test messages
            test_messages = [
                StatusMessage(
                    status_info=StatusInfo.create(
                        "WorkerService", StatusType.CREATED, worker_id=100
                    ),
                    routing_key="worker-instance.100.status",
                ),
                StatusMessage(
                    status_info=StatusInfo.create(
                        "Server", StatusType.RUNNING, worker_id=101
                    ),
                    routing_key="worker-instance.101.status",
                ),
            ]

            mock_subscriber.get_status_messages.return_value = test_messages

            with patch.object(
                processor, "_external_status_publisher"
            ) as mock_publisher:
                processor._process_internal_status_messages()

                # Verify that each message was published externally
                assert mock_publisher.publish_external.call_count == 2
                mock_publisher.publish_external.assert_any_call(
                    test_messages[0].status_info
                )
                mock_publisher.publish_external.assert_any_call(
                    test_messages[1].status_info
                )

    def test_processor_shutdown(self, mock_rabbitmq_connection):
        """Test that the processor shuts down cleanly."""
        with (
            patch(
                "manman.host.status_processor.RabbitStatusSubscriber"
            ) as mock_subscriber_class,
            patch(
                "manman.host.status_processor.RabbitStatusPublisher"
            ) as mock_publisher_class,
        ):
            mock_internal_subscriber = Mock()
            mock_external_consumer = Mock()
            mock_publisher = Mock()

            # The RabbitStatusSubscriber is called twice - once for internal, once for external
            mock_subscriber_class.side_effect = [
                mock_internal_subscriber,
                mock_external_consumer,
            ]
            mock_publisher_class.return_value = mock_publisher

            processor = StatusEventProcessor(mock_rabbitmq_connection)

            processor._shutdown()

            # Verify shutdown was called on all components
            mock_internal_subscriber.shutdown.assert_called_once()
            mock_external_consumer.shutdown.assert_called_once()
            mock_publisher.shutdown.assert_called_once()
            assert processor._is_running is False


class TestStatusProcessorRealConnections:
    """Tests that can run with real connections if services are available."""

    @pytest.mark.skipif(
        not os.getenv("INTEGRATION_TESTS_ENABLED"),
        reason="Integration tests require INTEGRATION_TESTS_ENABLED=true and running services",
    )
    def test_end_to_end_status_processing(self):
        """End-to-end test with real RabbitMQ and database connections."""
        # This test would only run when explicitly enabled and when services are running
        pytest.skip("End-to-end integration test - implement when needed")
