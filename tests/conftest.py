"""Pytest configuration and fixtures."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.models import Base
from app.database import get_db_session
from app.main import app


# Test database
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def db_session():
    """Create test database session."""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create tables
    Base.metadata.create_all(bind=engine)

    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Create test client with database override."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db_session] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def mock_lwa_token_response():
    """Mock LWA token response."""
    return {
        "access_token": "Atza|test_access_token",
        "refresh_token": "Atzr|test_refresh_token",
        "token_type": "bearer",
        "expires_in": 3600,
    }


@pytest.fixture
def mock_spapi_reviews_response():
    """Mock SP-API reviews response."""
    return {
        "reviews": [
            {
                "reviewId": "R1TEST",
                "reviewerId": "A2REVIEWER",
                "reviewerName": "Test User",
                "rating": 5,
                "title": "Great product",
                "body": "This is a test review",
                "verifiedPurchase": True,
                "helpfulVotes": 10,
                "language": "en-US",
                "reviewDate": "2025-11-01T00:00:00Z",
            },
            {
                "reviewId": "R2TEST",
                "reviewerId": "A3REVIEWER",
                "reviewerName": "Another User",
                "rating": 4,
                "title": "Good product",
                "body": "Another test review",
                "verifiedPurchase": True,
                "helpfulVotes": 5,
                "language": "en-US",
                "reviewDate": "2025-11-02T00:00:00Z",
            },
        ],
        "nextToken": None,
    }
