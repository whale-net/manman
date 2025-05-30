# Mock Worker and Server Tools

This directory contains mock implementations of the ManMan worker and server services that can be used for development, testing, and system integration without the overhead of running actual game server processes.

## Overview

The mock tools provide the same interfaces and publish the same status messages as the real services, but simulate their behavior without:
- Running actual game server processes
- Installing files via SteamCMD
- Creating real system processes

## Components

### MockProcessBuilder
- Simulates the ProcessBuilder lifecycle without executing real processes
- Supports all ProcessBuilderStatus states (NOTSTARTED, INIT, RUNNING, STOPPED)
- Handles parameters, stdin, and command rendering
- Uses timers to simulate realistic state transitions

### MockServer
- Simulates Server behavior without executing real processes
- Uses MockProcessBuilder instead of real ProcessBuilder
- Publishes all expected status updates (CREATED, INITIALIZING, RUNNING, COMPLETE)
- Handles command execution and lifecycle management
- Skips steamcmd installation but maintains API compatibility

### MockWorkerService
- Simulates WorkerService behavior without real work
- Creates MockServer instances instead of real servers
- Handles command processing and server lifecycle management
- Publishes worker status updates and maintains heartbeat

## Usage

### Mock Worker Service

Start a mock worker that simulates worker behavior:

```bash
mock-worker start-mock-worker --host-url http://localhost:8000
```

Environment variables:
- `MANMAN_HOST_URL` - URL of the host API
- `MANMAN_WORKER_INSTALL_DIRECTORY` - Directory for mock installations (default: ./data)
- `MANMAN_RABBITMQ_HOST` - RabbitMQ host
- `MANMAN_RABBITMQ_PORT` - RabbitMQ port
- `MANMAN_RABBITMQ_USER` - RabbitMQ username
- `MANMAN_RABBITMQ_PASSWORD` - RabbitMQ password
- `APP_ENV` - Application environment (affects RabbitMQ virtual host)

### Mock Server

Start a standalone mock server for a specific game server configuration:

```bash
mock-server start-mock-server --host-url http://localhost:8000 --game-server-config-id 1 --worker-id 1
```

Options:
- `--host-url` - URL of the host API
- `--game-server-config-id` - ID of the game server configuration to mock
- `--worker-id` - Worker ID to associate with this mock server (default: 1)
- `--install-directory` - Directory for mock installations (default: ./data)

## Benefits

1. **Fast Development**: No need to wait for real game servers to start/stop
2. **Reliable Testing**: Predictable behavior without external dependencies
3. **Resource Efficient**: No actual processes or file operations
4. **Status Publishing**: Full integration with status monitoring systems
5. **Command Handling**: Supports all the same commands as real services

## Integration

The mock tools integrate seamlessly with the existing ManMan infrastructure:
- Publish status updates to the same RabbitMQ exchanges
- Use the same API endpoints for configuration
- Follow the same command and status message formats
- Support the same routing keys and queue names

This makes them ideal for:
- Development environments where you don't need real game servers
- Integration testing of the host services
- Load testing of the message processing systems
- Debugging command and status flows

## Development Notes

The mock implementations are designed to be as close to the real implementations as possible while avoiding actual work. They:
- Use the same class interfaces and method signatures
- Publish status messages at the same lifecycle points
- Handle the same commands and parameters
- Follow the same error handling patterns

This ensures that code developed and tested with the mock services will work correctly with the real services.