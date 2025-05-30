"""Tests for mock implementations to ensure they work correctly."""
import pytest
from unittest.mock import Mock, patch
import time

from manman.mock.processbuilder import MockProcessBuilder
from manman.worker.processbuilder import ProcessBuilderStatus


class TestMockProcessBuilder:
    """Test the mock ProcessBuilder implementation."""

    def test_initial_state(self):
        """Test that mock process builder starts in the correct state."""
        pb = MockProcessBuilder("test_executable")
        assert pb.status == ProcessBuilderStatus.NOTSTARTED

    def test_parameter_addition(self):
        """Test adding parameters to the mock process builder."""
        pb = MockProcessBuilder("test_executable")
        pb.add_parameter("--arg1", "--arg2")
        pb.add_parameter_stdin("input1")
        
        command, stdin = pb.render_command()
        assert command == "test_executable --arg1 --arg2"
        assert stdin == "input1"

    def test_lifecycle_states(self):
        """Test that mock process builder goes through expected states."""
        pb = MockProcessBuilder("test_executable", stdin_delay_seconds=1)
        
        # Should start as NOT_STARTED
        assert pb.status == ProcessBuilderStatus.NOTSTARTED
        
        # After run, should be INIT for delay period
        pb.run()
        assert pb.status == ProcessBuilderStatus.INIT
        
        # Wait for delay period to pass, should become RUNNING
        time.sleep(1.1)
        assert pb.status == ProcessBuilderStatus.RUNNING
        
        # After stop, should be STOPPED
        pb.stop()
        assert pb.status == ProcessBuilderStatus.STOPPED

    def test_run_with_wait(self):
        """Test run with wait=True completes immediately."""
        pb = MockProcessBuilder("test_executable")
        pb.run(wait=True)
        assert pb.status == ProcessBuilderStatus.STOPPED

    def test_kill_functionality(self):
        """Test kill functionality."""
        pb = MockProcessBuilder("test_executable")
        pb.run()
        assert pb.status == ProcessBuilderStatus.INIT
        
        pb.kill()
        assert pb.status == ProcessBuilderStatus.STOPPED

    def test_stdin_handling(self):
        """Test stdin writing behavior."""
        pb = MockProcessBuilder("test_executable")
        pb.run()
        time.sleep(1.1)  # Get to RUNNING state
        
        # Should not raise exception, just log
        pb.write_stdin("test input")
        assert pb.status == ProcessBuilderStatus.RUNNING


class TestMockServerIntegration:
    """Test mock server integration points."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mocked dependencies for MockServer initialization."""
        mock_wapi = Mock()
        mock_rabbitmq_connection = Mock()
        mock_config = Mock()
        mock_config.game_server_id = 1
        mock_config.name = "test-server"
        mock_config.executable = "server.exe"
        mock_config.args = ["--port", "27015"]
        mock_config.env_var = []

        # Mock the instance creation
        mock_instance = Mock()
        mock_instance.game_server_instance_id = 123
        mock_wapi.game_server_instance_create.return_value = mock_instance

        # Mock game server
        mock_game_server = Mock()
        mock_game_server.server_type = 1  # STEAM
        mock_game_server.app_id = 730
        mock_wapi.game_server.return_value = mock_game_server

        return {
            "wapi": mock_wapi,
            "rabbitmq_connection": mock_rabbitmq_connection,
            "config": mock_config,
            "instance": mock_instance,
            "game_server": mock_game_server,
        }

    @patch("manman.mock.server.RabbitStatusPublisher")
    @patch("manman.mock.server.RabbitCommandSubscriber")
    def test_mock_server_initialization(
        self, mock_cmd_sub, mock_status_pub, mock_dependencies
    ):
        """Test that mock server can be initialized."""
        from manman.mock.server import MockServer

        mock_publisher = Mock()
        mock_status_pub.return_value = mock_publisher

        # Create a MockServer instance
        server = MockServer(
            wapi=mock_dependencies["wapi"],
            rabbitmq_connection=mock_dependencies["rabbitmq_connection"],
            root_install_directory="/test/path",
            config=mock_dependencies["config"],
            worker_id=1,
        )

        # Verify the server was created successfully
        assert server is not None
        assert server.instance == mock_dependencies["instance"]
        assert not server.is_shutdown

        # Verify CREATED status was published
        mock_publisher.publish.assert_called_once()


def test_import_mock_modules():
    """Test that all mock modules can be imported successfully."""
    # This is a basic smoke test to ensure modules are structured correctly
    from manman.mock.main import app
    from manman.mock.worker_service import MockWorkerService
    from manman.mock.server import MockServer
    from manman.mock.processbuilder import MockProcessBuilder
    
    # Basic checks that classes exist and have expected attributes
    assert hasattr(MockWorkerService, 'RMQ_EXCHANGE')
    assert hasattr(MockServer, 'RMQ_EXCHANGE')
    assert hasattr(MockProcessBuilder, 'status')
    
    # Check that typer app exists
    assert app is not None


