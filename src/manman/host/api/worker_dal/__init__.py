from .server import router as server_router
from .worker import router as worker_router

__all__ = ["worker_router", "server_router", "create_app"]


def create_app():
    """Factory function to create the Worker DAL API FastAPI application."""
    from fastapi import FastAPI

    from manman.host.api.shared import add_health_check

    app = FastAPI(
        title="ManMan Worker DAL API",
        root_path="/workerdal",  # Configure root path for reverse proxy
    )
    app.include_router(server_router)
    app.include_router(worker_router)
    # For worker DAL, health check should be at the root level since root_path handles the /workerdal prefix
    add_health_check(app)
    return app
