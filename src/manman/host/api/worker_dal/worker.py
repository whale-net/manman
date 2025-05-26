from fastapi import APIRouter, HTTPException

from manman.models import Worker
from manman.repository.database import WorkerRepository

# TODO - add authcz
# TODO - this should have a better prefix taht is different from the server api
router = APIRouter(
    prefix="/worker"
)  # , dependencies=[Depends(has_basic_worker_authz)])


# TODO - fix this
# @router.get("/health")
# async def health() -> str:
#     return "OK"


@router.post("/create")
async def worker_create() -> Worker:
    repository = WorkerRepository()
    return repository.create_worker()


@router.put("/shutdown")
async def worker_shutdown(instance: Worker) -> Worker:
    repository = WorkerRepository()
    result = repository.shutdown_worker(instance.worker_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Worker not found")
    return result


@router.put("/shutdown/other")
async def worker_shutdown_other(instance: Worker):
    repository = WorkerRepository()
    repository.close_other_workers(instance.worker_id)


# heartbeat
@router.get("/heartbeat")
async def worker_heartbeat(instance: Worker):
    repository = WorkerRepository()
    try:
        result = repository.update_worker_heartbeat(instance.worker_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
