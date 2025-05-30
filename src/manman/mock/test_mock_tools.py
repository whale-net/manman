#!/usr/bin/env python3
"""
Quick test script to demonstrate mock worker and server functionality.

This script can be used to verify that the mock implementations work correctly
without needing a full ManMan environment setup.
"""
import sys
import os
from unittest.mock import Mock, patch

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))


def test_mock_processbuilder():
    """Test the MockProcessBuilder functionality."""
    print("=== Testing MockProcessBuilder ===")
    
    from manman.mock.processbuilder import MockProcessBuilder
    from manman.worker.processbuilder import ProcessBuilderStatus
    import time
    
    # Create a mock process builder
    pb = MockProcessBuilder("test_server.exe", stdin_delay_seconds=1)
    print(f"Initial status: {pb.status}")
    
    # Add some parameters
    pb.add_parameter("--port", "27015", "--map", "de_dust2")
    pb.add_parameter_stdin("changelevel de_mirage")
    
    # Render the command
    command, stdin = pb.render_command()
    print(f"Command: {command}")
    print(f"Stdin: {stdin}")
    
    # Run the process
    print("Starting mock process...")
    pb.run()
    print(f"Status after run: {pb.status}")
    
    # Wait for it to enter RUNNING state
    print("Waiting for RUNNING state...")
    time.sleep(1.1)
    print(f"Status after delay: {pb.status}")
    
    # Write some stdin
    pb.write_stdin("status")
    
    # Stop the process
    print("Stopping mock process...")
    pb.stop()
    print(f"Final status: {pb.status}")
    
    print("MockProcessBuilder test completed!\n")


def test_mock_server():
    """Test the MockServer functionality."""
    print("=== Testing MockServer ===")
    
    with patch("manman.mock.server.RabbitCommandSubscriber") as mock_cmd_sub, \
         patch("manman.mock.server.RabbitStatusPublisher") as mock_status_pub:
        
        from manman.mock.server import MockServer
        from manman.models import Command, CommandType
        
        # Setup mocks
        mock_cmd_sub.return_value = Mock()
        mock_status_pub.return_value = Mock()
        
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
        mock_game_server.server_type = 1  # STEAM
        mock_game_server.app_id = 730
        mock_wapi.game_server.return_value = mock_game_server

        # Create mock server
        print("Creating MockServer...")
        server = MockServer(
            wapi=mock_wapi,
            rabbitmq_connection=Mock(),
            root_install_directory="/tmp/test",
            config=mock_config,
            worker_id=1,
        )
        
        print(f"Server instance ID: {server.instance.game_server_instance_id}")
        print(f"Command routing key: {server.command_routing_key}")
        print(f"Status routing key: {server.status_routing_key}")
        
        # Test command execution
        print("Testing STDIN command...")
        stdin_cmd = Command(command_type=CommandType.STDIN, command_args=["123", "test", "command"])
        server.execute_command(stdin_cmd)
        
        print("Testing STOP command...")
        stop_cmd = Command(command_type=CommandType.STOP, command_args=["123"])
        server.execute_command(stop_cmd)
        
        print(f"Server is shutdown: {server.is_shutdown}")
        print("MockServer test completed!\n")


def test_queue_names():
    """Test queue name generation."""
    print("=== Testing Queue Name Generation ===")
    
    from manman.mock.worker_service import MockWorkerService
    from manman.mock.server import MockServer
    
    # Test worker queue names
    worker_id = 42
    worker_cmd_queue = MockWorkerService.generate_command_queue_name(worker_id)
    worker_status_queue = MockWorkerService.generate_status_queue_name(worker_id)
    
    print(f"Worker {worker_id} command queue: {worker_cmd_queue}")
    print(f"Worker {worker_id} status queue: {worker_status_queue}")
    
    # Test server queue names
    instance_id = 123
    server_cmd_queue = MockServer.generate_command_queue_name(instance_id)
    server_status_queue = MockServer.generate_status_queue_name(instance_id)
    
    print(f"Server instance {instance_id} command queue: {server_cmd_queue}")
    print(f"Server instance {instance_id} status queue: {server_status_queue}")
    
    print("Queue name generation test completed!\n")


def main():
    """Run all tests."""
    print("ManMan Mock Tools Test Script")
    print("=" * 50)
    
    try:
        test_mock_processbuilder()
        test_mock_server()
        test_queue_names()
        
        print("🎉 All tests passed! Mock tools are working correctly.")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()