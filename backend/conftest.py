"""Shared pytest configuration and fixtures.

Every fixture that other test files used to redefine locally (mock_env,
in-memory DB setup, S3 mocking) now lives here and is applied automatically
(autouse) so individual test files don't need to duplicate it.
"""
import os
import sys
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add backend directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))


@pytest.fixture(scope="session")
def monkeypatch_session():
    """Session-scoped monkeypatch fixture."""
    with pytest.MonkeyPatch.context() as m:
        yield m


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """Mock environment variables for testing. Applies to every test."""
    env_vars = {
        "DATABASE_URL": "sqlite:///:memory:",
        "MINIO_INTERNAL_URL": "http://minio-test:9000",
        "MINIO_PUBLIC_URL": "http://localhost:9000",
        "S3_BUCKET": "test-bucket",
        "MINIO_ACCESS_KEY": "test_access_key",
        "MINIO_SECRET_KEY": "test_secret_key",
        "SECRET_KEY": "test-secret-key-for-jwt",
        "ALGORITHM": "HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
        "DEFAULT_STORAGE_BYTES": "1073741824",  # 1 GB
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, mock_env):
    # Depends explicitly on mock_env to guarantee env vars (in particular
    # DATABASE_URL) are set *before* `db` is imported for the first time,
    # since db.py builds its engine at module import time.
    """
    Give every single test a fresh, isolated in-memory SQLite database.

    Replaces the ad-hoc "mock_db" / "setup_db" fixtures that used to be
    copy-pasted (with the schema duplicated as raw SQL, or with `db.Base`
    itself mocked out) into test_authorization.py, test_db.py,
    test_storage.py and test_cloudstorage.py. All of those approaches are
    gone now; this is the single source of truth for test DB setup, and it
    uses the *real* SQLAlchemy models (db.Base.metadata.create_all) so the
    schema can never drift from the actual application code.
    """
    from db import Base

    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(bind=test_engine)

    monkeypatch.setattr("db.engine", test_engine)
    monkeypatch.setattr("db.SessionLocal", TestSessionLocal)

    yield test_engine


@pytest.fixture(autouse=True)
def mock_s3_clients(monkeypatch, mock_env):
    """
    Replace the boto3 S3 clients used by storage.py with MagicMocks for
    every test, so no test can accidentally hit a real MinIO/S3 endpoint.
    Individual tests can still further customize behaviour (e.g. make a
    method raise) via monkeypatch on top of this.
    """
    import storage

    mock_s3 = MagicMock()
    mock_s3_public = MagicMock()
    monkeypatch.setattr(storage, "s3", mock_s3)
    monkeypatch.setattr(storage, "s3_public", mock_s3_public)
    return mock_s3, mock_s3_public


@pytest.fixture
def db_session(isolated_db):
    """Create a session bound to the isolated test database."""
    from db import SessionLocal

    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def client(isolated_db, mock_s3_clients):
    """Create a FastAPI test client wired to the isolated test DB / mocked S3."""
    from fastapi.testclient import TestClient
    import CloudStorage

    return TestClient(CloudStorage.app)


@pytest.fixture
def test_user_data():
    """Test user data."""
    return {
        "login": "testuser",
        "password": "testpass123",
    }


@pytest.fixture
def registered_user(client, test_user_data):
    """Register a test user and return the user data."""
    response = client.post("/register", json=test_user_data)
    assert response.status_code == 200
    return test_user_data


@pytest.fixture
def auth_headers(client, test_user_data, registered_user):
    """
    Register + log in a user via real HTTP calls and return a dict with a
    valid Bearer Authorization header, ready to use against any protected
    endpoint (including /files/*). This is what lets us write genuine
    end-to-end HTTP tests instead of calling router functions directly.
    """
    response = client.post(
        "/token",
        data={"username": test_user_data["login"], "password": test_user_data["password"]},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
