# RabbitMQ Connection Recovery

This implementation addresses connection dropping issues that could cause services to become unreachable.

## Problem

The original implementation used basic AMQPStorm connections without heartbeat configuration or connection recovery mechanisms. This led to:

- Silent connection drops that made services unreachable
- No automatic reconnection when connections were lost
- Services appearing to run but unable to receive commands

## Solution

### RobustConnection Wrapper

A new `RobustConnection` class provides:

- **AMQP Heartbeat Configuration**: Prevents silent connection drops (default 30s)
- **Automatic Health Monitoring**: Continuously checks connection health
- **Exponential Backoff Reconnection**: Automatic reconnection with configurable retry attempts
- **Connection Callbacks**: Monitoring hooks for operational visibility

### Updated Connection Initialization

The `init_rabbitmq()` function now:
- Uses `RobustConnection` wrapper for enhanced reliability
- Configures heartbeat intervals to prevent connection drops
- Provides connection recovery without service restart
- Maintains backward compatibility with existing code

### Connection Health Checking

Services now benefit from:
- Connection validation before use via `get_connection()`
- Automatic reconnection on connection failures
- Graceful error handling for temporary network issues
- Operational callbacks for monitoring connection state

## Usage

```python
# Initialize with robust connection (backward compatible)
init_rabbitmq(
    host='localhost',
    port=5672,
    username='guest',
    password='guest',
    heartbeat_interval=30,  # New: AMQP heartbeat
    max_reconnect_attempts=5,  # New: Retry configuration
    reconnect_delay=1.0  # New: Delay between attempts
)

# Use normally - transparently benefits from robustness
connection = get_rabbitmq_connection()
publisher = RabbitPublisher(connection, binding_config)
```

## Benefits

- **Prevents Unreachable Services**: Connection drops no longer make services unreachable
- **Maintains Availability**: Services remain functional during temporary network issues
- **Operational Visibility**: Connection lost/restored callbacks for monitoring
- **Zero Downtime**: Connection recovery without service restart
- **Backward Compatible**: Existing code works without changes

## Testing

Comprehensive test suites validate:
- Robust connection functionality
- Integration with publishers/subscribers
- Connection recovery scenarios
- Util function compatibility
- End-to-end connection handling
