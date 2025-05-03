# The application logic layer
from typing import Annotated, Optional

from amqpstorm import Channel
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, desc, select

from manman.host.api.injectors import inject_rmq_channel
from manman.models import Command, CommandType, GameServerInstance, Worker
from manman.util import get_sqlalchemy_session
from manman.worker.service import WorkerService

router = APIRouter(prefix="/host")


@router.get("/health")
async def health() -> str:
    return "OK"


# TODO - this whole thing needs rethnking ,but just going to hack it together for now
async def get_current_worker(session: Optional[Session] = None) -> Worker:
    with get_sqlalchemy_session(session) as sess:
        stmt = (
            select(Worker)
            .where(Worker.end_date.is_(None))
            .order_by(desc(Worker.created_date))
            .limit(1)
        )
        worker = sess.exec(stmt).one_or_none()
        if worker:
            # If a session is provided, we don't want to expunge the worker
            if session is None:
                sess.expunge(worker)
            return worker
        else:
            # Handle the case where no active worker exists
            raise HTTPException(status_code=404, detail="No active worker found")


@router.get("/worker/current")
async def worker_current() -> Worker:
    return await get_current_worker()


async def get_current_instances(
    worker_id: int, session: Optional[Session] = None
) -> list[GameServerInstance]:
    with get_sqlalchemy_session(session) as sess:
        stmt = (
            select(GameServerInstance)
            .where(GameServerInstance.worker_id == worker_id)
            .where(GameServerInstance.end_date.is_(None))
        )
        results = sess.exec(stmt).scalars().all()
        # If a session is provided, we don't want to expunge the instances
        if session is None:
            for instance in results:
                sess.expunge(instance)
        return results


@router.post("/gameserver/{id}/start", dependencies=[Depends(inject_rmq_channel)])
async def start_game_server(
    id: int,
    channel: Annotated[Channel, Depends(inject_rmq_channel)],
):
    with get_sqlalchemy_session() as sess:
        worker = await get_current_worker(sess)

        # Create a Command object with CommandType.START and game_server_config_id as arg
        command = Command(command_type=CommandType.START, command_args=[str(id)])

        # Set exchange and queue name using the worker's ID
        exchange = WorkerService.RMQ_EXCHANGE
        queue_name = WorkerService.generate_rmq_queue_name(worker.worker_id)

        # Ensure the queue exists and is bound to the exchange
        channel.queue.declare(queue=queue_name, auto_delete=True)
        channel.queue.bind(exchange=exchange, queue=queue_name, routing_key=queue_name)

        # Serialize the command to JSON
        message = command.model_dump_json()

        # Publish the command to the worker's queue
        channel.basic.publish(body=message, exchange=exchange, routing_key=queue_name)
        # for now, explicitly close the channel
        channel.close()

        return {
            "status": "success",
            "message": f"Start command sent to worker {worker.worker_id}",
        }


@router.post("/gameserver/{id}/stop", dependencies=[Depends(inject_rmq_channel)])
async def stop_game_server(
    id: int,
    channel: Annotated[Channel, Depends(inject_rmq_channel)],
):
    """
    Stop all running game server instances for the current worker.
    """
    with get_sqlalchemy_session() as sess:
        worker = await get_current_worker(sess)

        command = Command(command_type=CommandType.STOP, command_args=[str(id)])

        # Set exchange and queue name using the worker's ID
        exchange = WorkerService.RMQ_EXCHANGE
        queue_name = WorkerService.generate_rmq_queue_name(worker.worker_id)

        # Ensure the queue exists and is bound to the exchange
        channel.queue.declare(queue=queue_name, auto_delete=True)
        channel.queue.bind(exchange=exchange, queue=queue_name, routing_key=queue_name)

        # Serialize the command to JSON
        message = command.model_dump_json()

        # Publish the command to the worker's queue
        channel.basic.publish(body=message, exchange=exchange, routing_key=queue_name)

        # for now, explicitly close the channel
        channel.close()

        return {
            "status": "success",
            "message": f"Stop command sent to worker {worker.worker_id}",
        }
