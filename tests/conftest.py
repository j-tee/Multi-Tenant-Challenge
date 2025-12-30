"""Test configuration and fixtures."""

import pytest
from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.main import app
from app.models import Base


# Create in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def db_engine():
    """Create a test database engine."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Enable foreign keys for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create a test database session."""
    # Create tables
    Base.metadata.create_all(bind=db_engine)

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=db_engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with the test database."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def sample_tenant(client):
    """Create a sample tenant for testing."""
    response = client.post("/tenants", json={"name": "Test Company"})
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def sample_vendor(client, sample_tenant):
    """Create a sample vendor for testing."""
    response = client.post(
        f"/tenants/{sample_tenant['id']}/vendors",
        json={"name": "Acme Corp"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def sample_invoice(client, sample_tenant, sample_vendor):
    """Create a sample invoice for testing."""
    response = client.post(
        f"/tenants/{sample_tenant['id']}/invoices",
        json={
            "vendor_id": sample_vendor["id"],
            "invoice_number": "INV-001",
            "amount": "1000.00",
            "currency": "USD",
            "invoice_date": "2024-01-15",
            "description": "Consulting services",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def sample_bank_transactions(client, sample_tenant):
    """Create sample bank transactions for testing."""
    transactions = [
        {
            "external_id": "TXN-001",
            "posted_at": "2024-01-15T12:00:00Z",
            "amount": "1000.00",
            "currency": "USD",
            "description": "Payment from Acme Corp - INV-001",
        },
        {
            "external_id": "TXN-002",
            "posted_at": "2024-01-16T14:00:00Z",
            "amount": "500.00",
            "currency": "USD",
            "description": "Office supplies",
        },
        {
            "external_id": "TXN-003",
            "posted_at": "2024-01-18T10:00:00Z",
            "amount": "1000.00",
            "currency": "USD",
            "description": "Random payment",
        },
    ]

    response = client.post(
        f"/tenants/{sample_tenant['id']}/bank-transactions/import",
        json={"transactions": transactions},
        headers={"Idempotency-Key": "test-import-001"},
    )
    assert response.status_code == 201
    return response.json()
