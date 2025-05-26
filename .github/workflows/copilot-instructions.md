# GitHub Copilot Instructions for ManMan Project

## Project Overview
ManMan is a game server management system that orchestrates Steam-based game servers through a distributed worker architecture. The system uses RabbitMQ for messaging, PostgreSQL for persistence, FastAPI for REST APIs, and Kubernetes for deployment.

**Core Components:**
- **Host Service**: Central management API and orchestration (see `src/manman/host/`)
- **Worker Service**: Distributed workers that manage game server instances (see `src/manman/worker/`)
- **Messaging System**: RabbitMQ-based command/status messaging (see `src/manman/repository/rabbitmq.py`)
- **Database**: PostgreSQL with SQLModel ORM (see `src/manman/models.py`)

## Code Style Guidelines
- Use Python 3.11+ with strict type hints for all function parameters and return types
- Follow PEP 8 style guidelines
- Use descriptive variable and function names
- Add comprehensive docstrings to all classes and methods using Google-style format
- Use `logging` module for all logging with appropriate levels
- Prefer composition over inheritance
- Use dependency injection for all external dependencies

## Discovering Current Implementation

**IMPORTANT: Always examine the actual codebase before making assumptions.**

When working on any feature:
1. **Check `src/manman/models.py`** for current model definitions and relationships
2. **Browse `src/manman/host/api/`** for existing API patterns and endpoints
3. **Review `src/manman/repository/`** for current data access implementations
4. **Examine `src/manman/worker/`** for worker service patterns
5. **Look at `tests/`** for usage examples and test patterns
6. **Check `alembic/versions/`** for current database schema
7. **Review recent commits** to understand current development patterns

**Never assume static information in these instructions is current - always verify against the actual code.**

## Architecture Patterns
- **Repository Pattern**: All data access through repository classes (e.g., `rabbitmq.py`)
- **Abstract Base Classes**: Use ABC for interfaces (MessagePublisher, MessageSubscriber)
- **Dependency Injection**: Pass connections and dependencies through constructors
- **Service Layer**: Business logic in service classes
- **Command Pattern**: Commands for game server operations
- **Observer Pattern**: Status updates through messaging
- **Factory Pattern**: TODO - Add specific factory patterns used

## Key Models and Data Structures

### Primary Models Location
- **All models are defined in `src/manman/models.py`** - Always reference this file for current model definitions
- **Database schema**: Use Alembic migrations in `alembic/versions/` for current schema
- **API models**: Check FastAPI route definitions for request/response schemas

### Core Model Categories
When working with models, examine the actual definitions in `src/manman/models.py` to understand:
- Database table models (inherit from SQLModel with `table=True`)
- Message/communication models (pydantic models for RabbitMQ)
- API request/response models
- Configuration models

### Model Relationships
- Examine foreign key relationships and `Relationship()` definitions in the models file
- Check migration files for constraint definitions and indexes

## Repository Layer (`src/manman/repository/`)

### RabbitMQ Messaging
- `MessagePublisher` (ABC): Interface for publishing messages
- `MessageSubscriber` (ABC): Interface for consuming messages
- `RabbitStatusPublisher`: Publishes StatusInfo to fanout exchange
- `RabbitCommandSubscriber`: Subscribes to Command messages

**Messaging Patterns:**
- Use fanout exchanges for broadcasting status updates
- Use direct exchanges for targeted command routing
- Auto-delete queues for temporary consumers
- Proper connection and channel management with shutdown procedures

## API Layer (`src/manman/host/api/`)
- FastAPI-based REST endpoints
- Check route files in `src/manman/host/api/` for current endpoint implementations
- Use OpenAPI schema (available at `/docs` endpoint) for current API documentation
- Authentication patterns: Examine middleware and dependencies in API modules

## Worker System (`src/manman/worker/`)

### Core Components
Check `src/manman/worker/` directory for current implementations:
- Main worker service orchestration
- Individual game server management classes
- Steam integration components
- Process management utilities

