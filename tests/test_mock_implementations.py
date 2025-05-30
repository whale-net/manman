"""Tests for mock mode functionality in real services."""
import pytest
from unittest.mock import Mock, patch
import time

from manman.worker.processbuilder import ProcessBuilder, ProcessBuilderStatus


class TestProcessBuilderMockMode:
    """Test the ProcessBuilder mock mode functionality."""

    def test_initial_state(self):
        """Test that process builder starts in the correct state."""
        pb = ProcessBuilder("test_executable", mock_mode=True)
        assert pb.status == ProcessBuilderStatus.NOTSTARTED

    def test_parameter_addition(self):
        """Test adding parameters to the process builder."""
        pb = ProcessBuilder("test_executable", mock_mode=True)
        pb.add_parameter("--arg1", "--arg2")
        pb.add_parameter_stdin("input1")
        
        command, stdin = pb.render_command()
        assert command == "test_executable --arg1 --arg2"
        assert stdin == "input1"

    def test_lifecycle_states_mock_mode(self):
        """Test that process builder goes through expected states in mock mode."""
        pb = ProcessBuilder("test_executable", stdin_delay_seconds=1, mock_mode=True)
        
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

    def test_run_with_wait_mock_mode(self):
        """Test run with wait=True completes immediately in mock mode."""
        pb = ProcessBuilder("test_executable", mock_mode=True)
        pb.run(wait=True)
        assert pb.status == ProcessBuilderStatus.STOPPED

    def test_kill_functionality_mock_mode(self):
        """Test kill functionality in mock mode."""
        pb = ProcessBuilder("test_executable", mock_mode=True)
        pb.run()
        assert pb.status == ProcessBuilderStatus.INIT
        
        pb.kill()
        assert pb.status == ProcessBuilderStatus.STOPPED

    def test_stdin_handling_mock_mode(self):
        """Test stdin writing behavior in mock mode."""
        pb = ProcessBuilder("test_executable", mock_mode=True)
        pb.run()
        time.sleep(1.1)  # Get to RUNNING state
        
        # Should not raise exception, just log
        pb.write_stdin("test input")
        assert pb.status == ProcessBuilderStatus.RUNNING

    def test_exit_code_mock_mode(self):
        """Test exit code behavior in mock mode."""
        pb = ProcessBuilder("test_executable", mock_mode=True)
        
        # Should be None when not started
        assert pb.exit_code is None
        
        pb.run()
        # Should be None when running
        assert pb.exit_code is None
        
        pb.stop()
        # Should be 0 when stopped in mock mode
        assert pb.exit_code == 0

    def test_normal_mode_vs_mock_mode(self):
        """Test that normal mode and mock mode behave differently."""
        pb_normal = ProcessBuilder("echo", mock_mode=False)
        pb_mock = ProcessBuilder("echo", mock_mode=True)
        
        # Both should start as NOTSTARTED
        assert pb_normal.status == ProcessBuilderStatus.NOTSTARTED
        assert pb_mock.status == ProcessBuilderStatus.NOTSTARTED
        
        # Mock mode should use different internal attributes
        assert hasattr(pb_mock, '_mock_mode')
        assert pb_mock._mock_mode is True
        assert pb_normal._mock_mode is False


class TestServerMockMode:
    """Test Server mock mode integration points."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mocked dependencies for Server initialization."""
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

    @patch("manman.worker.server.RabbitStatusPublisher")
    @patch("manman.worker.server.RabbitCommandSubscriber")
    def test_server_initialization_mock_mode(
        self, mock_cmd_sub, mock_status_pub, mock_dependencies
    ):
        """Test that server can be initialized in mock mode."""
        from manman.worker.server import Server

        mock_publisher = Mock()
        mock_status_pub.return_value = mock_publisher

        # Create a Server instance in mock mode
        server = Server(
            wapi=mock_dependencies["wapi"],
            rabbitmq_connection=mock_dependencies["rabbitmq_connection"],
            root_install_directory="/test/path",
            config=mock_dependencies["config"],
            worker_id=1,
            mock_mode=True,
        )

        # Verify the server was created successfully
        assert server is not None
        assert server.instance == mock_dependencies["instance"]
        assert server._mock_mode is True
        assert hasattr(server._proc, '_mock_mode')
        assert server._proc._mock_mode is True

        # Verify CREATED status was published
        mock_publisher.publish.assert_called_once()

    @patch("manman.worker.server.RabbitStatusPublisher")
    @patch("manman.worker.server.RabbitCommandSubscriber")
    def test_server_initialization_normal_mode(
        self, mock_cmd_sub, mock_status_pub, mock_dependencies
    ):
        """Test that server can be initialized in normal mode."""
        from manman.worker.server import Server

        mock_publisher = Mock()
        mock_status_pub.return_value = mock_publisher

        # Create a Server instance in normal mode
        server = Server(
            wapi=mock_dependencies["wapi"],
            rabbitmq_connection=mock_dependencies["rabbitmq_connection"],
            root_install_directory="/test/path",
            config=mock_dependencies["config"],
            worker_id=1,
            mock_mode=False,
        )

        # Verify the server was created successfully
        assert server is not None
        assert server.instance == mock_dependencies["instance"]
        assert server._mock_mode is False
        assert hasattr(server._proc, '_mock_mode')
        assert server._proc._mock_mode is False


