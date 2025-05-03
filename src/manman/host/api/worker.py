import sqlalchemy
from fastapi import APIRouter
from sqlalchemy.sql.functions import current_timestamp

from manman.models import Worker
from manman.repository.workerdal import close_other_workers
from manman.util import get_sqlalchemy_session

# TODO - add authcz
# TODO - this should have a better prefix taht is different from the server api
router = APIRouter(
    prefix="/workerdal"
)  # , dependencies=[Depends(has_basic_worker_authz)])


@router.post("/worker/create")
async def worker_create() -> Worker:
    with get_sqlalchemy_session() as sess:
        worker = Worker()
        sess.add(worker)
        sess.flush()
        sess.expunge(worker)
        sess.commit()

    return worker


@router.put("/worker/shutdown")
async def worker_shutdown(instance: Worker) -> Worker:
    with get_sqlalchemy_session() as sess:
        # TODO - move check that it's not already dead to trigger
        # DB is right place to do that, but doing this so I can learn
        stmt = sqlalchemy.select(Worker).where(Worker.worker_id == instance.worker_id)
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

    # print(current_instance.end_date)
    return current_instance


@router.put("/worker/shutdown/other")
async def worker_shutdown_other(instance: Worker):
    # TODO - make this work 3/16 7 pm
    close_other_workers(instance.worker_id)
