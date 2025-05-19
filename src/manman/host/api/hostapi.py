# The application logic layer
from typing import Annotated, Optional

from amqpstorm import Channel
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, desc, select

from manman.host.api.injectors import inject_rmq_channel
from manman.host.request_models import (
    CurrentInstanceResponse,  # TODO - move this
    StdinCommandRequest,
)
from manman.models import (
    Command,
    CommandType,
    GameServerConfig,
    GameServerInstance,
    Worker,
)
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
    # TODO - don't re-use a session in the context manager if one is provided
    #        doing so will cause the session to be closed when the context manager exits
    #        #35
    sess = get_sqlalchemy_session(session)
    stmt = (
        select(GameServerInstance)
        .where(GameServerInstance.worker_id == worker_id)
        .where(GameServerInstance.end_date.is_(None))
    )
    results = sess.exec(stmt).all()
    # If a session is provided, we don't want to expunge the instances
    if session is None:
        for instance in results:
            sess.expunge(instance)
        sess.close()
    return results


@router.get("/gameserver")
async def get_game_servers() -> list[GameServerConfig]:
    """
    Get all game server configs

    Although it seems strange for us to return configs instead of instances,
    this is the way the API is designed. We want to make the /gameserver/ endpoint
    the way you would interact with a game server. The whole instance thing
    should be abstracted away from the user.

    :return: list of game server configs
    """
    with get_sqlalchemy_session() as sess:
        stmt = (
            select(GameServerConfig)
            .where(GameServerConfig.is_visible.is_(True))
            .order_by(GameServerConfig.name)
        )
        results = sess.exec(stmt).all()
        for config in results:
            sess.expunge(config)
        return results


@router.post("/gameserver/{id}/start", dependencies=[Depends(inject_rmq_channel)])
async def start_game_server(
    id: int,
    channel: Annotated[Channel, Depends(inject_rmq_channel)],
):
    """
    Given the game server config ID, start a game server instance

    :param id: game server config ID
    :param channel: rabbitmq channel
    :return: arbitrary response
    """
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

        # TODO - FUTURE enhancement, have worker echo the instance back to the host
        # could do json, or could lookup via session
        # the idea of having the worker hit the host for an instance
        # just to send it back to the host seems a bit funny
        # but is also effective because the workerdal is effectively its own
        # service layer https://www.youtube.com/watch?v=-FtCTW2rVFM
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
    Given the game server config ID, stop a game server instance

    Finds the current worker, and sends a stop command to it
    It is up to the worker to handle the command
    and stop the game server instance.

    This endpoint provides an abstract gameserver interface
    to users, so they don't have to know about the worker
    and how it works

    :param id: game server config ID
    :param channel: rabbitmq channel
    :return: arbitrary response
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


@router.post("/gameserver/{id}/stdin", dependencies=[Depends(inject_rmq_channel)])
async def stdin_game_server(
    id: int,
    channel: Annotated[Channel, Depends(inject_rmq_channel)],
    body: StdinCommandRequest,
):
    """
    Send a stdin command to the game server config's running instance

    This finds the current worker, and sends a stdin command to it
    It is up to the worker to handle the command
    and send it to the game server instance.

    This endpoint does not have a bheavior defined if no server is running.

    :param id: game server config ID
    :param channel: rabbitmq channel
    :param body: StdinCommandRequest
    :return: arbitrary response
    """
    with get_sqlalchemy_session() as sess:
        worker = await get_current_worker(sess)

        command = Command(
            command_type=CommandType.STDIN, command_args=[str(id), *body.commands]
        )

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
            "message": f"Stdin command sent to worker {worker.worker_id}",
        }


@router.get("/gameserver/instances/active")
async def get_active_game_server_instances(
    worker: Annotated[Worker, Depends(worker_current)],
) -> CurrentInstanceResponse:
    """
    Get all active game server instances for the current worker.
    """
    with get_sqlalchemy_session() as sess:
        instances = await get_current_instances(worker.worker_id, sess)
        # TODO fix this when coming back to this
        return CurrentInstanceResponse.from_instances(instances)


@router.post(
    "/gameserver/instance/{id}/stdin", dependencies=[Depends(inject_rmq_channel)]
)
async def stdin_game_server_instance(
    id: int,
    channel: Annotated[Channel, Depends(inject_rmq_channel)],
    body: StdinCommandRequest,
):
    """
    Send a stdin command to the game server instance

    This sends a command directly to the game server instance.
    The worker is not involved in this process.

    This endpoint does not have a behavior defined if the game server instance is not running.

    :param id: game server instance ID
    :param channel: rabbitmq channel
    :param body: StdinCommandRequest
    :return: arbitrary response
    """
    # Copy from above, but send to instance
    # first I think I need to make the instance handle the command though
    raise NotImplementedError("Not implemented yet")
