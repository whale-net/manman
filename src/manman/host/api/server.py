import sqlalchemy
from fastapi import APIRouter
from sqlalchemy.sql.functions import current_timestamp

from manman.models import GameServer, GameServerConfig, GameServerInstance
from manman.util import get_sqlalchemy_session

# TODO - add authcz
# TODO - this should have a better prefix taht is different from the worker api
router = APIRouter(
    prefix="/workerdal"
)  # , dependencies=[Depends(has_basic_worker_authz)])


@router.post("/server/instance/create")
async def server_instance_create(body: GameServerInstance) -> GameServerInstance:
    with get_sqlalchemy_session() as sess:
        # TODO validate gaem_server_config_id exists
        server = GameServerInstance(game_server_config_id=body.game_server_config_id)
        sess.add(server)
        sess.flush()
        sess.expunge(server)
        sess.commit()

    return server


@router.put("/server/instance/shutdown")
async def server_instance_shutdown(instance: GameServerInstance) -> GameServerInstance:
    with get_sqlalchemy_session() as sess:
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

    return current_instance


@router.get("/server/config/{id}")
async def server_config(id: int) -> GameServerConfig:
    with get_sqlalchemy_session() as sess:
        config = sess.get_one(GameServerConfig, id)
        sess.expunge(config)
    return config


@router.get("/server/{id}")
async def server(id: int) -> GameServer:
    with get_sqlalchemy_session() as sess:
        config = sess.get_one(GameServer, id)
        sess.expunge(config)
    return config
