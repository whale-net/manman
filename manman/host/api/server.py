from fastapi import APIRouter
import sqlalchemy
from sqlalchemy.sql.functions import current_timestamp

from manman.models import GameServerInstance
from manman.util import get_session

router = APIRouter()


@router.post("/server/create")
async def server_create(body: GameServerInstance) -> GameServerInstance:
    with get_session() as sess:
        # TODO validate gaem_server_config_id exists
        server = GameServerInstance(game_server_config_id=body.game_server_config_id)
        sess.add(server)
        sess.flush()
        sess.expunge(server)
        sess.commit()

    return server


@router.put("/server/shutdown")
async def server_shutdown(instance: GameServerInstance) -> GameServerInstance:
    with get_session() as sess:
        # TODO - move check that it's not already dead to trigger
        # DB is right place to do that, but doing this so I can learn
        stmt = sqlalchemy.select(GameServerInstance).where(
            GameServerInstance.game_server_instance_id
            == instance.game_server_instance_id
        )
        current_instance = sess.scalar(stmt)
        if current_instance is None:
            raise Exception("instance is None")
        if current_instance.end_date is not None:
            raise Exception("instance already closed on server")

        current_instance.end_date = current_timestamp()
        sess.add(current_instance)
        sess.flush()
        sess.refresh(current_instance)
        sess.expunge(current_instance)
        sess.commit()

    print(current_instance.end_date)
    return current_instance


#     return server
