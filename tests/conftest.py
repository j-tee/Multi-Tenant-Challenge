"""Test configuration and fixtures with async support."""

import os
import tempfile
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from typing import AsyncGenerator

from httpx import AsyncClient, ASGITransport
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_async_db
from app.main import app
from app.models import Base


@pytest.fixture(scope="function")
def temp_db_path():
    """Create a temporary database file path."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture(scope="function")
async def async_db_engine(temp_db_path):
    """Create an async test database engine."""
    db_url = f"sqlite+aiosqlite:///{temp_db_path}"
    engine = create_async_engine(
        db_url,
        connect_args={"check_same_thread": False},
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture(scope="function")
async def client(async_db_engine):
    """Create a test client with the test database."""
    
    # Override AI settings for testing - disable AI to use fallback
    from app.core.config import get_settings
    settings = get_settings()
    original_ai_enabled = settings.ai_enabled
    settings.ai_enabled = False
    
    AsyncTestingSessionLocal = async_sessionmaker(
        async_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async def override_get_async_db() -> AsyncGenerator[AsyncSession, None]:
        async with AsyncTestingSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_async_db] = override_get_async_db
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    settings.ai_enabled = original_ai_enabled


@pytest.fixture
async def sample_tenant(client):
    """Create a sample tenant for testing."""
    response = await client.post("/tenants", json={"name": "Test Company"})
    assert response.status_code == 201
    return response.json()


@pytest.fixture
async def sample_vendor(client, sample_tenant):
    """Create a sample vendor for testing."""
    response = await client.post(
        f"/tenants/{sample_tenant['id']}/vendors",
        json={"name": "Acme Corp"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
async def sample_invoice(client, sample_tenant, sample_vendor):
    """Create a sample invoice for testing."""
    response = await client.post(
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
async def sample_bank_transactions(client, sample_tenant):
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

    response = await client.post(
        f"/tenants/{sample_tenant['id']}/bank-transactions/import",
        json={"transactions": transactions},
        headers={"Idempotency-Key": "test-import-001"},
    )
    assert response.status_code == 201
    return response.json()
