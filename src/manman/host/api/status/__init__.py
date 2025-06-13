from .api import router

__all__ = ["router", "create_app"]


def create_app():
    """Factory function to create the Status API FastAPI application."""
    from fastapi import FastAPI

    from manman.host.api.shared import add_health_check

    app = FastAPI(title="ManMan Status API", root_path="/status")
    app.include_router(router)
    add_health_check(app)
    return app
