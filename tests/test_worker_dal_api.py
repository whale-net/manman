"""
Unit tests for Worker DAL API endpoints.

Tests the core functionality: "Do I pass it in? Do I get something out?"
Focuses on happy path and error cases for worker management endpoints.
"""

from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from manman.host.api.worker_dal.worker import router
from manman.models import Worker


@pytest.fixture
def client():
    """Create a test client for the worker DAL API router."""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestWorkerCreate:
    """Test POST /worker/create endpoint."""

    def test_worker_create_success(self, client, mock_worker_repository):
        """Test successful worker creation."""
        # Arrange
        expected_worker = Worker(
            worker_id=123,
            created_date=datetime(2024, 1, 1, 0, 0, 0),
            end_date=None,
            last_heartbeat=None,
        )
        mock_worker_repository.create_worker.return_value = expected_worker

        # Act
        response = client.post("/worker/create")

        # Assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["worker_id"] == 123
        mock_worker_repository.create_worker.assert_called_once()


class TestWorkerShutdown:
    """Test PUT /worker/shutdown endpoint."""

    def test_worker_shutdown_success(self, client, mock_worker_repository):
        """Test successful worker shutdown."""
        # Arrange
        worker_input = {"worker_id": 123}
        expected_worker = Worker(
            worker_id=123,
            created_date=datetime(2024, 1, 1, 0, 0, 0),
            end_date=datetime(2024, 1, 2, 0, 0, 0),
            last_heartbeat=None,
        )
        mock_worker_repository.shutdown_worker.return_value = expected_worker

        # Act
        response = client.put("/worker/shutdown", json=worker_input)

        # Assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["worker_id"] == 123
        mock_worker_repository.shutdown_worker.assert_called_once_with(123)

    def test_worker_shutdown_not_found(self, client, mock_worker_repository):
        """Test worker shutdown when worker not found."""
        # Arrange
        worker_input = {"worker_id": 999}
        mock_worker_repository.shutdown_worker.return_value = None

        # Act
        response = client.put("/worker/shutdown", json=worker_input)

        # Assert
        assert response.status_code == 404
        assert response.json()["detail"] == "Worker not found"
        mock_worker_repository.shutdown_worker.assert_called_once_with(999)


class TestWorkerShutdownOther:
    """Test PUT /worker/shutdown/other endpoint."""

    def test_worker_shutdown_other_success(self, client, mock_worker_repository):
        """Test successful shutdown of other workers."""
        # Arrange
        worker_input = {"worker_id": 123}
        mock_worker_repository.close_other_workers.return_value = []

        # Act
        response = client.put("/worker/shutdown/other", json=worker_input)

        # Assert
        assert response.status_code == 200
        mock_worker_repository.close_other_workers.assert_called_once_with(123)

    # TODO lost worker list test


