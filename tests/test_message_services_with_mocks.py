"""
Tests demonstrating how to use mock message interfaces with service classes.

This module shows how the mock publishers and subscribers can be used to test
the message service classes without needing actual RabbitMQ connections.
"""

import json
import unittest
import sys
import os

# Add the src directory to the path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tests.conftest import MockMessagePublisher, MockMessageSubscriber
from manman.repository.message.pub import (
    InternalStatusInfoPubService,
    ExternalStatusInfoPubService,
    CommandPubService,
)
from manman.repository.message.sub import (
    InternalStatusSubService,
    ExternalStatusSubService, 
    CommandSubService,
)
from manman.models import InternalStatusInfo, ExternalStatusInfo, Command, StatusType, CommandType
from manman.repository.rabbitmq.config import EntityRegistry


class TestPublishingServicesWithMocks(unittest.TestCase):
    """Test publishing services using mock publishers."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_publisher = MockMessagePublisher()

    def test_internal_status_publishing(self):
        """Test that InternalStatusInfoPubService publishes messages correctly."""
        pub_service = InternalStatusInfoPubService(self.mock_publisher)
        
        # Create a test status
        status = InternalStatusInfo.create(
            entity_type=EntityRegistry.WORKER,
            identifier="test-worker-123",
            status_type=StatusType.RUNNING
        )
        
        # Publish the status
        pub_service.publish_status(status)
        
        # Verify the message was published
        self.assertEqual(self.mock_publisher.publish_call_count, 1)
        self.assertEqual(len(self.mock_publisher.published_messages), 1)
        
        # Verify the message content
        published_message = self.mock_publisher.get_last_message()
        self.assertIsInstance(published_message, str)
        
        # Parse the JSON to verify structure
        message_data = json.loads(published_message)
        self.assertEqual(message_data["entity_type"], EntityRegistry.WORKER.value)
        self.assertEqual(message_data["identifier"], "test-worker-123")
        self.assertEqual(message_data["status_type"], StatusType.RUNNING.value)

    def test_external_status_publishing(self):
        """Test that ExternalStatusInfoPubService publishes messages correctly."""
        pub_service = ExternalStatusInfoPubService(self.mock_publisher)
        
        # Create a test external status
        status = ExternalStatusInfo.create(
            "TestWorkerClass", 
            StatusType.COMPLETE, 
            worker_id=456
        )
        
        # Publish the status
        pub_service.publish_external_status(status)
        
        # Verify the message was published
        self.assertEqual(self.mock_publisher.publish_call_count, 1)
        self.assertTrue(self.mock_publisher.was_called_with(self.mock_publisher.get_last_message()))
        
        # Parse and verify the message content
        message_data = json.loads(self.mock_publisher.get_last_message())
        self.assertEqual(message_data["class_name"], "TestWorkerClass")
        self.assertEqual(message_data["status_type"], StatusType.COMPLETE.value)
        self.assertEqual(message_data["worker_id"], 456)

    def test_command_publishing(self):
        """Test that CommandPubService publishes commands correctly."""
        pub_service = CommandPubService(self.mock_publisher)
        
        # Create a test command
        command = Command(
            command_type=CommandType.START,
            command_args=["arg1", "arg2"]
        )
        
        # Publish the command
        pub_service.publish_command(command)
        
        # Verify the message was published
        self.assertEqual(self.mock_publisher.publish_call_count, 1)
        
        # Parse and verify the message content
        message_data = json.loads(self.mock_publisher.get_last_message())
        self.assertEqual(message_data["command_type"], CommandType.START.value)
        self.assertEqual(message_data["command_args"], ["arg1", "arg2"])

    def test_multiple_publications(self):
        """Test that multiple publications are tracked correctly."""
        pub_service = InternalStatusInfoPubService(self.mock_publisher)
        
        # Create multiple statuses
        statuses = [
            InternalStatusInfo.create(EntityRegistry.WORKER, "worker-1", StatusType.CREATED),
            InternalStatusInfo.create(EntityRegistry.WORKER, "worker-2", StatusType.RUNNING),
            InternalStatusInfo.create(EntityRegistry.WORKER, "worker-3", StatusType.COMPLETE),
        ]
        
        # Publish all statuses
        for status in statuses:
            pub_service.publish_status(status)
        
        # Verify all messages were published
        self.assertEqual(self.mock_publisher.publish_call_count, 3)
        self.assertEqual(len(self.mock_publisher.published_messages), 3)
        
        # Verify each message content
        for i, published_message in enumerate(self.mock_publisher.published_messages):
            message_data = json.loads(published_message)
            self.assertEqual(message_data["identifier"], f"worker-{i+1}")


class TestSubscribingServicesWithMocks(unittest.TestCase):
    """Test subscribing services using mock subscribers."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_subscriber = MockMessageSubscriber()

    def test_internal_status_consuming(self):
        """Test that InternalStatusSubService consumes messages correctly."""
        sub_service = InternalStatusSubService(self.mock_subscriber)
        
        # Create test status messages
        status1 = InternalStatusInfo.create(EntityRegistry.WORKER, "worker-1", StatusType.RUNNING)
        status2 = InternalStatusInfo.create(EntityRegistry.WORKER, "worker-2", StatusType.COMPLETE)
        
        # Queue the messages in the mock subscriber
        self.mock_subscriber.queue_message(status1.model_dump_json())
        self.mock_subscriber.queue_message(status2.model_dump_json())
        
        # Consume the messages
        consumed_statuses = sub_service.get_internal_statuses()
        
        # Verify the consumption
        self.assertEqual(self.mock_subscriber.consume_call_count, 1)
        self.assertEqual(len(consumed_statuses), 2)
        
        # Verify the consumed status content
        self.assertEqual(consumed_statuses[0].identifier, "worker-1")
        self.assertEqual(consumed_statuses[0].status_type, StatusType.RUNNING)
        self.assertEqual(consumed_statuses[1].identifier, "worker-2")
        self.assertEqual(consumed_statuses[1].status_type, StatusType.COMPLETE)

    def test_external_status_consuming(self):
        """Test that ExternalStatusSubService consumes messages correctly."""
        sub_service = ExternalStatusSubService(self.mock_subscriber)
        
        # Create test external status message
        status = ExternalStatusInfo.create("TestClass", StatusType.CRASHED, worker_id=123)
        
        # Queue the message
        self.mock_subscriber.queue_message(status.model_dump_json())
        
        # Consume the message
        consumed_statuses = sub_service.get_external_status_infos()
        
        # Verify the consumption
        self.assertEqual(len(consumed_statuses), 1)
        self.assertEqual(consumed_statuses[0].class_name, "TestClass")
        self.assertEqual(consumed_statuses[0].status_type, StatusType.CRASHED)
        self.assertEqual(consumed_statuses[0].worker_id, 123)

    def test_command_consuming(self):
        """Test that CommandSubService consumes commands correctly."""
        sub_service = CommandSubService(self.mock_subscriber)
        
        # Create test command messages
        command1 = Command(command_type=CommandType.START, command_args=["start-arg"])
        command2 = Command(command_type=CommandType.STOP, command_args=["stop-arg"])
        
        # Queue the messages
        self.mock_subscriber.queue_messages([
            command1.model_dump_json(),
            command2.model_dump_json()
        ])
        
        # Consume the commands
        consumed_commands = sub_service.get_commands()
        
        # Verify the consumption
        self.assertEqual(len(consumed_commands), 2)
        self.assertEqual(consumed_commands[0].command_type, CommandType.START)
        self.assertEqual(consumed_commands[0].command_args, ["start-arg"])
        self.assertEqual(consumed_commands[1].command_type, CommandType.STOP)
        self.assertEqual(consumed_commands[1].command_args, ["stop-arg"])

    def test_empty_consumption(self):
        """Test consuming when no messages are available."""
        sub_service = InternalStatusSubService(self.mock_subscriber)
        
        # Consume without queueing any messages
        consumed_statuses = sub_service.get_internal_statuses()
        
        # Verify empty consumption
        self.assertEqual(len(consumed_statuses), 0)
        self.assertEqual(self.mock_subscriber.consume_call_count, 1)

    def test_multiple_consume_calls(self):
        """Test multiple consume calls work independently."""
        sub_service = CommandSubService(self.mock_subscriber)
        
        # First batch
        command1 = Command(command_type=CommandType.START, command_args=["1"])
        self.mock_subscriber.queue_message(command1.model_dump_json())
        
        first_batch = sub_service.get_commands()
        self.assertEqual(len(first_batch), 1)
        self.assertEqual(first_batch[0].command_args, ["1"])
        
        # Second batch
        command2 = Command(command_type=CommandType.STOP, command_args=["2"])
        self.mock_subscriber.queue_message(command2.model_dump_json())
        
        second_batch = sub_service.get_commands()
        self.assertEqual(len(second_batch), 1)
        self.assertEqual(second_batch[0].command_args, ["2"])
        
        # Verify total consume calls
        self.assertEqual(self.mock_subscriber.consume_call_count, 2)


