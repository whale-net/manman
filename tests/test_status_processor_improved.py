"""
Improved tests for the status processor using mock message interfaces.

This module demonstrates how to properly test the StatusEventProcessor
using the mock message interfaces instead of broad patches.
"""

import json
import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add the src directory to the path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tests.conftest import MockMessagePublisher, MockMessageSubscriber
from manman.host.status_processor import StatusEventProcessor
from manman.models import InternalStatusInfo, ExternalStatusInfo, StatusType
from manman.repository.rabbitmq.config import EntityRegistry
from manman.repository.message.pub import ExternalStatusInfoPubService
from manman.repository.message.sub import InternalStatusSubService


class TestStatusProcessorImproved(unittest.TestCase):
    """Improved tests for StatusEventProcessor using proper mocks."""

    def setUp(self):
        """Set up test fixtures."""
        # Set up environment variables that the processor needs
        env_vars = {
            "MANMAN_RABBITMQ_HOST": "localhost",
            "MANMAN_RABBITMQ_PORT": "5672", 
            "MANMAN_RABBITMQ_USER": "guest",
            "MANMAN_RABBITMQ_PASSWORD": "guest",
            "MANMAN_RABBITMQ_ENABLE_SSL": "false",
            "MANMAN_POSTGRES_URL": "postgresql+psycopg2://postgres:postgres@localhost:5432/manman_test",
            "APP_ENV": "test",
        }
        
        for key, value in env_vars.items():
            os.environ[key] = value
            
        # Create mock connection
        self.mock_connection = Mock()
        self.mock_channel = Mock()
        self.mock_connection.channel.return_value = self.mock_channel
        self.mock_channel.queue.declare.return_value = {"queue": "test-queue"}

    def test_status_processor_with_mock_services(self):
        """Test status processing using mock services for proper isolation."""
        # Create mock publishers and subscribers
        mock_internal_subscriber_publisher = MockMessagePublisher()
        mock_internal_subscriber = MockMessageSubscriber()
        mock_worker_publisher = MockMessagePublisher()
        mock_gsi_publisher = MockMessagePublisher()
        
        # Create test internal status messages
        status1 = InternalStatusInfo.create(
            EntityRegistry.WORKER, "100", StatusType.CREATED
        )
        status2 = InternalStatusInfo.create(
            EntityRegistry.WORKER, "101", StatusType.RUNNING
        )
        
        # Queue messages in the mock subscriber
        mock_internal_subscriber.queue_messages([
            status1.model_dump_json(),
            status2.model_dump_json()
        ])
        
        # Create service instances with mocks
        internal_sub_service = InternalStatusSubService(mock_internal_subscriber)
        worker_pub_service = ExternalStatusInfoPubService(mock_worker_publisher)
        gsi_pub_service = ExternalStatusInfoPubService(mock_gsi_publisher)
        
        # Patch the StatusEventProcessor to use our mock services
        with (
            patch("manman.host.status_processor.RabbitSubscriber"),
            patch("manman.host.status_processor.RabbitPublisher"),
            patch.object(StatusEventProcessor, "_StatusEventProcessor__build_internal_status_subscriber", 
                        return_value=internal_sub_service),
            patch.object(StatusEventProcessor, "_StatusEventProcessor__build_external_status_publisher") as mock_build_pub,
        ):
            # Configure the publisher builder to return our mock services
            def build_publisher_side_effect(key):
                if key.entity == EntityRegistry.WORKER:
                    return worker_pub_service
                elif key.entity == EntityRegistry.GAME_SERVER_INSTANCE:
                    return gsi_pub_service
                else:
                    raise ValueError(f"Unexpected entity: {key.entity}")
            
            mock_build_pub.side_effect = build_publisher_side_effect
            
            # Create the processor
            processor = StatusEventProcessor(self.mock_connection)
            
            # Mock the database repository to avoid real database calls
            with patch.object(processor._db_repository, "write_external_status_to_database") as mock_db_write:
                # Process the messages
                processor._process_internal_status_messages()
                
                # Verify the internal subscriber was called
                self.assertEqual(mock_internal_subscriber.consume_call_count, 1)
                
                # Verify external publishers were called correctly
                # Should publish 2 worker status messages (both internal statuses are for workers)
                self.assertEqual(mock_worker_publisher.publish_call_count, 2)
                self.assertEqual(mock_gsi_publisher.publish_call_count, 0)  # No GSI messages
                
                # Verify database writes occurred
                self.assertEqual(mock_db_write.call_count, 2)
                
                # Verify the content of published messages
                published_messages = mock_worker_publisher.published_messages
                self.assertEqual(len(published_messages), 2)
                
                # Parse and verify first message
                msg1_data = json.loads(published_messages[0])
                self.assertEqual(msg1_data["worker_id"], 100)
                self.assertEqual(msg1_data["status_type"], StatusType.CREATED.value)
                
                # Parse and verify second message
                msg2_data = json.loads(published_messages[1])
                self.assertEqual(msg2_data["worker_id"], 101)
                self.assertEqual(msg2_data["status_type"], StatusType.RUNNING.value)

    def test_message_flow_with_gsi_status(self):
        """Test processing GSI (Game Server Instance) status messages."""
        # Create mock services
        mock_internal_subscriber = MockMessageSubscriber()
        mock_worker_publisher = MockMessagePublisher()
        mock_gsi_publisher = MockMessagePublisher()
        
        # Create test GSI status message
        gsi_status = InternalStatusInfo.create(
            EntityRegistry.GAME_SERVER_INSTANCE, "200", StatusType.RUNNING
        )
        
        mock_internal_subscriber.queue_message(gsi_status.model_dump_json())
        
        # Create service instances with mocks
        internal_sub_service = InternalStatusSubService(mock_internal_subscriber)
        worker_pub_service = ExternalStatusInfoPubService(mock_worker_publisher)
        gsi_pub_service = ExternalStatusInfoPubService(mock_gsi_publisher)
        
        with (
            patch("manman.host.status_processor.RabbitSubscriber"),
            patch("manman.host.status_processor.RabbitPublisher"),
            patch.object(StatusEventProcessor, "_StatusEventProcessor__build_internal_status_subscriber", 
                        return_value=internal_sub_service),
            patch.object(StatusEventProcessor, "_StatusEventProcessor__build_external_status_publisher") as mock_build_pub,
        ):
            def build_publisher_side_effect(key):
                if key.entity == EntityRegistry.WORKER:
                    return worker_pub_service
                elif key.entity == EntityRegistry.GAME_SERVER_INSTANCE:
                    return gsi_pub_service
                else:
                    raise ValueError(f"Unexpected entity: {key.entity}")
            
            mock_build_pub.side_effect = build_publisher_side_effect
            
            processor = StatusEventProcessor(self.mock_connection)
            
            with patch.object(processor._db_repository, "write_external_status_to_database"):
                processor._process_internal_status_messages()
                
                # Verify the GSI publisher was called, not the worker publisher
                self.assertEqual(mock_worker_publisher.publish_call_count, 0)
                self.assertEqual(mock_gsi_publisher.publish_call_count, 1)
                
                # Verify GSI message content
                gsi_message = json.loads(mock_gsi_publisher.get_last_message())
                self.assertEqual(gsi_message["game_server_instance_id"], 200)
                self.assertEqual(gsi_message["status_type"], StatusType.RUNNING.value)
                self.assertIsNone(gsi_message["worker_id"])

    def test_empty_message_processing(self):
        """Test processing when no messages are available."""
        # Create mock services with no queued messages
        mock_internal_subscriber = MockMessageSubscriber()
        mock_worker_publisher = MockMessagePublisher()
        mock_gsi_publisher = MockMessagePublisher()
        
        internal_sub_service = InternalStatusSubService(mock_internal_subscriber)
        worker_pub_service = ExternalStatusInfoPubService(mock_worker_publisher)
        gsi_pub_service = ExternalStatusInfoPubService(mock_gsi_publisher)
        
        with (
            patch("manman.host.status_processor.RabbitSubscriber"),
            patch("manman.host.status_processor.RabbitPublisher"),
            patch.object(StatusEventProcessor, "_StatusEventProcessor__build_internal_status_subscriber", 
                        return_value=internal_sub_service),
            patch.object(StatusEventProcessor, "_StatusEventProcessor__build_external_status_publisher") as mock_build_pub,
        ):
            def build_publisher_side_effect(key):
                if key.entity == EntityRegistry.WORKER:
                    return worker_pub_service
                elif key.entity == EntityRegistry.GAME_SERVER_INSTANCE:
                    return gsi_pub_service
                else:
                    raise ValueError(f"Unexpected entity: {key.entity}")
            
            mock_build_pub.side_effect = build_publisher_side_effect
            
            processor = StatusEventProcessor(self.mock_connection)
            
            with patch.object(processor._db_repository, "write_external_status_to_database") as mock_db_write:
                processor._process_internal_status_messages()
                
                # Verify that subscriber was called but nothing was processed
                self.assertEqual(mock_internal_subscriber.consume_call_count, 1)
                self.assertEqual(mock_worker_publisher.publish_call_count, 0)
                self.assertEqual(mock_gsi_publisher.publish_call_count, 0)
                self.assertEqual(mock_db_write.call_count, 0)

    def test_database_error_handling_with_mocks(self):
        """Test that database errors are handled gracefully with mock services."""
        # Create mock services
        mock_internal_subscriber = MockMessageSubscriber()
        mock_worker_publisher = MockMessagePublisher()
        mock_gsi_publisher = MockMessagePublisher()
        
        # Queue a test message
        status = InternalStatusInfo.create(
            EntityRegistry.WORKER, "123", StatusType.RUNNING
        )
        mock_internal_subscriber.queue_message(status.model_dump_json())
        
        internal_sub_service = InternalStatusSubService(mock_internal_subscriber)
        worker_pub_service = ExternalStatusInfoPubService(mock_worker_publisher)
        gsi_pub_service = ExternalStatusInfoPubService(mock_gsi_publisher)
        
        with (
            patch("manman.host.status_processor.RabbitSubscriber"),
            patch("manman.host.status_processor.RabbitPublisher"),
            patch.object(StatusEventProcessor, "_StatusEventProcessor__build_internal_status_subscriber", 
                        return_value=internal_sub_service),
            patch.object(StatusEventProcessor, "_StatusEventProcessor__build_external_status_publisher") as mock_build_pub,
        ):
            def build_publisher_side_effect(key):
                if key.entity == EntityRegistry.WORKER:
                    return worker_pub_service
                elif key.entity == EntityRegistry.GAME_SERVER_INSTANCE:
                    return gsi_pub_service
                else:
                    raise ValueError(f"Unexpected entity: {key.entity}")
            
            mock_build_pub.side_effect = build_publisher_side_effect
            
            processor = StatusEventProcessor(self.mock_connection)
            
            # Mock database to raise an exception
            with patch.object(
                processor._db_repository, 
                "write_external_status_to_database",
                side_effect=Exception("Database connection failed")
            ) as mock_db_write:
                # This should not raise an exception despite the database error
                processor._process_internal_status_messages()
                
                # Verify that the message was still processed despite database error
                self.assertEqual(mock_internal_subscriber.consume_call_count, 1)
                self.assertEqual(mock_worker_publisher.publish_call_count, 1)
                self.assertEqual(mock_db_write.call_count, 1)


if __name__ == "__main__":
    unittest.main()