### Process Management
- Examine `src/manman/processbuilder.py` for current process management patterns
- Check worker service files for status monitoring implementations
- Look for signal handling and cleanup procedures in worker modules

## Testing Guidelines
- Write unit tests for all new functionality using pytest
- Mock external dependencies (RabbitMQ connections, database, Steam APIs)
- Use factories for test data creation
- Test error conditions and edge cases
- Minimum 80% code coverage requirement
- Integration tests for API endpoints
- TODO: Add specific test patterns and fixtures

## Error Handling
- Log errors using the standard logging module with contextual information
- Gracefully handle connection failures to RabbitMQ and database
- Implement proper shutdown procedures for all resources
- Use structured exception handling with specific exception types
- Retry logic for transient failures
- Circuit breaker pattern for external service calls

## RabbitMQ Conventions

### Exchange Patterns
- **Fanout exchanges**: For broadcasting status updates to multiple consumers
- **Direct exchanges**: For point-to-point command routing
- **Topic exchanges**: TODO - Add topic exchange patterns if used

### Queue Naming
- Format: `{service}.{instance}.{purpose}` (e.g., `worker.123.commands`)
- Use auto-delete queues for temporary consumers
- Use durable queues for persistent message handling

### Message Routing
- Status messages: Published to fanout exchange, no routing key needed
- Commands: Use worker ID or instance ID as routing key
- TODO: Add specific routing key patterns

## Database Conventions

### Schema Management
- Use Alembic for all database migrations
- Schema name: `manman`
- Follow snake_case for table and column names
- Use meaningful foreign key constraint names
- Add appropriate indexes for query performance

### SQLModel Patterns
- Inherit from `Base` class with schema metadata
- Use `Field()` for column definitions with proper constraints
- Define relationships with `Relationship()`
- Use `table=True` for database tables
- Use separate models for API serialization if needed

## Security Considerations
- TODO: Add authentication requirements (OAuth2, JWT, etc.)
- TODO: Add data validation rules and input sanitization
- TODO: Add rate limiting patterns
- TODO: Add sensitive data handling guidelines (secrets, tokens)
- TODO: Add network security requirements

## Performance Guidelines
- Use non-blocking message retrieval (`get_commands()` should not block)
- Implement proper connection pooling for database and RabbitMQ
- Use background tasks for long-running operations
- Monitor memory usage in worker processes
- Implement graceful degradation for high load scenarios
- TODO: Add specific performance targets and SLAs

## Environment Configuration

### Required Environment Variables
```bash
# Host Service
MANMAN_HOST_URL=http://localhost:8000
MANMAN_POSTGRES_URL=postgresql+psycopg2://user:pass@host:port/db
MANMAN_RABBITMQ_URL=amqp://user:pass@host:port/vhost

# Worker Service
MANMAN_WORKER_INSTALL_DIRECTORY=./data
MANMAN_WORKER_SA_CLIENT_ID=TODO
MANMAN_WORKER_SA_CLIENT_SECRET=TODO

# Development
APP_ENV=dev|staging|prod
MANMAN_BUILD_POSTGRES_ENV=default|custom
MANMAN_BUILD_RABBITMQ_ENV=default|custom
MANMAN_ENABLE_EXPERIENCE_API=true|false
```

## Development Workflow

### Local Development with Tilt
- Use `tilt up` for local Kubernetes development
- PostgreSQL available on localhost:5432
- RabbitMQ available on localhost:5672 (management: 15672)
- Hot reload enabled for code changes

### Docker Development
- Base image: TODO - Add base image info
- Multi-stage builds for optimization
- Build args: `COMPILE_CORES=2`

### Common Code Patterns

#### Finding Current Implementation Patterns
When implementing new features, always check existing code first:
- Examine `src/manman/models.py` for current model definitions and relationships
- Look at existing API routes in `src/manman/host/api/` for patterns
- Check `src/manman/repository/` for data access patterns
- Review `src/manman/worker/` for worker implementation patterns
- Examine tests in `tests/` for usage examples

