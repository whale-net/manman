"""
Comprehensive example of using the mock message infrastructure.

This module demonstrates how to use the centralized mock fixtures from conftest.py
to test message flows and service interactions without requiring actual RabbitMQ.
"""

import json
import unittest
import sys
import os

# Add the src directory to the path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tests.conftest import (
    MockMessagePublisher, 
    MockMessageSubscriber,
    PYTEST_AVAILABLE
)
from manman.models import InternalStatusInfo, ExternalStatusInfo, Command, StatusType, CommandType
from manman.repository.rabbitmq.config import EntityRegistry


class TestMockInfrastructureUsage(unittest.TestCase):
    """Examples showing how to use the mock infrastructure effectively."""

    def test_basic_mock_usage(self):
        """Basic example of using mock publisher and subscriber."""
        # Create mocks directly
        publisher = MockMessagePublisher()
        subscriber = MockMessageSubscriber()
        
        # Test message flow
        test_message = "Hello, World!"
        
        # Publish a message
        publisher.publish(test_message)
        
        # Verify it was published
        self.assertTrue(publisher.was_called_with(test_message))
        self.assertEqual(publisher.get_last_message(), test_message)
        
        # Simulate the message being received
        subscriber.queue_message(test_message)
        
        # Consume the message
        messages = subscriber.consume()
        self.assertEqual(messages, [test_message])

    def test_service_integration_example(self):
        """Example of testing service classes with mocks."""
        from manman.repository.message.pub import InternalStatusInfoPubService
        from manman.repository.message.sub import InternalStatusSubService
        
        # Create the mock publisher and subscriber
        mock_publisher = MockMessagePublisher()
        mock_subscriber = MockMessageSubscriber()
        
        # Create service instances with the mocks
        pub_service = InternalStatusInfoPubService(mock_publisher)
        sub_service = InternalStatusSubService(mock_subscriber)
        
        # Create test data
        original_status = InternalStatusInfo.create(
            EntityRegistry.WORKER, "test-worker", StatusType.RUNNING
        )
        
        # Publish the status
        pub_service.publish_status(original_status)
        
        # Verify publication
        self.assertEqual(mock_publisher.publish_call_count, 1)
        published_json = mock_publisher.get_last_message()
        
        # Simulate the message being received by the subscriber
        mock_subscriber.queue_message(published_json)
        
        # Consume and verify
        consumed_statuses = sub_service.get_internal_statuses()
        self.assertEqual(len(consumed_statuses), 1)
        
        consumed_status = consumed_statuses[0]
        self.assertEqual(consumed_status.entity_type, original_status.entity_type)
        self.assertEqual(consumed_status.identifier, original_status.identifier)
        self.assertEqual(consumed_status.status_type, original_status.status_type)

    def test_multiple_message_types(self):
        """Example of handling different message types with the same mocks."""
        from manman.repository.message.pub import (
            InternalStatusInfoPubService,
            ExternalStatusInfoPubService,
            CommandPubService,
        )
        
        # Single publisher can handle different message types
        mock_publisher = MockMessagePublisher()
        
        # Create different service instances using the same mock publisher
        internal_pub = InternalStatusInfoPubService(mock_publisher)
        external_pub = ExternalStatusInfoPubService(mock_publisher)
        command_pub = CommandPubService(mock_publisher)
        
        # Publish different types of messages
        internal_status = InternalStatusInfo.create(
            EntityRegistry.WORKER, "worker-1", StatusType.CREATED
        )
        external_status = ExternalStatusInfo.create(
            "TestClass", StatusType.RUNNING, worker_id=100
        )
        command = Command(command_type=CommandType.START, command_args=["arg1"])
        
        internal_pub.publish_status(internal_status)
        external_pub.publish_external_status(external_status)
        command_pub.publish_command(command)
        
        # Verify all messages were published
        self.assertEqual(mock_publisher.publish_call_count, 3)
        self.assertEqual(len(mock_publisher.published_messages), 3)
        
        # Verify message contents
        messages = mock_publisher.published_messages
        
        # Parse and verify each message type
        internal_msg = json.loads(messages[0])
        self.assertEqual(internal_msg["entity_type"], EntityRegistry.WORKER.value)
        self.assertEqual(internal_msg["identifier"], "worker-1")
        
        external_msg = json.loads(messages[1])
        self.assertEqual(external_msg["class_name"], "TestClass")
        self.assertEqual(external_msg["worker_id"], 100)
        
        command_msg = json.loads(messages[2])
        self.assertEqual(command_msg["command_type"], CommandType.START.value)
        self.assertEqual(command_msg["command_args"], ["arg1"])

    def test_mock_inspection_patterns(self):
        """Examples of how to inspect mocks to verify behavior."""
        publisher = MockMessagePublisher()
        subscriber = MockMessageSubscriber()
        
        # Test publication patterns
        messages = ["msg1", "msg2", "msg3"]
        for msg in messages:
            publisher.publish(msg)
        
        # Various ways to inspect what was published
        self.assertEqual(publisher.publish_call_count, 3)
        self.assertEqual(len(publisher.published_messages), 3)
        self.assertEqual(publisher.published_messages, messages)
        self.assertEqual(publisher.get_last_message(), "msg3")
        
        # Check if specific messages were published
        for msg in messages:
            self.assertTrue(publisher.was_called_with(msg))
        self.assertFalse(publisher.was_called_with("nonexistent"))
        
        # Test subscription patterns
        test_messages = ["test1", "test2"]
        subscriber.queue_messages(test_messages)
        
        # Verify queue state
        self.assertTrue(subscriber.has_queued_messages())
        
        # Consume and verify
        consumed = subscriber.consume()
        self.assertEqual(consumed, test_messages)
        self.assertEqual(subscriber.consume_call_count, 1)
        self.assertFalse(subscriber.has_queued_messages())  # Queue should be empty after consume

    def test_mock_state_management(self):
        """Examples of managing mock state during testing."""
        publisher = MockMessagePublisher()
        subscriber = MockMessageSubscriber()
        
        # Initial test
        publisher.publish("test1")
        subscriber.queue_message("sub1")
        
        self.assertEqual(publisher.publish_call_count, 1)
        self.assertTrue(subscriber.has_queued_messages())
        
        # Clear state for next test
        publisher.clear()
        subscriber.clear_queue()
        
        self.assertEqual(publisher.publish_call_count, 0)
        self.assertEqual(len(publisher.published_messages), 0)
        self.assertFalse(subscriber.has_queued_messages())
        
        # Verify clean state for subsequent testing
        publisher.publish("test2")
        self.assertEqual(publisher.publish_call_count, 1)
        self.assertEqual(publisher.get_last_message(), "test2")

    def test_error_handling_patterns(self):
        """Examples of testing error conditions with mocks."""
        publisher = MockMessagePublisher()
        
        # Test getting last message when none published
        with self.assertRaises(ValueError):
            publisher.get_last_message()
        
        # Test normal operation after error
        publisher.publish("recovery test")
        self.assertEqual(publisher.get_last_message(), "recovery test")