class TestWorkerServiceMockMode:
    """Test WorkerService mock mode integration points."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mocked dependencies for WorkerService initialization."""
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

    @patch("manman.worker.worker_service.RabbitStatusPublisher")
    @patch("manman.worker.worker_service.RabbitCommandSubscriber")
    @patch("manman.worker.worker_service.WorkerAPIClient")
    @patch("manman.worker.worker_service.get_auth_api_client")
    def test_worker_service_initialization_mock_mode(
        self, mock_auth_api, mock_wapi_class, mock_cmd_sub, mock_status_pub, mock_dependencies
    ):
        """Test that worker service can be initialized in mock mode."""
        from manman.worker.worker_service import WorkerService

        # Setup mocks
        mock_wapi_class.return_value = mock_dependencies["wapi"]
        mock_auth_api.return_value = Mock()
        mock_status_pub.return_value = Mock()
        mock_cmd_sub.return_value = Mock()

        # Create a WorkerService instance in mock mode
        service = WorkerService(
            install_dir="/test/path",
            host_url="http://test.example.com",
            sa_client_id=None,
            sa_client_secret=None,
            rabbitmq_connection=mock_dependencies["rabbitmq_connection"],
            mock_mode=True,
        )

        # Verify the service was created successfully
        assert service is not None
        assert hasattr(service, '_worker_instance')
        assert hasattr(service, '_servers')
        assert hasattr(service, '_mock_mode')
        assert service._mock_mode is True
        assert len(service._servers) == 0

    def test_queue_name_generation(self):
        """Test queue name generation methods."""
        from manman.worker.worker_service import WorkerService
        
        worker_id = 123
        cmd_queue = WorkerService.generate_command_queue_name(worker_id)
        status_queue = WorkerService.generate_status_queue_name(worker_id)
        
        assert cmd_queue == "cmd.worker-instance.123"
        assert status_queue == "status.worker-instance.123"


class TestServerMockModeCommands:
    """Test server command handling in mock mode."""

    @pytest.fixture
    def mock_server(self):
        """Create a server in mock mode for testing."""
        with patch("manman.worker.server.RabbitCommandSubscriber") as mock_cmd_sub, \
             patch("manman.worker.server.RabbitStatusPublisher") as mock_status_pub:
            
            from manman.worker.server import Server

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

            server = Server(
                wapi=mock_wapi,
                rabbitmq_connection=Mock(),
                root_install_directory="/test/path",
                config=mock_config,
                worker_id=1,
                mock_mode=True,  # Enable mock mode
            )
            
            return server

    def test_queue_name_generation(self):
        """Test queue name generation for server."""
        from manman.worker.server import Server
        
        instance_id = 456
        cmd_queue = Server.generate_command_queue_name(instance_id)
        status_queue = Server.generate_status_queue_name(instance_id)
        
        assert cmd_queue == "cmd.game-server-instance.456"
        assert status_queue == "status.game-server-instance.456"

    def test_execute_stdin_command_mock_mode(self, mock_server):
        """Test executing a stdin command in mock mode."""
        from manman.models import Command, CommandType
        
        stdin_command = Command(command_type=CommandType.STDIN, command_args=["123", "test", "input"])
        
        # Should not raise exception
        mock_server.execute_command(stdin_command)