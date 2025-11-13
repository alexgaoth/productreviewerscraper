"""Tests for API endpoints."""

import pytest
from unittest.mock import AsyncMock, patch


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_root_endpoint(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert "version" in data


@pytest.mark.asyncio
async def test_oauth_callback(client, db_session, mock_lwa_token_response):
    """Test OAuth callback endpoint."""
    with patch("app.api.routes.lwa_client.exchange_code_for_tokens") as mock_exchange:
        # Mock token exchange
        mock_token_response = AsyncMock()
        mock_token_response.access_token = mock_lwa_token_response["access_token"]
        mock_token_response.refresh_token = mock_lwa_token_response["refresh_token"]
        mock_token_response.expires_at = None
        mock_exchange.return_value = mock_token_response

        response = client.post(
            "/api/v1/auth/amazon/callback",
            json={
                "code": "test_code",
                "state": "test_state",
                "seller_id": "A1TESTSELLER",
                "marketplace_id": "ATVPDKIKX0DER",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["seller_id"] == "A1TESTSELLER"


def test_fetch_reviews_seller_not_found(client):
    """Test fetch reviews with non-existent seller."""
    response = client.post(
        "/api/v1/fetch/reviews",
        json={
            "seller_id": "NONEXISTENT",
            "marketplace_id": "ATVPDKIKX0DER",
            "asins": ["B07TEST"],
        },
    )

    assert response.status_code == 404


def test_job_status_not_found(client):
    """Test job status for non-existent job."""
    response = client.get("/api/v1/jobs/nonexistent/status")
    assert response.status_code == 404
