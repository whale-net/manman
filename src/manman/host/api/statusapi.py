# The status API stub
from fastapi import APIRouter

router = APIRouter(prefix="/status")


@router.get("/health")
async def health() -> str:
    return "OK"
