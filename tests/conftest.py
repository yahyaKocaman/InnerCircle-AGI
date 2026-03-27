"""
Test Configuration — conftest.py
──────────────────────────────────
Sets up an isolated in-memory SQLite database for every test session.
The real database is NEVER touched during tests.

Pattern: Override the `get_db` FastAPI dependency with a test session,
run the tests, and tear down the schema afterwards.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from app.infrastructure.database import Base
from app.api.deps import get_db

# ── In-memory database (isolated per test run) ───────────────
TEST_DB_URL = "sqlite://"   # no file — lives purely in RAM


@pytest.fixture(scope="session")
def db_engine():
    """Create engine + schema once per test session."""
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Fresh transaction per test — rolled back after each test."""
    connection = db_engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session):
    """TestClient with the real app but an isolated test database."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass  # rollback handled in db_session fixture

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


# ── Reusable helpers ─────────────────────────────────────────
@pytest.fixture()
def registered_user(client):
    """Register a test user and return the response JSON."""
    resp = client.post("/auth/register", json={
        "username":  "testuser",
        "email":     "testuser@example.com",
        "full_name": "Test User",
        "password":  "testpass123",
    })
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture()
def auth_headers(client, registered_user):
    """Login and return Authorization headers for authenticated requests."""
    resp = client.post("/auth/login", json={
        "username": "testuser",
        "password": "testpass123",
    })
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