class TestIntegratedMessageFlow(unittest.TestCase):
    """Test integrated message flow using both publisher and subscriber mocks."""

    def test_end_to_end_message_flow(self):
        """Test a complete message flow from publisher to subscriber."""
        # Set up publisher and subscriber
        mock_publisher = MockMessagePublisher()
        mock_subscriber = MockMessageSubscriber()
        
        pub_service = InternalStatusInfoPubService(mock_publisher)
        sub_service = InternalStatusSubService(mock_subscriber)
        
        # Create and publish a status
        original_status = InternalStatusInfo.create(
            EntityRegistry.WORKER, "integration-test-worker", StatusType.RUNNING
        )
        pub_service.publish_status(original_status)
        
        # Simulate the message being received by subscriber
        published_message = mock_publisher.get_last_message()
        mock_subscriber.queue_message(published_message)
        
        # Consume the message
        consumed_statuses = sub_service.get_internal_statuses()
        
        # Verify the end-to-end flow
        self.assertEqual(len(consumed_statuses), 1)
        consumed_status = consumed_statuses[0]
        
        self.assertEqual(consumed_status.entity_type, original_status.entity_type)
        self.assertEqual(consumed_status.identifier, original_status.identifier)
        self.assertEqual(consumed_status.status_type, original_status.status_type)
        self.assertEqual(consumed_status.as_of, original_status.as_of)


if __name__ == "__main__":
    unittest.main()