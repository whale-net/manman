"""
ASGI application factories for production deployment with Gunicorn.

These factories create the FastAPI applications that Gunicorn can serve.
"""

import os

from fastapi import FastAPI


def create_experience_app() -> FastAPI:
    """Create the Experience API application."""
    from manman.host.api.experience import router as experience_router
    from manman.host.api.shared import add_health_check

    app = FastAPI(title="ManMan Experience API", root_path="/experience")
    app.include_router(experience_router)
    add_health_check(app)
    return app


def create_status_app() -> FastAPI:
    """Create the Status API application."""
    from manman.host.api.shared import add_health_check
    from manman.host.api.status import router as status_router

    app = FastAPI(title="ManMan Status API", root_path="/status")
    app.include_router(status_router)
    add_health_check(app)
    return app


def create_worker_dal_app() -> FastAPI:
    """Create the Worker DAL API application."""
    from manman.host.api.shared import add_health_check
    from manman.host.api.worker_dal import server_router, worker_router

    app = FastAPI(
        title="ManMan Worker DAL API",
        root_path="/workerdal",
    )
    app.include_router(server_router)
    app.include_router(worker_router)
    add_health_check(app)
    return app


# Application instances for Gunicorn
# Set SERVICE_NAME environment variable to specify which app to serve
service_name = os.getenv("SERVICE_NAME", "experience-api")

if service_name == "experience-api":
    app = create_experience_app()
elif service_name == "status-api":
    app = create_status_app()
elif service_name == "worker-dal-api":
    app = create_worker_dal_app()
else:
    raise ValueError(f"Unknown service name: {service_name}")
