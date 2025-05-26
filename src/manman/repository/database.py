"""
Database repository for status and worker operations.

This module contains all database operations related to status tracking,
worker management, and related functionality extracted from the status processor.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlmodel import Session, not_, select

from manman.models import (
    ACTIVE_STATUS_TYPES,
    GameServerInstance,
    StatusInfo,
    Worker,
)
from manman.util import get_sqlalchemy_session


class DatabaseRepository:
    """Repository class for database operations related to status and worker management."""

    def __init__(self, session: Optional[Session] = None):
        """
        Initialize the repository with an optional session.

        Args:
            session: Optional SQLAlchemy session. If not provided, a new session will be created for each operation.
        """
        self._session = session

    def get_stale_workers_with_status(
        self, heartbeat_threshold: datetime, heartbeat_max_lookback: datetime
    ) -> List[Tuple[Worker, str]]:
        """
        Get workers whose heartbeats are stale along with their current status.

        Args:
            heartbeat_threshold: Workers with heartbeat before this time are considered stale
            heartbeat_max_lookback: Only consider workers that had a heartbeat within this lookback period

        Returns:
            List of tuples containing (Worker, current_status_type)
        """
        with get_sqlalchemy_session(self._session) as session:
            # Subquery to get the latest status for each worker
            inner = select(StatusInfo).alias("i")
            last_status = (
                select(StatusInfo).where(
                    not_(StatusInfo.worker_id.is_(None)),
                    not_(
                        select(inner)
                        .where(
                            inner.c.worker_id == StatusInfo.worker_id,
                            inner.c.as_of > StatusInfo.as_of,
                        )
                        .exists()
                    ),
                )
            ).subquery()

            # Query for workers with stale heartbeats
            candidate_workers = (
                select(Worker, last_status.c.status_type)
                .join(last_status)
                .where(
                    Worker.last_heartbeat > heartbeat_max_lookback,
                    Worker.last_heartbeat < heartbeat_threshold,
                    Worker.end_date.is_(None),
                    last_status.c.status_type.in_(ACTIVE_STATUS_TYPES),
                )
            )

            return session.exec(candidate_workers).all()

    def get_active_game_server_instances(
        self, worker_id: int
    ) -> List[GameServerInstance]:
        """
        Get all active game server instances for a given worker.

        Args:
            worker_id: The ID of the worker

        Returns:
            List of active GameServerInstance objects
        """
        with get_sqlalchemy_session(self._session) as session:
            stmt = (
                select(GameServerInstance)
                .where(GameServerInstance.worker_id == worker_id)
                .where(GameServerInstance.end_date.is_(None))
            )
            return session.exec(stmt).all()

    def write_status_to_database(self, status_info: StatusInfo) -> None:
        """
        Write a status message to the database.

        Args:
            status_info: The StatusInfo object to write to the database
        """
        with get_sqlalchemy_session(self._session) as session:
            session.add(status_info)
            session.commit()

    def get_workers_with_stale_heartbeats(
        self,
        heartbeat_threshold_seconds: int = 5,
        heartbeat_max_lookback_hours: int = 1,
    ) -> List[Tuple[Worker, str]]:
        """
        Convenience method to get workers with stale heartbeats using default time periods.

        Args:
            heartbeat_threshold_seconds: Seconds before now to consider heartbeat stale (default: 5)
            heartbeat_max_lookback_hours: Hours before now to look back for workers (default: 1)

        Returns:
            List of tuples containing (Worker, current_status_type)
        """
        current_time = datetime.now(timezone.utc)
        heartbeat_threshold = current_time - timedelta(
            seconds=heartbeat_threshold_seconds
        )
        heartbeat_max_lookback = current_time - timedelta(
            hours=heartbeat_max_lookback_hours
        )

        return self.get_stale_workers_with_status(
            heartbeat_threshold, heartbeat_max_lookback
        )