# Only run pytest-specific fixture tests if pytest is available
if PYTEST_AVAILABLE:
    import pytest
    
    class TestPytestFixtures:
        """Tests that demonstrate pytest fixture usage (only if pytest available)."""
        
        def test_with_publisher_fixture(self, mock_message_publisher):
            """Example using the pytest publisher fixture."""
            mock_message_publisher.publish("fixture test")
            assert mock_message_publisher.get_last_message() == "fixture test"
        
        def test_with_subscriber_fixture(self, mock_message_subscriber):
            """Example using the pytest subscriber fixture."""
            mock_message_subscriber.queue_message("fixture message")
            messages = mock_message_subscriber.consume()
            assert messages == ["fixture message"]
        
        def test_with_service_fixtures(self, mock_internal_status_pub_service, mock_internal_status_sub_service):
            """Example using the pytest service fixtures."""
            # Get the underlying mocks from the services
            publisher_mock = mock_internal_status_pub_service._publisher
            subscriber_mock = mock_internal_status_sub_service._subscriber
            
            # Create test data
            status = InternalStatusInfo.create(
                EntityRegistry.WORKER, "fixture-worker", StatusType.RUNNING
            )
            
            # Publish using the service
            mock_internal_status_pub_service.publish_status(status)
            
            # Verify publication
            assert publisher_mock.publish_call_count == 1
            
            # Simulate message reception
            published_json = publisher_mock.get_last_message()
            subscriber_mock.queue_message(published_json)
            
            # Consume using the service
            consumed = mock_internal_status_sub_service.get_internal_statuses()
            assert len(consumed) == 1
            assert consumed[0].identifier == "fixture-worker"


if __name__ == "__main__":
    unittest.main()