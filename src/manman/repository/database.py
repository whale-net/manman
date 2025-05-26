"""
Database repository for status and worker operations.

This module contains all database operations related to status tracking,
worker management, and related functionality extracted from the status processor.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import desc
from sqlalchemy.sql.functions import current_timestamp
from sqlmodel import Session, not_, select

from manman.models import (
    ACTIVE_STATUS_TYPES,
    GameServer,
    GameServerConfig,
    GameServerInstance,
    StatusInfo,
    StatusType,
    Worker,
)


class DatabaseRepository:
    """Repository class for database operations related to status and worker management."""

    def __init__(self, session: Optional[Session] = None):
        """
        Initialize the repository with an optional session.

        Args:
            session: Optional SQLAlchemy session. If not provided, a new session will be created for each operation.
        """
        self._session = session

    def _get_session(self) -> Session:
        """Get a database session. If none provided, create a new one."""
        if self._session is not None:
            return self._session

        # Import here to avoid circular import
        from manman.util import get_sqlalchemy_session

        return get_sqlalchemy_session()

    def _get_session_context(self):
        """Get a session context manager."""
        if self._session is not None:
            # If we have a persistent session, create a context manager that yields it
            from contextlib import contextmanager

            @contextmanager
            def session_context():
                yield self._session

            return session_context()

        # Import here to avoid circular import
        from manman.util import get_sqlalchemy_session

        return get_sqlalchemy_session()

    @staticmethod
    def get_worker_current_status_subquery():
        # Subquery to get the latest status for each worker
        inner = select(StatusInfo).alias("si2")
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
        return last_status

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
        with self._get_session_context() as session:
            last_status = DatabaseRepository.get_worker_current_status_subquery()

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
        with self._get_session_context() as session:
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
        with self._get_session_context() as session:
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


class StatusRepository(DatabaseRepository):
    """Repository class for status-related database operations."""

    def get_latest_worker_status(self, worker_id: int) -> Optional[StatusInfo]:
        """
        Get the latest status for a specific worker.

        Args:
            worker_id: The ID of the worker

        Returns:
            The latest StatusInfo for the worker, or None if not found
        """
        with self._get_session_context() as session:
            stmt = (
                select(StatusInfo)
                .where(StatusInfo.worker_id == worker_id)
                .order_by(desc(StatusInfo.as_of))
                .limit(1)
            )
            return session.exec(stmt).first()

    def get_latest_instance_status(
        self, game_server_instance_id: int
    ) -> Optional[StatusInfo]:
        """
        Get the latest status for a specific game server instance.

        Args:
            game_server_instance_id: The ID of the game server instance

        Returns:
            The latest StatusInfo for the instance, or None if not found
        """
        with self._get_session_context() as session:
            stmt = (
                select(StatusInfo)
                .where(StatusInfo.game_server_instance_id == game_server_instance_id)
                .order_by(desc(StatusInfo.as_of))
                .limit(1)
            )
            return session.exec(stmt).first()


class WorkerRepository(DatabaseRepository):
    """Repository class for worker-related database operations."""

    def create_worker(self) -> Worker:
        """
        Create a new worker.

        Returns:
            The created Worker instance
        """
        with self._get_session_context() as session:
            worker = Worker()
            session.add(worker)
            session.flush()
            session.expunge(worker)
            session.commit()
            return worker

    def get_worker_by_id(self, worker_id: int) -> Optional[Worker]:
        """
        Get a worker by its ID.

        Args:
            worker_id: The ID of the worker

        Returns:
            The Worker instance, or None if not found
        """
        with self._get_session_context() as session:
            stmt = select(Worker).where(Worker.worker_id == worker_id)
            return session.exec(stmt).first()

    def shutdown_worker(self, worker_id: int) -> Optional[Worker]:
        """
        Shutdown a worker by setting its end_date.

        Args:
            worker_id: The ID of the worker to shutdown

        Returns:
            The updated Worker instance, or None if not found

        Raises:
            Exception: If the worker is already shut down
        """
        with self._get_session_context() as session:
            stmt = select(Worker).where(Worker.worker_id == worker_id)
            current_instance = session.exec(stmt).first()

            if current_instance is None:
                return None

            if current_instance.end_date is not None:
                raise Exception("Worker already closed on server")

            current_instance.end_date = current_timestamp()
            session.add(current_instance)
            session.flush()
            session.refresh(current_instance)
            session.expunge(current_instance)
            session.commit()

            return current_instance

    def update_worker_heartbeat(self, worker_id: int) -> Optional[Worker]:
        """
        Update the heartbeat timestamp for a worker.

        Args:
            worker_id: The ID of the worker

        Returns:
            The updated Worker instance, or None if not found

        Raises:
            Exception: If the worker is not found or already shut down
        """
        with self._get_session_context() as session:
            stmt = select(Worker).where(Worker.worker_id == worker_id)
            current_instance = session.exec(stmt).first()

            if current_instance is None:
                raise Exception("Worker not found")

            if current_instance.end_date is not None:
                raise Exception("Worker already closed on server")

            current_instance.last_heartbeat = current_timestamp()
            session.add(current_instance)
            session.flush()
            session.refresh(current_instance)
            session.expunge(current_instance)
            session.commit()

            return current_instance

    def close_other_workers(self, worker_id: int) -> list[Worker]:
        """
        Close all other workers except the specified one.

        Args:
            worker_id: The ID of the worker to keep active

        Returns:
            list of lost workers who are now terminated
        """
        from sqlmodel import and_, func, update

        with self._get_session_context() as session:
            # hopefully this is all one transaction
            # otherwise this doesn't work
            open_worker_condition = and_(
                Worker.worker_id != worker_id,
                Worker.end_date.is_(None),
            )

            last_status = DatabaseRepository.get_worker_current_status_subquery()
            lost_workers = session.exec(
                select(Worker)
                .join(last_status)
                .where(
                    open_worker_condition, last_status.c.status_type == StatusType.LOST
                )
            ).all()
            for worker in lost_workers:
                session.expunge(worker)

            update_stmt = (
                update(Worker).where(open_worker_condition).values(end_date=func.now())
            )
            # result = session.exec(update_stmt)
            # affected_rows = result.rowcount
            session.exec(update_stmt)
            session.commit()
            return lost_workers


class GameServerRepository(DatabaseRepository):
    """Repository class for game server-related database operations."""

    def get_game_server_by_id(self, server_id: int) -> Optional[GameServer]:
        """
        Get a game server by its ID.

        Args:
            server_id: The ID of the game server

        Returns:
            The GameServer instance, or None if not found
        """
        with self._get_session_context() as session:
            server = session.get(GameServer, server_id)
            if server:
                session.expunge(server)
            return server

    def get_game_server_config_by_id(
        self, config_id: int
    ) -> Optional[GameServerConfig]:
        """
        Get a game server configuration by its ID.

        Args:
            config_id: The ID of the game server configuration

        Returns:
            The GameServerConfig instance, or None if not found
        """
        with self._get_session_context() as session:
            config = session.get(GameServerConfig, config_id)
            if config:
                session.expunge(config)
            return config


class GameServerInstanceRepository(DatabaseRepository):
    """Repository class for game server instance-related database operations."""

    def create_instance(
        self, game_server_config_id: int, worker_id: int
    ) -> GameServerInstance:
        """
        Create a new game server instance.

        Args:
            game_server_config_id: The ID of the game server configuration
            worker_id: The ID of the worker

        Returns:
            The created GameServerInstance
        """
        with self._get_session_context() as session:
            server = GameServerInstance(
                game_server_config_id=game_server_config_id, worker_id=worker_id
            )
            session.add(server)
            session.flush()
            session.expunge(server)
            session.commit()
            return server

    def get_instance_by_id(self, instance_id: int) -> Optional[GameServerInstance]:
        """
        Get a game server instance by its ID.

        Args:
            instance_id: The ID of the game server instance

        Returns:
            The GameServerInstance, or None if not found
        """
        with self._get_session_context() as session:
            instance = session.get(GameServerInstance, instance_id)
            if instance:
                session.expunge(instance)
            return instance

    def shutdown_instance(self, instance_id: int) -> Optional[GameServerInstance]:
        """
        Shutdown a game server instance by setting its end_date.

        Args:
            instance_id: The ID of the instance to shutdown

        Returns:
            The updated GameServerInstance, or None if not found

        Raises:
            Exception: If the instance is already shut down
        """
        with self._get_session_context() as session:
            stmt = select(GameServerInstance).where(
                GameServerInstance.game_server_instance_id == instance_id
            )
            current_instance = session.exec(stmt).first()

            if current_instance is None:
                return None

            if current_instance.end_date is not None:
                raise Exception("Instance already closed on server")

            current_instance.end_date = datetime.now(timezone.utc)
            session.add(current_instance)
            session.flush()
            session.refresh(current_instance)
            session.expunge(current_instance)
            session.commit()

            return current_instance

    def update_instance_heartbeat(
        self, instance_id: int
    ) -> Optional[GameServerInstance]:
        """
        Update the heartbeat timestamp for a game server instance.

        Args:
            instance_id: The ID of the instance

        Returns:
            The updated GameServerInstance, or None if not found
        """
        with self._get_session_context() as session:
            instance = session.get(GameServerInstance, instance_id)
            if instance is None:
                return None

            instance.last_heartbeat = datetime.now(timezone.utc)
            session.add(instance)
            session.flush()
            session.expunge(instance)
            session.commit()
            return instance