#### Creating a RabbitMQ Publisher
```python
# Check src/manman/repository/rabbitmq.py for current implementation
# For status broadcasting (fanout)
publisher = RabbitStatusPublisher(
    connection=connection,
    exchange="status-exchange"
)
```

#### Creating a RabbitMQ Subscriber
```python
# Check src/manman/repository/rabbitmq.py for current implementation
subscriber = RabbitCommandSubscriber(
    connection=connection,
    exchange="command-exchange",
    queue_name="worker-commands-123"
)
```

#### Database Operations
```python
# Always check src/manman/models.py for current model structure
# Example based on typical SQLModel patterns:
instance = GameServerInstance(
    game_server_config_id=config_id,
    worker_id=worker_id
)
```

#### Error Handling Pattern
```python
try:
    # Operation
    result = operation()
except SpecificException as e:
    logger.exception("Contextual error message: %s", e)
    # Handle specific error
except Exception as e:
    logger.exception("Unexpected error: %s", e)
    # Handle general error
finally:
    # Cleanup resources
    cleanup()
```

## Steam Integration

### SteamCMD Usage
- Install games using SteamCMD wrapper
- Cache installations in `MANMAN_WORKER_INSTALL_DIRECTORY`
- Handle Steam authentication for protected content
- TODO: Add specific Steam API patterns

### Game Server Management
- Each game server runs in its own process
- Monitor process health and restart as needed
- Handle game-specific configuration files
- TODO: Add game-specific configuration patterns

## Kubernetes Deployment

### Helm Charts
- Chart location: `charts/manman-host/`
- Use Helm for all Kubernetes deployments
- Environment-specific value files
- TODO: Add specific deployment patterns

### Service Discovery
- Use Kubernetes DNS for service discovery
- Format: `{service}.{namespace}.svc.cluster.local`
- Example: `postgres-dev.manman-dev.svc.cluster.local`

## Dependencies
- **amqpstorm**: RabbitMQ client library
- **fastapi**: Web framework for APIs
- **sqlmodel**: Database ORM (SQLAlchemy + Pydantic)
- **typer**: CLI framework
- **uvicorn**: ASGI server
- **alembic**: Database migration tool
- **pytest**: Testing framework
- TODO: Add version constraints and compatibility requirements

## Documentation Requirements
- All public methods must have Google-style docstrings
- Include parameter descriptions with types
- Document return types and possible exceptions
- Add usage examples for complex functionality
- Update this instruction file when adding new patterns
- TODO: Add API documentation generation (OpenAPI/Swagger)

## Common Anti-Patterns to Avoid
- Don't use synchronous blocking calls in async contexts
- Don't create database connections in loops
- Don't hardcode configuration values
- Don't ignore exceptions or use bare `except:` clauses
- Don't commit database transactions in loops
- Don't create RabbitMQ channels without proper cleanup
- Avoid circular imports between modules

## Monitoring and Observability
- TODO: Add logging patterns and structured logging
- TODO: Add metrics collection (Prometheus/Grafana)
- TODO: Add health check endpoints
- TODO: Add distributed tracing requirements

## Maintaining These Instructions

**These instructions emphasize discovery over documentation for good reason:**

1. **Always check the actual code** - File references (like `src/manman/models.py`) are more reliable than hardcoded schemas
2. **Use exploration patterns** - Instead of listing specific classes, the instructions tell you where to look
3. **Reference live documentation** - API schemas at `/docs`, database migrations in `alembic/versions/`
4. **Focus on patterns over specifics** - Architectural patterns and conventions remain stable longer than implementation details

**When updating these instructions:**
- Add new architectural patterns or conventions
- Update file/directory references if the project structure changes significantly
- Add discovery guidance for new subsystems
- Remove outdated TODOs when patterns are established
- Keep specific implementation details minimal - let the code be the source of truth

---
*This instruction set should be updated as the project evolves and new patterns emerge.*
