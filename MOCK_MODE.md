# Mock Mode Documentation

This document describes the mock mode functionality that has been integrated into the ManMan worker services.

## Overview

Mock mode allows you to run ManMan worker services without executing actual game server processes. This is useful for:

- **Development**: Fast iteration without waiting for real game servers
- **Testing**: Predictable behavior without external dependencies  
- **Integration Testing**: Testing message flows and command handling
- **Resource Efficiency**: No actual processes or file operations

## Usage

### Command Line

Run the worker service in mock mode:

```bash
worker start --mock-mode --host-url http://localhost:8000
```

All other worker command line options work the same way. The `--mock-mode` flag is the only addition.

### Environment Variables

You can also set the mock mode using environment variables if needed (though the command line flag is recommended):

```bash
export MANMAN_HOST_URL=http://localhost:8000
export MANMAN_WORKER_INSTALL_DIRECTORY=./data
export MANMAN_RABBITMQ_HOST=localhost
export MANMAN_RABBITMQ_PORT=5672
export MANMAN_RABBITMQ_USER=guest
export MANMAN_RABBITMQ_PASSWORD=guest

worker start --mock-mode
```

## How It Works

### ProcessBuilder Mock Mode

When `mock_mode=True` is passed to `ProcessBuilder`:

- **No actual processes are spawned**
- Status transitions are simulated with timers
- All the same interfaces and methods are available
- Stdin/stdout operations are logged but don't interact with real processes
- Process lifecycle (NOTSTARTED → INIT → RUNNING → STOPPED) is simulated

### Server Mock Mode

When `mock_mode=True` is passed to `Server`:

- Uses `ProcessBuilder` in mock mode
- **Skips SteamCMD installation** (`should_update` is ignored for SteamCMD)
- All status messages and RabbitMQ integration work the same
- Command handling (STOP, STDIN) works the same
- Server lifecycle management is identical

### WorkerService Mock Mode

When `mock_mode=True` is passed to `WorkerService`:

- Creates `Server` instances in mock mode
- All worker management functionality works the same
- Heartbeat, status publishing, and command processing are unchanged
- Server creation and lifecycle management work identically

## What's Different in Mock Mode

### Faster Operation
- No waiting for real game server startup/shutdown
- No SteamCMD download/installation delays  
- Configurable timing via `stdin_delay_seconds` (defaults to 20s, often set lower for testing)

### Same Interfaces
- All the same status messages are published
- Same RabbitMQ routing keys and exchanges
- Same command handling and responses
- Same API calls and error handling

### What's Skipped
- No actual process execution
- No SteamCMD installation
- No file system operations for game servers
- No network ports are bound by game servers

## Testing

The mock mode functionality is tested in `tests/test_mock_implementations.py`. The tests verify:

- ProcessBuilder state transitions work correctly in mock mode
- Server initialization works with mock mode enabled
- WorkerService passes mock mode through to servers
- All interfaces remain compatible

## Migration from Separate Mock Classes

Previously, there were separate `MockProcessBuilder`, `MockServer`, and `MockWorkerService` classes. These have been removed in favor of the integrated mock mode approach:

### Before (deprecated)
```python
from manman.mock.processbuilder import MockProcessBuilder
pb = MockProcessBuilder("executable")
```

### After (current)
```python  
from manman.worker.processbuilder import ProcessBuilder
pb = ProcessBuilder("executable", mock_mode=True)
```

This approach eliminates code duplication while providing the same functionality.

## Benefits

1. **Reduced Code Duplication**: Single codebase with mode parameter instead of duplicate classes
2. **Better Maintainability**: Changes to core logic automatically apply to mock mode
3. **Consistent Interfaces**: Identical APIs between normal and mock modes
4. **Easy Testing**: Simple parameter change enables mock behavior
5. **Resource Efficient**: Fast development and testing cycles

## Examples

### Basic Mock Mode Worker
```bash
# Start a mock worker that simulates game server behavior
worker start --mock-mode --host-url http://localhost:8000
```

### Integration Testing
```python
# Create a worker service in mock mode for testing
service = WorkerService(
    install_dir="/tmp/test",
    host_url="http://localhost:8000", 
    sa_client_id=None,
    sa_client_secret=None,
    rabbitmq_connection=rabbitmq_conn,
    mock_mode=True,  # Enable mock mode
)
```

### Unit Testing
```python
# Test ProcessBuilder behavior without real processes
pb = ProcessBuilder("game_server.exe", mock_mode=True, stdin_delay_seconds=1)
pb.run()
assert pb.status == ProcessBuilderStatus.INIT
```

This mock mode integration provides all the benefits of the previous separate mock classes while eliminating code duplication and improving maintainability.