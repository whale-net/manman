"""
Shared pytest fixtures and utilities for testing.

This module provides reusable testing utilities that can be used across different test modules.
"""

from typing import Generator, List
from unittest.mock import Mock, patch

# Try to import pytest, but don't fail if it's not available
try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False
    # Create a dummy pytest object for when pytest is not available
    class DummyPytest:
        def fixture(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
    pytest = DummyPytest()

from manman.repository.message.abstract_interface import (
    MessagePublisherInterface,
    MessageSubscriberInterface,
)


# Mock implementations of the message interfaces
class MockMessagePublisher(MessagePublisherInterface):
    """
    Mock implementation of MessagePublisherInterface for testing.
    
    This mock tracks all published messages and allows inspection of what was sent.
    """
    
    def __init__(self):
        self.published_messages: List[str] = []
        self.publish_call_count = 0
        
    def publish(self, message: str) -> None:
        """Record the published message for later inspection."""
        self.published_messages.append(message)
        self.publish_call_count += 1
        
    def clear(self) -> None:
        """Clear the recorded messages and call count."""
        self.published_messages.clear()
        self.publish_call_count = 0
        
    def get_last_message(self) -> str:
        """Get the last published message."""
        if not self.published_messages:
            raise ValueError("No messages have been published")
        return self.published_messages[-1]
        
    def was_called_with(self, message: str) -> bool:
        """Check if the publisher was called with a specific message."""
        return message in self.published_messages


class MockMessageSubscriber(MessageSubscriberInterface):
    """
    Mock implementation of MessageSubscriberInterface for testing.
    
    This mock allows setting up test messages to be consumed and tracks consumption calls.
    """
    
    def __init__(self):
        self._queued_messages: List[str] = []
        self.consume_call_count = 0
        
    def consume(self) -> List[str]:
        """Return all queued messages and clear the queue."""
        self.consume_call_count += 1
        messages = self._queued_messages.copy()
        self._queued_messages.clear()
        return messages
        
    def queue_message(self, message: str) -> None:
        """Add a message to be returned by the next consume() call."""
        self._queued_messages.append(message)
        
    def queue_messages(self, messages: List[str]) -> None:
        """Add multiple messages to be returned by the next consume() call."""
        self._queued_messages.extend(messages)
        
    def clear_queue(self) -> None:
        """Clear all queued messages."""
        self._queued_messages.clear()
        
    def has_queued_messages(self) -> bool:
        """Check if there are any queued messages."""
        return bool(self._queued_messages)


def create_mock_repository(repository_import_path: str) -> Generator[Mock, None, None]:
    """
    Factory function to create repository mocks for any repository class.

    This is a reusable utility that can mock any repository by patching its import path.

    Args:
        repository_import_path: The full import path to the repository class
                               (e.g., 'manman.host.api.status.api.StatusRepository')

    Returns:
        A mock repository instance that can be configured for tests

    Example usage in a test file:
        @pytest.fixture
        def mock_my_repository():
            yield from create_mock_repository('my.module.MyRepository')
    """
    with patch(repository_import_path) as mock_repo_class:
        mock_repo = Mock()
        mock_repo_class.return_value = mock_repo
        yield mock_repo


# Example fixtures using the factory - add more as needed:


@pytest.fixture
def mock_message_publisher():
    """Create a mock MessagePublisher for testing."""
    return MockMessagePublisher()


@pytest.fixture
def mock_message_subscriber():
    """Create a mock MessageSubscriber for testing."""
    return MockMessageSubscriber()


@pytest.fixture
def mock_status_repository():
    """Create a mock StatusRepository for testing status API endpoints."""
    yield from create_mock_repository("manman.host.api.status.api.StatusRepository")


@pytest.fixture
def mock_game_repository():
    """Create a mock GameRepository for testing game API endpoints."""
    yield from create_mock_repository("manman.host.api.game.api.GameRepository")


@pytest.fixture
def mock_worker_repository():
    """Create a mock WorkerRepository for testing worker DAL API endpoints."""
    yield from create_mock_repository(
        "manman.host.api.worker_dal.worker.WorkerRepository"
    )