class TestMockWorkerServiceIntegration:
    """Test mock worker service integration points."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mocked dependencies for MockWorkerService initialization."""
        mock_wapi = Mock()
        mock_rabbitmq_connection = Mock()
        
        # Mock worker instance creation
        mock_worker_instance = Mock()
        mock_worker_instance.worker_id = 42
        mock_wapi.worker_create.return_value = mock_worker_instance
        mock_wapi.close_other_workers.return_value = None
        mock_wapi.worker_heartbeat.return_value = None
        
        return {
            "wapi": mock_wapi,
            "rabbitmq_connection": mock_rabbitmq_connection,
            "worker_instance": mock_worker_instance,
        }

    @patch("manman.mock.worker_service.RabbitStatusPublisher")
    @patch("manman.mock.worker_service.RabbitCommandSubscriber")
    @patch("manman.mock.worker_service.WorkerAPIClient")
    @patch("manman.mock.worker_service.get_auth_api_client")
    def test_mock_worker_service_initialization(
        self, mock_auth_api, mock_wapi_class, mock_cmd_sub, mock_status_pub, mock_dependencies
    ):
        """Test that mock worker service can be initialized."""
        from manman.mock.worker_service import MockWorkerService

        # Setup mocks
        mock_wapi_class.return_value = mock_dependencies["wapi"]
        mock_auth_api.return_value = Mock()
        mock_status_pub.return_value = Mock()
        mock_cmd_sub.return_value = Mock()

        # Create a MockWorkerService instance
        service = MockWorkerService(
            install_dir="/test/path",
            host_url="http://test.example.com",
            sa_client_id=None,
            sa_client_secret=None,
            rabbitmq_connection=mock_dependencies["rabbitmq_connection"],
        )

        # Verify the service was created successfully
        assert service is not None
        assert hasattr(service, '_worker_instance')
        assert hasattr(service, '_servers')
        assert len(service._servers) == 0

    def test_queue_name_generation(self):
        """Test queue name generation methods."""
        from manman.mock.worker_service import MockWorkerService
        
        worker_id = 123
        cmd_queue = MockWorkerService.generate_command_queue_name(worker_id)
        status_queue = MockWorkerService.generate_status_queue_name(worker_id)
        
        assert cmd_queue == "cmd.worker-instance.123"
        assert status_queue == "status.worker-instance.123"


class TestMockServerCommands:
    """Test mock server command handling."""

    @pytest.fixture
    def mock_server(self):
        """Create a mock server for testing."""
        with patch("manman.mock.server.RabbitCommandSubscriber") as mock_cmd_sub, \
             patch("manman.mock.server.RabbitStatusPublisher") as mock_status_pub:
            
            from manman.mock.server import MockServer

            # Create mock dependencies
            mock_wapi = Mock()
            mock_config = Mock()
            mock_config.game_server_id = 1
            mock_config.name = "test-server"
            mock_config.executable = "server.exe"
            mock_config.args = ["--port", "27015"]

            mock_instance = Mock()
            mock_instance.game_server_instance_id = 123
            mock_wapi.game_server_instance_create.return_value = mock_instance

            mock_game_server = Mock()
            mock_game_server.server_type = 1
            mock_game_server.app_id = 730
            mock_wapi.game_server.return_value = mock_game_server

            mock_cmd_sub.return_value = Mock()
            mock_status_pub.return_value = Mock()

            server = MockServer(
                wapi=mock_wapi,
                rabbitmq_connection=Mock(),
                root_install_directory="/test/path",
                config=mock_config,
                worker_id=1,
            )
            
            return server

    def test_queue_name_generation(self):
        """Test queue name generation for mock server."""
        from manman.mock.server import MockServer
        
        instance_id = 456
        cmd_queue = MockServer.generate_command_queue_name(instance_id)
        status_queue = MockServer.generate_status_queue_name(instance_id)
        
        assert cmd_queue == "cmd.game-server-instance.456"
        assert status_queue == "status.game-server-instance.456"

    def test_execute_stop_command(self, mock_server):
        """Test executing a stop command."""
        from manman.models import Command, CommandType
        
        stop_command = Command(command_type=CommandType.STOP, command_args=["123"])
        
        # Should not raise exception
        mock_server.execute_command(stop_command)
        assert mock_server.is_shutdown

    def test_execute_stdin_command(self, mock_server):
        """Test executing a stdin command."""
        from manman.models import Command, CommandType
        
        stdin_command = Command(command_type=CommandType.STDIN, command_args=["123", "test", "input"])
        
        # Should not raise exception
        mock_server.execute_command(stdin_command)