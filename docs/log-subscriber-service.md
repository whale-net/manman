# Log Subscriber Service

The Log Subscriber Service is a new component that enables transparent pass-through of log messages from server instances while preserving the original service identity. This allows for centralized log collection and potentially exposing logs to web interfaces in the future.

## Overview

The service consists of several key components:

1. **LogMessage Model** - A new message type for log data with service metadata
2. **Enhanced log_stream utility** - Modified to optionally publish log messages
3. **LogSubscriberService** - Main service that consumes and re-emits logs
4. **Integration with ProcessBuilder** - Captures game server logs automatically

## Key Features

- **Preserves Original Service Identity**: Logs are re-emitted as if they came from the original service, not the subscriber
- **Transparent Pass-Through**: Acts as a lightweight proxy without modifying log content
- **Source Tracking**: Distinguishes between stdout and stderr log sources
- **Error Handling**: Graceful degradation when message processing fails
- **Non-Blocking**: Uses existing non-blocking message consumption patterns

## Architecture

### Message Flow

1. **Log Capture**: Game server processes output logs via `ProcessBuilder.read_output()`
2. **Log Publishing**: Enhanced `log_stream()` publishes `LogMessage` objects to RabbitMQ
3. **Log Consumption**: `LogSubscriberService` consumes log messages from the message queue
4. **Log Re-emission**: Logs are re-emitted using loggers named after the original service

### Message Types

A new `LOG` message type has been added to `MessageTypeRegistry`:

```python
class MessageTypeRegistry(StrEnum):
    STATUS = "status"
    COMMAND = "command"
    LOG = "log"        # New log message type
```

### LogMessage Model

```python
class LogMessage(ManManBase, table=False):
    entity_type: EntityRegistry      # Original service entity type
    identifier: str                  # Original service identifier
    timestamp: datetime.datetime     # Log timestamp
    log_level: str                  # Log level (INFO, ERROR, etc.)
    message: str                    # Log message content
    source: str                     # Log source (stdout, stderr)
```

## Usage

### Running the Log Subscriber Service

The service can be started using the new CLI command:

```bash
python -m manman.host.main start-log-subscriber \
    --rabbitmq-host localhost \
    --rabbitmq-port 5672 \
    --rabbitmq-username guest \
    --rabbitmq-password guest
```

All standard RabbitMQ connection parameters are supported, including SSL options.

### Configuration

The service uses environment variables for configuration:

- `MANMAN_RABBITMQ_HOST` - RabbitMQ host
- `MANMAN_RABBITMQ_PORT` - RabbitMQ port  
- `MANMAN_RABBITMQ_USER` - RabbitMQ username
- `MANMAN_RABBITMQ_PASSWORD` - RabbitMQ password
- `MANMAN_RABBITMQ_ENABLE_SSL` - Enable SSL (default: false)
- `MANMAN_RABBITMQ_SSL_HOSTNAME` - SSL hostname for verification
- `APP_ENV` - Application environment (dev/staging/prod)
- `MANMAN_LOG_OTLP` - Enable OpenTelemetry logging (default: false)

### Integration with Worker Services

Game server instances automatically capture and publish logs when:

1. A `LogMessagePubService` is configured in the `Server` class
2. The `ProcessBuilder` is initialized with log publishing parameters
3. Process output is read via `ProcessBuilder.read_output()`

This integration is automatic and requires no additional configuration.

## Implementation Details

### Enhanced log_stream Function

The `log_stream()` utility function has been enhanced with optional log publishing:

```python
def log_stream(
    stream: io.BufferedReader | None,
    prefix: str | None = None,
    logger: logging.Logger = logger,
    max_lines: int | None = None,
    log_publisher=None,           # Optional LogMessagePubService
    entity_type=None,             # Required if log_publisher provided
    identifier: str | None = None, # Required if log_publisher provided
):
```

When `log_publisher` is provided, each log line is published as a `LogMessage` while still being logged normally.

### ProcessBuilder Integration

The `ProcessBuilder` class now accepts optional log publishing parameters:

```python
pb = ProcessBuilder(
    executable=executable_path,
    log_publisher=self._log_publisher,      # LogMessagePubService instance
    entity_type=self.service_entity_type,   # EntityRegistry value
    identifier=self.identifier,             # Service identifier string
)
```

### LogSubscriberService

The main service that processes log messages:

```python
class LogSubscriberService:
    def __init__(self, rabbitmq_connection: Connection)
    def run(self)                    # Main processing loop
    def stop(self)                   # Graceful shutdown
    def _process_log_messages(self)  # Process available messages
    def _re_emit_log_message(self, log_message: LogMessage)  # Re-emit logs
```

## Error Handling

The service includes comprehensive error handling:

- **Connection Failures**: RabbitMQ connection issues are logged and don't crash the service
- **Message Parsing**: Invalid log messages are logged and skipped
- **Log Re-emission**: Failures in re-emitting logs are logged but don't affect other messages
- **Graceful Shutdown**: Service can be stopped cleanly via keyboard interrupt

## Future Enhancements

This implementation provides the foundation for several future features:

1. **Web Interface Integration**: Additional subscribers could expose logs to web pages
2. **Real-time Log Streaming**: WebSocket-based log streaming for real-time monitoring
3. **Log Filtering and Search**: Enhanced processing for log filtering and search capabilities
4. **Log Aggregation**: Multiple log streams could be aggregated and correlated
5. **Log Level Parsing**: Enhanced parsing of log levels from message content

## Testing

The implementation includes comprehensive testing:

- **Unit Tests**: Individual component testing with mocks
- **Integration Tests**: End-to-end message flow validation
- **Error Handling Tests**: Verification of graceful error handling

Run tests with:
```bash
python /tmp/test_log_subscriber.py
python /tmp/test_log_subscriber_integration.py  
python /tmp/test_end_to_end_log_flow.py
```

## Minimal Change Philosophy

This implementation follows the "minimal change" philosophy by:

- **Leveraging Existing Infrastructure**: Uses established RabbitMQ patterns and message types
- **Non-Breaking Changes**: All existing functionality continues to work unchanged  
- **Optional Integration**: Log publishing is optional and doesn't affect normal operation
- **Following Established Patterns**: Mirrors existing service and messaging patterns
- **Incremental Enhancement**: Builds upon existing `log_stream()` and `ProcessBuilder` functionality

The service can be deployed and tested independently without affecting existing game server operations.