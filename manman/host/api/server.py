from fastapi import APIRouter

from manman.models import GameServerInstance
from manman.util import get_session

router = APIRouter()


@router.post("/server/create")
async def server_create(game_server_config_id: int) -> GameServerInstance:
    with get_session() as sess:
        server = GameServerInstance(game_server_config_id=game_server_config_id)
        sess.add(server)
        sess.flush()
        sess.expunge(server)
        sess.commit()

    return server
