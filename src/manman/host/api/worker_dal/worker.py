import logging

from fastapi import APIRouter, HTTPException

from manman.exceptions import WorkerAlreadyClosedException
from manman.models import StatusInfo, StatusType, Worker
from manman.repository.database import WorkerRepository
from manman.repository.rabbitmq import RabbitStatusPublisher
from manman.util import get_rabbitmq_connection

logger = logging.getLogger(__name__)

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
    try:
        result = repository.shutdown_worker(instance.worker_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Worker not found")
        return result
    except WorkerAlreadyClosedException as e:
        raise HTTPException(
            status_code=409,
            detail=f"Worker {e.worker_id} was already closed on {e.end_date.isoformat()}. Shutdown rejected.",
        )


@router.put("/shutdown/other")
async def worker_shutdown_other(instance: Worker):
    repository = WorkerRepository()
    lost_workers = repository.close_other_workers(instance.worker_id)
    # terminate the lost workers
    # TBD if this ist her ighte way tod oit
    if len(lost_workers) > 0:
        for worker in lost_workers:
            logger.warning(f"Worker {worker.worker_id} has been lost")

        # Send COMPLETE status to worker status queue for each shutdown worker
        for worker in lost_workers:
            worker_publisher = RabbitStatusPublisher(
                connection=get_rabbitmq_connection(),
                exchanges_config={
                    "worker": [f"status.worker-instance.{worker.worker_id}"]
                },
            )
            worker_publisher.publish(
                StatusInfo.create(
                    class_name="WorkerDal",
                    status_type=StatusType.COMPLETE,
                    worker_id=worker.worker_id,
                )
            )
            worker_publisher.shutdown()


# heartbeat
@router.post("/heartbeat")
async def worker_heartbeat(instance: Worker):
    repository = WorkerRepository()
    try:
        result = repository.update_worker_heartbeat(instance.worker_id)
        return result
    except Exception as e:
        # Handle specific case where worker is already closed
        if isinstance(e, WorkerAlreadyClosedException):
            raise HTTPException(
                status_code=410,
                detail=f"Worker {e.worker_id} was already closed on {e.end_date.isoformat()}. Heartbeat rejected.",
            )

        # Handle all other exceptions with generic 400
        raise HTTPException(status_code=400, detail=str(e))
