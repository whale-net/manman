# The status API - read-only queries for status information

from fastapi import APIRouter, HTTPException
from sqlalchemy import desc
from sqlmodel import select

from manman.models import StatusInfo
from manman.util import get_sqlalchemy_session

router = APIRouter(prefix="/status")


# status for a worker id
@router.get(
    "/worker/{worker_id}",
)
async def get_worker_status(
    worker_id: int,
) -> StatusInfo:
    with get_sqlalchemy_session() as sess:
        instances = sess.exec(
            select(StatusInfo)
            .where(StatusInfo.worker_id == worker_id)
            .order_by(desc(StatusInfo.as_of))
            .limit(1)
        ).first()
        if not instances:
            raise HTTPException(status_code=404, detail="Worker not found")
        return instances


# status for a single game server instance
@router.get(
    "/instance/{game_server_instance_id}",
)
async def get_game_server_instance(
    game_server_instance_id: int,
) -> StatusInfo:
    with get_sqlalchemy_session() as sess:
        instance = sess.exec(
            select(StatusInfo)
            .where(StatusInfo.game_server_instance_id == game_server_instance_id)
            .order_by(desc(StatusInfo.as_of))
            .limit(1)
        ).first()
        if instance is None:
            raise HTTPException(status_code=404, detail="Instance not found")
        return instance
