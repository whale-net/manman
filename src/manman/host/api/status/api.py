# The status API - read-only queries for status information
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, HTTPException
from sqlalchemy import desc
from sqlmodel import select

from manman.models import GameServerInstance, Worker
from manman.util import get_sqlalchemy_session

router = APIRouter(prefix="/status")


@router.get("/workers")
async def get_workers_status() -> List[dict]:
    """Get status of all workers."""
    with get_sqlalchemy_session() as session:
        stmt = select(Worker).order_by(desc(Worker.created_date))
        workers = session.exec(stmt).all()

        worker_status = []
        for worker in workers:
            # Determine if worker is healthy based on heartbeat
            is_healthy = False
            if worker.last_heartbeat and worker.end_date is None:
                time_since_heartbeat = datetime.utcnow() - worker.last_heartbeat
                is_healthy = time_since_heartbeat < timedelta(minutes=5)

            worker_status.append(
                {
                    "worker_id": worker.worker_id,
                    "created_date": worker.created_date,
                    "end_date": worker.end_date,
                    "last_heartbeat": worker.last_heartbeat,
                    "is_healthy": is_healthy,
                    "status": "healthy"
                    if is_healthy
                    else "unhealthy"
                    if worker.end_date is None
                    else "terminated",
                }
            )

        return worker_status


@router.get("/workers/{worker_id}")
async def get_worker_status(worker_id: int) -> dict:
    """Get detailed status for a specific worker."""
    with get_sqlalchemy_session() as session:
        worker = session.get(Worker, worker_id)
        if not worker:
            raise HTTPException(status_code=404, detail="Worker not found")

        # Get server instances for this worker
        stmt = select(GameServerInstance).where(
            GameServerInstance.worker_id == worker_id
        )
        instances = session.exec(stmt).all()

        # Determine health status
        is_healthy = False
        if worker.last_heartbeat and worker.end_date is None:
            time_since_heartbeat = datetime.utcnow() - worker.last_heartbeat
            is_healthy = time_since_heartbeat < timedelta(minutes=5)

        return {
            "worker_id": worker.worker_id,
            "created_date": worker.created_date,
            "end_date": worker.end_date,
            "last_heartbeat": worker.last_heartbeat,
            "is_healthy": is_healthy,
            "status": "healthy"
            if is_healthy
            else "unhealthy"
            if worker.end_date is None
            else "terminated",
            "server_instances": [
                {
                    "instance_id": instance.game_server_instance_id,
                    "game_server_config_id": instance.game_server_config_id,
                    "created_date": instance.created_date,
                    "end_date": instance.end_date,
                    "status": "running" if instance.end_date is None else "stopped",
                }
                for instance in instances
            ],
        }


@router.get("/servers")
async def get_servers_status() -> List[dict]:
    """Get status of all server instances."""
    with get_sqlalchemy_session() as session:
        stmt = select(GameServerInstance).order_by(
            desc(GameServerInstance.created_date)
        )
        instances = session.exec(stmt).all()

        return [
            {
                "instance_id": instance.game_server_instance_id,
                "worker_id": instance.worker_id,
                "game_server_config_id": instance.game_server_config_id,
                "created_date": instance.created_date,
                "end_date": instance.end_date,
                "status": "running" if instance.end_date is None else "stopped",
            }
            for instance in instances
        ]


@router.get("/servers/active")
async def get_active_servers() -> List[dict]:
    """Get status of currently running server instances."""
    with get_sqlalchemy_session() as session:
        stmt = (
            select(GameServerInstance)
            .where(GameServerInstance.end_date.is_(None))
            .order_by(desc(GameServerInstance.created_date))
        )
        instances = session.exec(stmt).all()

        return [
            {
                "instance_id": instance.game_server_instance_id,
                "worker_id": instance.worker_id,
                "game_server_config_id": instance.game_server_config_id,
                "created_date": instance.created_date,
                "status": "running",
            }
            for instance in instances
        ]


@router.get("/system")
async def get_system_status() -> dict:
    """Get overall system status summary."""
    with get_sqlalchemy_session() as session:
        # Count workers
        active_workers = session.exec(
            select(Worker).where(Worker.end_date.is_(None))
        ).all()

        healthy_workers = 0
        for worker in active_workers:
            if worker.last_heartbeat:
                time_since_heartbeat = datetime.utcnow() - worker.last_heartbeat
                if time_since_heartbeat < timedelta(minutes=5):
                    healthy_workers += 1

        # Count servers
        active_servers = session.exec(
            select(GameServerInstance).where(GameServerInstance.end_date.is_(None))
        ).all()

        return {
            "timestamp": datetime.utcnow(),
            "workers": {
                "total_active": len(active_workers),
                "healthy": healthy_workers,
                "unhealthy": len(active_workers) - healthy_workers,
            },
            "servers": {"total_active": len(active_servers)},
            "overall_status": "healthy"
            if healthy_workers > 0
            else "degraded"
            if len(active_workers) > 0
            else "down",
        }
