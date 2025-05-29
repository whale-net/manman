"""
Unit tests for the internal API that combines all endpoints.

Tests that the internal API correctly exposes all endpoints from:
- Experience API
- Status API  
- Worker DAL API
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from manman.host.api.experience import router as experience_router
from manman.host.api.status import router as status_router
from manman.host.api.worker_dal import server_router, worker_router


@pytest.fixture
def internal_client():
    """Create a test client for the internal API with all routers."""
    app = FastAPI(title="ManMan Internal API")
    app.include_router(experience_router)
    app.include_router(status_router)
    app.include_router(server_router)
    app.include_router(worker_router)
    return TestClient(app)


class TestInternalApiRouters:
    """Test that the internal API includes all expected routers."""

    def test_has_status_endpoints(self, internal_client, mock_status_repository):
        """Test that status endpoints are available in internal API."""
        # Configure mock to avoid 404
        mock_status_repository.get_latest_worker_status.return_value = None
        
        response = internal_client.get("/status/worker/123")
        # Should get 404 from status API (not 404 for route not found)
        assert response.status_code == 404
        assert "Worker not found" in response.json()["detail"]

    def test_has_worker_dal_endpoints(self, internal_client, mock_worker_repository):
        """Test that worker DAL endpoints are available in internal API."""
        # Configure mock to return a worker
        from datetime import datetime
        from manman.models import Worker
        
        expected_worker = Worker(
            worker_id=123,
            created_date=datetime(2024, 1, 1, 0, 0, 0),
            end_date=None,
            last_heartbeat=None,
        )
        mock_worker_repository.create_worker.return_value = expected_worker
        
        response = internal_client.post("/worker/create")
        assert response.status_code == 200
        assert response.json()["worker_id"] == 123

    def test_has_experience_endpoints(self, internal_client):
        """Test that experience endpoints are available in internal API."""
        # Experience API endpoints should be accessible
        # Use /gameserver endpoint which exists in experience API
        response = internal_client.get("/gameserver")
        # Should not be 404 for route not found - might be 500 or other error, but route should exist
        assert response.status_code != 404 or "Not Found" not in response.text