# TODO make work
# check for heartbeat to work
# TBH, this should probably just be a queue
# check that we can't heartbeat dead ones
class TestWorkerHeartbeat:
    """Test POST /worker/heartbeat endpoint."""

    def test_worker_heartbeat_recovery_from_lost(self, client):
        """Test worker heartbeat recovery when worker was previously LOST."""
        # Arrange
        worker_input = {"worker_id": 123}
        expected_worker = Worker(
            worker_id=123,
            created_date=datetime(2024, 1, 1, 0, 0, 0),
            end_date=None,
            last_heartbeat=datetime(2024, 1, 2, 0, 0, 0),
        )

        # Mock the required repositories and their methods
        with (
            patch("manman.host.api.worker_dal.worker.WorkerRepository") as mock_worker_repo_class,
            patch("manman.host.api.worker_dal.worker.StatusRepository") as mock_status_repo_class,
            patch("manman.host.api.worker_dal.worker.DatabaseRepository") as mock_db_repo_class,
            patch("manman.host.api.worker_dal.worker.RabbitStatusPublisher") as mock_publisher_class,
            patch("manman.host.api.worker_dal.worker.get_rabbitmq_connection") as mock_get_connection,
        ):
            # Set up mocks
            mock_worker_repo = mock_worker_repo_class.return_value
            mock_status_repo = mock_status_repo_class.return_value  
            mock_db_repo = mock_db_repo_class.return_value
            mock_publisher = mock_publisher_class.return_value
            mock_connection = Mock()
            mock_get_connection.return_value = mock_connection
            
            # Mock that worker was previously LOST
            from manman.models import StatusInfo, StatusType
            lost_status = StatusInfo.create(
                class_name="TestClass",
                status_type=StatusType.LOST,
                worker_id=123,
            )
            mock_status_repo.get_latest_worker_status.return_value = lost_status
            
            # Mock successful heartbeat update
            mock_worker_repo.update_worker_heartbeat.return_value = expected_worker
            
            # Mock no lost game server instances for simplicity
            mock_db_repo.get_lost_game_server_instances.return_value = []

            # Act
            response = client.post("/worker/heartbeat", json=worker_input)

            # Assert
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["worker_id"] == 123

            # Verify worker status check was called
            mock_status_repo.get_latest_worker_status.assert_called_once_with(123)
            
            # Verify heartbeat was updated
            mock_worker_repo.update_worker_heartbeat.assert_called_once_with(123)
            
            # Verify RUNNING status was published for recovery
            mock_publisher_class.assert_called()
            mock_publisher.publish.assert_called()
            
            # Get the StatusInfo object that was published
            published_status = mock_publisher.publish.call_args[0][0]
            assert published_status.status_type == StatusType.RUNNING
            assert published_status.worker_id == 123
            assert published_status.class_name == "WorkerDal"

    def test_worker_heartbeat_no_recovery_when_not_lost(self, client):
        """Test worker heartbeat does not send recovery status when worker was not LOST."""
        # Arrange
        worker_input = {"worker_id": 123}
        expected_worker = Worker(
            worker_id=123,
            created_date=datetime(2024, 1, 1, 0, 0, 0),
            end_date=None,
            last_heartbeat=datetime(2024, 1, 2, 0, 0, 0),
        )

        # Mock the required repositories and their methods
        with (
            patch("manman.host.api.worker_dal.worker.WorkerRepository") as mock_worker_repo_class,
            patch("manman.host.api.worker_dal.worker.StatusRepository") as mock_status_repo_class,
            patch("manman.host.api.worker_dal.worker.DatabaseRepository") as mock_db_repo_class,
            patch("manman.host.api.worker_dal.worker.RabbitStatusPublisher") as mock_publisher_class,
        ):
            # Set up mocks
            mock_worker_repo = mock_worker_repo_class.return_value
            mock_status_repo = mock_status_repo_class.return_value
            
            # Mock that worker was previously RUNNING (not LOST)
            from manman.models import StatusInfo, StatusType
            running_status = StatusInfo.create(
                class_name="TestClass",
                status_type=StatusType.RUNNING,
                worker_id=123,
            )
            mock_status_repo.get_latest_worker_status.return_value = running_status
            
            # Mock successful heartbeat update
            mock_worker_repo.update_worker_heartbeat.return_value = expected_worker

            # Act
            response = client.post("/worker/heartbeat", json=worker_input)

            # Assert
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["worker_id"] == 123

            # Verify worker status check was called
            mock_status_repo.get_latest_worker_status.assert_called_once_with(123)
            
            # Verify heartbeat was updated
            mock_worker_repo.update_worker_heartbeat.assert_called_once_with(123)
            
            # Verify NO status was published since worker was not LOST
            mock_publisher_class.assert_not_called()

    def test_worker_heartbeat_no_recovery_when_complete(self, client):
        """Test worker heartbeat does not send recovery status when worker is COMPLETE."""
        # Arrange
        worker_input = {"worker_id": 123}
        expected_worker = Worker(
            worker_id=123,
            created_date=datetime(2024, 1, 1, 0, 0, 0),
            end_date=None,
            last_heartbeat=datetime(2024, 1, 2, 0, 0, 0),
        )

        # Mock the required repositories and their methods
        with (
            patch("manman.host.api.worker_dal.worker.WorkerRepository") as mock_worker_repo_class,
            patch("manman.host.api.worker_dal.worker.StatusRepository") as mock_status_repo_class,
            patch("manman.host.api.worker_dal.worker.DatabaseRepository") as mock_db_repo_class,
            patch("manman.host.api.worker_dal.worker.RabbitStatusPublisher") as mock_publisher_class,
        ):
            # Set up mocks
            mock_worker_repo = mock_worker_repo_class.return_value
            mock_status_repo = mock_status_repo_class.return_value
            
            # Mock that worker was previously COMPLETE (not LOST)
            from manman.models import StatusInfo, StatusType
            complete_status = StatusInfo.create(
                class_name="TestClass",
                status_type=StatusType.COMPLETE,
                worker_id=123,
            )
            mock_status_repo.get_latest_worker_status.return_value = complete_status
            
            # Mock successful heartbeat update
            mock_worker_repo.update_worker_heartbeat.return_value = expected_worker

            # Act
            response = client.post("/worker/heartbeat", json=worker_input)

            # Assert
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["worker_id"] == 123

            # Verify worker status check was called
            mock_status_repo.get_latest_worker_status.assert_called_once_with(123)
            
            # Verify heartbeat was updated
            mock_worker_repo.update_worker_heartbeat.assert_called_once_with(123)
            
            # Verify NO status was published since worker was COMPLETE (not LOST)
            mock_publisher_class.assert_not_called()

    def test_worker_heartbeat_recovery_with_game_server_instances(self, client):
        """Test worker heartbeat recovery includes game server instances."""
        # Arrange
        worker_input = {"worker_id": 123}
        expected_worker = Worker(
            worker_id=123,
            created_date=datetime(2024, 1, 1, 0, 0, 0),
            end_date=None,
            last_heartbeat=datetime(2024, 1, 2, 0, 0, 0),
        )

        # Mock the required repositories and their methods
        with (
            patch("manman.host.api.worker_dal.worker.WorkerRepository") as mock_worker_repo_class,
            patch("manman.host.api.worker_dal.worker.StatusRepository") as mock_status_repo_class,
            patch("manman.host.api.worker_dal.worker.DatabaseRepository") as mock_db_repo_class,
            patch("manman.host.api.worker_dal.worker.RabbitStatusPublisher") as mock_publisher_class,
            patch("manman.host.api.worker_dal.worker.get_rabbitmq_connection") as mock_get_connection,
        ):
            # Set up mocks
            mock_worker_repo = mock_worker_repo_class.return_value
            mock_status_repo = mock_status_repo_class.return_value  
            mock_db_repo = mock_db_repo_class.return_value
            mock_publisher = mock_publisher_class.return_value
            mock_connection = Mock()
            mock_get_connection.return_value = mock_connection
            
            # Mock that worker was previously LOST
            from manman.models import StatusInfo, StatusType, GameServerInstance
            lost_status = StatusInfo.create(
                class_name="TestClass",
                status_type=StatusType.LOST,
                worker_id=123,
            )
            mock_status_repo.get_latest_worker_status.return_value = lost_status
            
            # Mock successful heartbeat update
            mock_worker_repo.update_worker_heartbeat.return_value = expected_worker
            
            # Mock some lost game server instances
            lost_instance1 = GameServerInstance(
                game_server_instance_id=1001,
                game_server_config_id=1,
                worker_id=123,
                created_date=datetime(2024, 1, 1, 0, 0, 0),
                end_date=None,
            )
            lost_instance2 = GameServerInstance(
                game_server_instance_id=1002,
                game_server_config_id=1,
                worker_id=123,
                created_date=datetime(2024, 1, 1, 0, 0, 0),
                end_date=None,
            )
            mock_db_repo.get_lost_game_server_instances.return_value = [lost_instance1, lost_instance2]

            # Act
            response = client.post("/worker/heartbeat", json=worker_input)

            # Assert
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["worker_id"] == 123

            # Verify repositories were called
            mock_status_repo.get_latest_worker_status.assert_called_once_with(123)
            mock_worker_repo.update_worker_heartbeat.assert_called_once_with(123)
            mock_db_repo.get_lost_game_server_instances.assert_called_once_with(123)
            
            # Verify publishers were created - one for worker + two for game server instances
            assert mock_publisher_class.call_count == 3
            
            # Verify all publish calls were made
            assert mock_publisher.publish.call_count == 3
            
            # Check that all published statuses are RUNNING
            published_calls = mock_publisher.publish.call_args_list
            for call in published_calls:
                published_status = call[0][0]
                assert published_status.status_type == StatusType.RUNNING
                assert published_status.class_name == "WorkerDal"
