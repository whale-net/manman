from fastapi import FastAPI
from .server import router as server_router

fastapp = FastAPI()
fastapp.include_router(server_router)
