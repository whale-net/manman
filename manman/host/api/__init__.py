from fastapi import FastAPI

from .server import router as server_router
from .worker import router as worker_router

# TODO - create second fastapp for internal/external if desired
# all code is going to be in deployable anyway
fastapp = FastAPI()
fastapp.include_router(server_router)
fastapp.include_router(worker_router)
