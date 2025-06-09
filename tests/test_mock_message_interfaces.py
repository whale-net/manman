"""
Tests for the mock message interface implementations.

This module tests that the mock publishers and subscribers work correctly
and provide the expected functionality for testing message flows.
"""

import unittest
import sys
import os

# Add the src directory to the path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tests.conftest import MockMessagePublisher, MockMessageSubscriber


class TestMockMessagePublisher(unittest.TestCase):
    """Test cases for MockMessagePublisher."""

    def setUp(self):
        """Set up test fixtures."""
        self.publisher = MockMessagePublisher()

    def test_initial_state(self):
        """Test that the publisher starts in a clean state."""
        self.assertEqual(self.publisher.publish_call_count, 0)
        self.assertEqual(len(self.publisher.published_messages), 0)

    def test_publish_single_message(self):
        """Test publishing a single message."""
        message = "test message"
        self.publisher.publish(message)

        self.assertEqual(self.publisher.publish_call_count, 1)
        self.assertEqual(len(self.publisher.published_messages), 1)
        self.assertEqual(self.publisher.published_messages[0], message)

    def test_publish_multiple_messages(self):
        """Test publishing multiple messages."""
        messages = ["message 1", "message 2", "message 3"]
        
        for message in messages:
            self.publisher.publish(message)

        self.assertEqual(self.publisher.publish_call_count, 3)
        self.assertEqual(len(self.publisher.published_messages), 3)
        self.assertEqual(self.publisher.published_messages, messages)

    def test_get_last_message(self):
        """Test getting the last published message."""
        messages = ["first", "second", "third"]
        
        for message in messages:
            self.publisher.publish(message)
            
        self.assertEqual(self.publisher.get_last_message(), "third")

    def test_get_last_message_empty(self):
        """Test getting last message when no messages have been published."""
        with self.assertRaises(ValueError):
            self.publisher.get_last_message()

    def test_was_called_with(self):
        """Test checking if publisher was called with specific message."""
        messages = ["hello", "world", "test"]
        
        for message in messages:
            self.publisher.publish(message)
            
        self.assertTrue(self.publisher.was_called_with("hello"))
        self.assertTrue(self.publisher.was_called_with("world"))
        self.assertTrue(self.publisher.was_called_with("test"))
        self.assertFalse(self.publisher.was_called_with("not published"))

    def test_clear(self):
        """Test clearing the publisher state."""
        self.publisher.publish("test message")
        self.publisher.publish("another message")
        
        self.assertEqual(self.publisher.publish_call_count, 2)
        self.assertEqual(len(self.publisher.published_messages), 2)
        
        self.publisher.clear()
        
        self.assertEqual(self.publisher.publish_call_count, 0)
        self.assertEqual(len(self.publisher.published_messages), 0)


class TestMockMessageSubscriber(unittest.TestCase):
    """Test cases for MockMessageSubscriber."""

    def setUp(self):
        """Set up test fixtures."""
        self.subscriber = MockMessageSubscriber()

    def test_initial_state(self):
        """Test that the subscriber starts in a clean state."""
        self.assertEqual(self.subscriber.consume_call_count, 0)
        self.assertFalse(self.subscriber.has_queued_messages())

    def test_consume_empty_queue(self):
        """Test consuming when no messages are queued."""
        messages = self.subscriber.consume()
        
        self.assertEqual(self.subscriber.consume_call_count, 1)
        self.assertEqual(len(messages), 0)

    def test_queue_and_consume_single_message(self):
        """Test queueing and consuming a single message."""
        test_message = "test message"
        self.subscriber.queue_message(test_message)
        
        self.assertTrue(self.subscriber.has_queued_messages())
        
        messages = self.subscriber.consume()
        
        self.assertEqual(self.subscriber.consume_call_count, 1)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0], test_message)
        self.assertFalse(self.subscriber.has_queued_messages())

    def test_queue_and_consume_multiple_messages(self):
        """Test queueing and consuming multiple messages."""
        test_messages = ["message 1", "message 2", "message 3"]
        
        for message in test_messages:
            self.subscriber.queue_message(message)
            
        self.assertTrue(self.subscriber.has_queued_messages())
        
        messages = self.subscriber.consume()
        
        self.assertEqual(self.subscriber.consume_call_count, 1)
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages, test_messages)
        self.assertFalse(self.subscriber.has_queued_messages())

    def test_queue_messages_batch(self):
        """Test queueing multiple messages at once."""
        test_messages = ["batch message 1", "batch message 2", "batch message 3"]
        
        self.subscriber.queue_messages(test_messages)
        
        self.assertTrue(self.subscriber.has_queued_messages())
        
        messages = self.subscriber.consume()
        
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages, test_messages)

    def test_multiple_consume_calls(self):
        """Test that consuming clears the queue."""
        self.subscriber.queue_message("test message")
        
        # First consume should return the message
        messages1 = self.subscriber.consume()
        self.assertEqual(len(messages1), 1)
        self.assertEqual(self.subscriber.consume_call_count, 1)
        
        # Second consume should return empty list
        messages2 = self.subscriber.consume()
        self.assertEqual(len(messages2), 0)
        self.assertEqual(self.subscriber.consume_call_count, 2)

    def test_clear_queue(self):
        """Test clearing the queue manually."""
        test_messages = ["message 1", "message 2"]
        self.subscriber.queue_messages(test_messages)
        
        self.assertTrue(self.subscriber.has_queued_messages())
        
        self.subscriber.clear_queue()
        
        self.assertFalse(self.subscriber.has_queued_messages())
        
        messages = self.subscriber.consume()
        self.assertEqual(len(messages), 0)


class TestMockInterfaces(unittest.TestCase):
    """Test cases for mock interface compatibility."""

    def test_publisher_interface_compatibility(self):
        """Test that MockMessagePublisher implements MessagePublisherInterface."""
        from manman.repository.message.abstract_interface import MessagePublisherInterface
        
        publisher = MockMessagePublisher()
        self.assertIsInstance(publisher, MessagePublisherInterface)
        
        # Test that the interface method is implemented
        publisher.publish("test")
        self.assertEqual(publisher.publish_call_count, 1)

    def test_subscriber_interface_compatibility(self):
        """Test that MockMessageSubscriber implements MessageSubscriberInterface."""
        from manman.repository.message.abstract_interface import MessageSubscriberInterface
        
        subscriber = MockMessageSubscriber()
        self.assertIsInstance(subscriber, MessageSubscriberInterface)
        
        # Test that the interface method is implemented
        messages = subscriber.consume()
        self.assertEqual(subscriber.consume_call_count, 1)
        self.assertEqual(messages, [])


if __name__ == "__main__":
    unittest.main()