from fastapi import FastAPI

from .experience import router as experience_router
from .status import router as status_router
from .worker_dal import server_router, worker_router

# External facing app (experience + status APIs)
fastapp = FastAPI()
fastapp.include_router(experience_router)
fastapp.include_router(status_router)

# Worker DAL APIs (typically used by worker services)
worker_dal_app = FastAPI(
    title="ManMan Worker DAL API",
    root_path="/workerdal",
)
worker_dal_app.include_router(server_router)
worker_dal_app.include_router(worker_router)

# Internal app that combines all endpoints for internal access
internal_app = FastAPI(title="ManMan Internal API")
internal_app.include_router(experience_router)
internal_app.include_router(status_router)
internal_app.include_router(server_router)
internal_app.include_router(worker_router)
