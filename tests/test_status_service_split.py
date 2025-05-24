"""
Test suite for ManMan status service split implementation.

This module tests that our status services can be imported and started correctly
after splitting the monolithic status service into separate API and processor services.
"""

import sys
from pathlib import Path

import pytest

# Add the src directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))


class TestStatusServiceSplit:
    """Test suite for the status service split implementation."""

    def test_status_api_import(self):
        """Test that the Status API can be imported."""
        from manman.host.api.status import router as status_router

        assert status_router is not None

    def test_status_processor_import(self):
        """Test that the Status Processor can be imported."""
        from manman.host.status_processor import StatusEventProcessor

        assert StatusEventProcessor is not None

    def test_main_module_import(self):
        """Test that the main module can be imported."""
        from manman.host.main import app

        assert app is not None

    def test_fastapi_app_creation(self):
        """Test creating a FastAPI app with our status routes."""
        from fastapi import FastAPI

        from manman.host.api.shared import add_health_check
        from manman.host.api.status import router as status_router

        status_app = FastAPI(title="ManMan Status API")
        status_app.include_router(status_router)
        add_health_check(status_app, prefix="/status")

        assert status_app is not None
        assert len(status_app.routes) > 0

        # Check that we have the expected routes (they have /status prefix)
        route_paths = [route.path for route in status_app.routes]
        assert "/status/health" in route_paths
        assert "/status/workers" in route_paths
        assert "/status/workers/{worker_id}" in route_paths
        assert "/status/servers" in route_paths
        assert "/status/servers/active" in route_paths
        assert "/status/system" in route_paths

    def test_status_api_endpoints_available(self):
        """Test that all expected status API endpoints are available."""
        from manman.host.api.status import router as status_router

        # Get all the route paths from the router
        route_paths = [route.path for route in status_router.routes]

        expected_endpoints = [
            "/status/workers",
            "/status/workers/{worker_id}",
            "/status/servers",
            "/status/servers/active",
            "/status/system",
        ]

        for endpoint in expected_endpoints:
            assert endpoint in route_paths, f"Missing endpoint: {endpoint}"

    def test_status_processor_class_structure(self):
        """Test that the StatusEventProcessor has the expected methods."""
        from manman.host.status_processor import StatusEventProcessor

        # Check that the class has the expected methods
        assert hasattr(StatusEventProcessor, "__init__")
        assert hasattr(StatusEventProcessor, "run")
        assert hasattr(StatusEventProcessor, "_handle_heartbeat_event")
        assert hasattr(StatusEventProcessor, "_handle_server_started_event")
        assert hasattr(StatusEventProcessor, "_handle_server_stopped_event")

    def test_models_import_successfully(self):
        """Test that our data models can be imported without issues."""
        from manman import models

        # Test that key models are available
        assert hasattr(models, "Worker")
        assert hasattr(models, "GameServerInstance")
        assert hasattr(models, "CommandType")
        assert hasattr(models, "Command")

        # Test that we have the new command types for heartbeat
        assert hasattr(models.CommandType, "HEARTBEAT")
        assert hasattr(models.CommandType, "SERVER_STARTED")
        assert hasattr(models.CommandType, "SERVER_STOPPED")


class TestServiceCommands:
    """Test the CLI commands for starting services."""

    def test_main_app_has_all_commands(self):
        """Test that the main typer app has all expected commands."""
        from manman.host.main import app

        # Get command names from the typer app
        command_names = [cmd.callback.__name__ for cmd in app.registered_commands]

        expected_commands = [
            "start_experience_api",
            "start_status_api",
            "start_worker_dal_api",
            "start_status_processor",
            "run_migration",
            "create_migration",
        ]

        for cmd in expected_commands:
            assert cmd in command_names, f"Missing command: {cmd}"

    def test_status_commands_have_correct_signatures(self):
        """Test that status-related commands have the expected parameters."""
        import inspect

        from manman.host.main import start_status_api, start_status_processor

        # Check start_status_api parameters
        api_sig = inspect.signature(start_status_api)
        api_params = list(api_sig.parameters.keys())

        expected_params = [
            "rabbitmq_host",
            "rabbitmq_port",
            "rabbitmq_username",
            "rabbitmq_password",
            "app_env",
            "port",
            "should_run_migration_check",
            "enable_ssl",
            "rabbitmq_ssl_hostname",
        ]

        for param in expected_params:
            assert param in api_params, (
                f"Missing parameter in start_status_api: {param}"
            )

        # Check start_status_processor parameters
        processor_sig = inspect.signature(start_status_processor)
        processor_params = list(processor_sig.parameters.keys())

        # Processor should have same params except port (no HTTP server)
        expected_processor_params = [p for p in expected_params if p != "port"]

        for param in expected_processor_params:
            assert param in processor_params, (
                f"Missing parameter in start_status_processor: {param}"
            )

        # Processor should NOT have port parameter
        assert "port" not in processor_params, (
            "start_status_processor should not have port parameter"
        )


if __name__ == "__main__":
    # Allow running this file directly for quick testing
    pytest.main([__file__, "-v"])
