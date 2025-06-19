"""
Shared pytest fixtures and utilities for testing.

This module provides reusable testing utilities that can be used across different test modules.

## Mock Message Infrastructure

This module provides a comprehensive mock infrastructure for testing message-based systems
without requiring actual RabbitMQ connections. The mock implementations follow the same
interfaces as the real RabbitMQ classes but provide additional testing capabilities.

### Core Mock Classes

- `MockMessagePublisher`: Mock implementation of `MessagePublisherInterface`
  - Tracks all published messages for inspection
  - Provides methods to verify message content and call counts
  - Can be cleared between tests for clean state

- `MockMessageSubscriber`: Mock implementation of `MessageSubscriberInterface`
  - Allows queuing test messages to be consumed
  - Tracks consumption calls
  - Provides queue management methods

### Available Fixtures

#### Basic Mocks
- `mock_message_publisher`: Fresh MockMessagePublisher instance
- `mock_message_subscriber`: Fresh MockMessageSubscriber instance

#### Service Mocks (combine publishers/subscribers with service logic)
- `mock_internal_status_pub_service`: InternalStatusInfoPubService with mock publisher
- `mock_external_status_pub_service`: ExternalStatusInfoPubService with mock publisher  
- `mock_command_pub_service`: CommandPubService with mock publisher
- `mock_internal_status_sub_service`: InternalStatusSubService with mock subscriber
- `mock_external_status_sub_service`: ExternalStatusSubService with mock subscriber
- `mock_command_sub_service`: CommandSubService with mock subscriber

#### Repository Mocks
- `mock_status_repository`: Mock for status API endpoints
- `mock_game_repository`: Mock for game API endpoints
- `mock_worker_repository`: Mock for worker API endpoints

### Usage Examples

#### Basic Message Testing
```python
def test_basic_message_flow(mock_message_publisher, mock_message_subscriber):
    # Publish a message
    mock_message_publisher.publish("test message")
    
    # Verify publication
    assert mock_message_publisher.publish_call_count == 1
    assert mock_message_publisher.was_called_with("test message")
    
    # Simulate message reception
    mock_message_subscriber.queue_message("test message")
    messages = mock_message_subscriber.consume()
    assert messages == ["test message"]
```

#### Service Testing
```python
def test_status_service(mock_internal_status_pub_service):
    status = InternalStatusInfo.create(EntityRegistry.WORKER, "test", StatusType.RUNNING)
    mock_internal_status_pub_service.publish_status(status)
    
    # Access underlying mock for verification
    publisher_mock = mock_internal_status_pub_service._publisher
    assert publisher_mock.publish_call_count == 1
```

#### Message Flow Testing
```python
def test_end_to_end_flow(mock_internal_status_pub_service, mock_internal_status_sub_service):
    # Get underlying mocks
    pub_mock = mock_internal_status_pub_service._publisher
    sub_mock = mock_internal_status_sub_service._subscriber
    
    # Publish a status
    status = InternalStatusInfo.create(EntityRegistry.WORKER, "worker-1", StatusType.RUNNING)
    mock_internal_status_pub_service.publish_status(status)
    
    # Simulate message delivery
    published_json = pub_mock.get_last_message()
    sub_mock.queue_message(published_json)
    
    # Consume and verify
    consumed = mock_internal_status_sub_service.get_internal_statuses()
    assert len(consumed) == 1
    assert consumed[0].identifier == "worker-1"
```

#### Testing Complex Systems
```python 
def test_status_processor_with_mocks():
    # Create mock services
    mock_subscriber = MockMessageSubscriber()
    mock_publisher = MockMessagePublisher()
    
    # Queue test messages
    status = InternalStatusInfo.create(EntityRegistry.WORKER, "100", StatusType.RUNNING)
    mock_subscriber.queue_message(status.model_dump_json())
    
    # Create service instances
    sub_service = InternalStatusSubService(mock_subscriber)
    pub_service = ExternalStatusInfoPubService(mock_publisher)
    
    # Inject into system under test using patches
    with patch.object(system, 'subscriber', sub_service), \\
         patch.object(system, 'publisher', pub_service):
        system.process_messages()
        
    # Verify behavior
    assert mock_subscriber.consume_call_count == 1
    assert mock_publisher.publish_call_count == 1
```

### Mock Inspection Methods

#### Publisher Inspection
- `publish_call_count`: Number of times publish() was called
- `published_messages`: List of all published message strings
- `get_last_message()`: Get the most recently published message
- `was_called_with(message)`: Check if a specific message was published
- `clear()`: Reset all tracking data

#### Subscriber Inspection  
- `consume_call_count`: Number of times consume() was called
- `queue_message(msg)`: Add a message to be returned by next consume()
- `queue_messages(msgs)`: Add multiple messages
- `clear_queue()`: Remove all queued messages
- `has_queued_messages()`: Check if messages are waiting

### Best Practices

1. **Use fixtures when possible**: The provided fixtures ensure clean state and proper setup
2. **Clear state between tests**: Use `clear()` methods when reusing mocks across test cases
3. **Verify both sides**: Check that messages are published AND consumed as expected
4. **Test error conditions**: Use mocks to simulate failures and verify error handling
5. **Inspect message content**: Parse JSON messages to verify structure and data
6. **Use service-level mocks**: Prefer testing at the service level rather than raw publisher/subscriber level

See `test_mock_infrastructure_examples.py` for comprehensive usage examples.
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
def mock_internal_status_sub_service(mock_message_subscriber):
    """Create a mock InternalStatusSubService for testing."""
    from manman.repository.message.sub import InternalStatusSubService
    return InternalStatusSubService(mock_message_subscriber)


@pytest.fixture
def mock_external_status_sub_service(mock_message_subscriber):
    """Create a mock ExternalStatusSubService for testing."""
    from manman.repository.message.sub import ExternalStatusSubService
    return ExternalStatusSubService(mock_message_subscriber)


@pytest.fixture
def mock_command_sub_service(mock_message_subscriber):
    """Create a mock CommandSubService for testing."""
    from manman.repository.message.sub import CommandSubService
    return CommandSubService(mock_message_subscriber)


@pytest.fixture
def mock_internal_status_pub_service(mock_message_publisher):
    """Create a mock InternalStatusInfoPubService for testing."""
    from manman.repository.message.pub import InternalStatusInfoPubService
    return InternalStatusInfoPubService(mock_message_publisher)


@pytest.fixture
def mock_external_status_pub_service(mock_message_publisher):
    """Create a mock ExternalStatusInfoPubService for testing."""
    from manman.repository.message.pub import ExternalStatusInfoPubService
    return ExternalStatusInfoPubService(mock_message_publisher)


@pytest.fixture
def mock_command_pub_service(mock_message_publisher):
    """Create a mock CommandPubService for testing."""
    from manman.repository.message.pub import CommandPubService
    return CommandPubService(mock_message_publisher)


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
