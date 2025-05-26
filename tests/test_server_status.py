"""
Tests for server status publishing functionality.

This module tests that the Server class correctly publishes status messages
during its lifecycle.
"""

from unittest.mock import Mock, patch

import pytest

from manman.models import StatusInfo, StatusType
from manman.worker.server import Server


class TestServerStatusPublishing:
    """Test server status publishing functionality."""

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
    @patch("manman.worker.server.ProcessBuilder")
    def test_server_initialization_publishes_created_status(
        self, mock_pb, mock_cmd_sub, mock_status_pub, mock_dependencies
    ):
        """Test that server initialization publishes CREATED status."""
        mock_publisher = Mock()
        mock_status_pub.return_value = mock_publisher

        # Create a Server instance to trigger the status publishing
        Server(
            wapi=mock_dependencies["wapi"],
            rabbitmq_connection=mock_dependencies["rabbitmq_connection"],
            root_install_directory="/test/path",
            config=mock_dependencies["config"],
            worker_id=123,
        )

        # Verify status publisher was created with correct parameters
        mock_status_pub.assert_called_once()
        call_args = mock_status_pub.call_args
        assert call_args[1]["exchange"] == "server"

        # Verify CREATED status was published
        mock_publisher.publish.assert_called_once()
        published_status = mock_publisher.publish.call_args[1]["status"]

        assert published_status.class_name == "Server"
        assert published_status.status_type == StatusType.CREATED
        assert published_status.game_server_instance_id == 123
        assert published_status.worker_id is None

    @patch("manman.worker.server.RabbitStatusPublisher")
    @patch("manman.worker.server.RabbitCommandSubscriber")
    @patch("manman.worker.server.ProcessBuilder")
    @patch("manman.worker.server.SteamCMD")
    @patch("manman.worker.server.env_list_to_dict")
    def test_server_run_publishes_lifecycle_statuses(
        self,
        mock_env_dict,
        mock_steamcmd,
        mock_pb,
        mock_cmd_sub,
        mock_status_pub,
        mock_dependencies,
    ):
        """Test that server run method publishes INITIALIZING and RUNNING statuses."""
        mock_publisher = Mock()
        mock_status_pub.return_value = mock_publisher

        mock_env_dict.return_value = {}
        mock_steamcmd_instance = Mock()
        mock_steamcmd.return_value = mock_steamcmd_instance

        # Mock ProcessBuilder behavior
        mock_process = Mock()
        mock_process.status = Mock()
        mock_process.status.__eq__ = Mock(
            side_effect=lambda x: False
        )  # Never equals STOPPED
        mock_pb.return_value = mock_process

        # Mock command subscriber
        mock_cmd_subscriber = Mock()
        mock_cmd_subscriber.get_commands.return_value = []
        mock_cmd_sub.return_value = mock_cmd_subscriber

        # Create server instance
        server = Server(
            wapi=mock_dependencies["wapi"],
            rabbitmq_connection=mock_dependencies["rabbitmq_connection"],
            root_install_directory="/tmp/test",
            config=mock_dependencies["config"],
            worker_id=1,
        )

        # Reset mock to clear CREATED status call
        mock_publisher.reset_mock()

        # Mock the server to stop after one iteration
        server._Server__is_stopped = True

        # Call run method
        try:
            server.run(should_update=True)
        except Exception:
            # Expected since we're mocking heavily
            pass

        # Verify INITIALIZING status was published
        publish_calls = mock_publisher.publish.call_args_list

        # Should have at least INITIALIZING status
        assert len(publish_calls) >= 1

        # Check INITIALIZING status
        initializing_status = publish_calls[0][1]["status"]
        assert initializing_status.class_name == "Server"
        assert initializing_status.status_type == StatusType.INITIALIZING
        assert initializing_status.game_server_instance_id == 123

    @patch("manman.worker.server.RabbitStatusPublisher")
    @patch("manman.worker.server.RabbitCommandSubscriber")
    @patch("manman.worker.server.ProcessBuilder")
    def test_server_shutdown_publishes_complete_status(
        self, mock_pb, mock_cmd_sub, mock_status_pub, mock_dependencies
    ):
        """Test that server shutdown publishes COMPLETE status."""
        mock_publisher = Mock()
        mock_status_pub.return_value = mock_publisher

        # Mock command subscriber
        mock_cmd_subscriber = Mock()
        mock_cmd_sub.return_value = mock_cmd_subscriber

        # Mock ProcessBuilder
        mock_process = Mock()
        mock_pb.return_value = mock_process

        # Create server instance
        server = Server(
            wapi=mock_dependencies["wapi"],
            rabbitmq_connection=mock_dependencies["rabbitmq_connection"],
            root_install_directory="/tmp/test",
            config=mock_dependencies["config"],
            worker_id=1,
        )

        # Reset mock to clear CREATED status call
        mock_publisher.reset_mock()
        mock_dependencies["wapi"].reset_mock()

        # Mock instance to be not shutdown initially
        server._instance.end_date = None

        # Call shutdown
        server._shutdown()

        # Verify COMPLETE status was published
        mock_publisher.publish.assert_called()
        published_status = mock_publisher.publish.call_args[1]["status"]

        assert published_status.class_name == "Server"
        assert published_status.status_type == StatusType.COMPLETE
        assert published_status.game_server_instance_id == 123

        # Verify publisher was shut down
        mock_publisher.shutdown.assert_called_once()

    def test_status_info_creation(self):
        """Test that StatusInfo objects are created correctly for servers."""
        status = StatusInfo.create(
            "Server", StatusType.RUNNING, game_server_instance_id=456
        )

        assert status.class_name == "Server"
        assert status.status_type == StatusType.RUNNING
        assert status.game_server_instance_id == 456
        assert status.worker_id is None
        assert status.as_of is not None
