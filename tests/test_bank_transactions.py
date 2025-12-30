"""Tests for bank transaction import with idempotency."""

import pytest


class TestBankTransactionImport:
    """Tests for bank transaction bulk import."""

    def test_import_transactions_success(self, client, sample_tenant):
        """Test successful transaction import."""
        transactions = [
            {
                "external_id": "TXN-100",
                "posted_at": "2024-01-15T12:00:00Z",
                "amount": "500.00",
                "currency": "USD",
                "description": "Test payment",
            },
        ]

        response = client.post(
            f"/tenants/{sample_tenant['id']}/bank-transactions/import",
            json={"transactions": transactions},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["imported"] == 1
        assert data["skipped"] == 0
        assert len(data["transactions"]) == 1

    def test_import_transactions_with_duplicates(self, client, sample_tenant):
        """Test import skips duplicates by external_id."""
        transactions = [
            {
                "external_id": "TXN-DUP",
                "posted_at": "2024-01-15T12:00:00Z",
                "amount": "500.00",
                "description": "First import",
            },
        ]

        # First import
        response = client.post(
            f"/tenants/{sample_tenant['id']}/bank-transactions/import",
            json={"transactions": transactions},
        )
        assert response.status_code == 201
        assert response.json()["imported"] == 1

        # Second import with same external_id
        transactions[0]["description"] = "Second import"
        response = client.post(
            f"/tenants/{sample_tenant['id']}/bank-transactions/import",
            json={"transactions": transactions},
        )
        assert response.status_code == 201
        assert response.json()["imported"] == 0
        assert response.json()["skipped"] == 1


class TestIdempotency:
    """Tests for idempotency key handling."""

    def test_idempotency_same_key_same_payload(self, client, sample_tenant):
        """Test idempotent request returns cached result."""
        transactions = [
            {
                "external_id": "TXN-IDEM-1",
                "posted_at": "2024-01-15T12:00:00Z",
                "amount": "100.00",
                "description": "Test",
            },
        ]
        idempotency_key = "idem-key-001"

        # First request
        response1 = client.post(
            f"/tenants/{sample_tenant['id']}/bank-transactions/import",
            json={"transactions": transactions},
            headers={"Idempotency-Key": idempotency_key},
        )
        assert response1.status_code == 201
        data1 = response1.json()
        assert data1["imported"] == 1

        # Second request with same key and payload
        response2 = client.post(
            f"/tenants/{sample_tenant['id']}/bank-transactions/import",
            json={"transactions": transactions},
            headers={"Idempotency-Key": idempotency_key},
        )
        assert response2.status_code == 201
        data2 = response2.json()

        # Should return same result (cached)
        assert data2["imported"] == data1["imported"]
        assert data2["skipped"] == data1["skipped"]

    def test_idempotency_same_key_different_payload(self, client, sample_tenant):
        """Test idempotency key reuse with different payload returns conflict."""
        idempotency_key = "idem-key-002"

        # First request
        transactions1 = [
            {
                "external_id": "TXN-IDEM-2",
                "posted_at": "2024-01-15T12:00:00Z",
                "amount": "100.00",
            },
        ]
        response1 = client.post(
            f"/tenants/{sample_tenant['id']}/bank-transactions/import",
            json={"transactions": transactions1},
            headers={"Idempotency-Key": idempotency_key},
        )
        assert response1.status_code == 201

        # Second request with same key but different payload
        transactions2 = [
            {
                "external_id": "TXN-IDEM-3",
                "posted_at": "2024-01-16T12:00:00Z",
                "amount": "200.00",
            },
        ]
        response2 = client.post(
            f"/tenants/{sample_tenant['id']}/bank-transactions/import",
            json={"transactions": transactions2},
            headers={"Idempotency-Key": idempotency_key},
        )

        # Should return 409 Conflict
        assert response2.status_code == 409
        assert "conflict" in response2.json()["error"]

    def test_idempotency_different_keys(self, client, sample_tenant):
        """Test different idempotency keys create separate records."""
        transactions = [
            {
                "external_id": "TXN-IDEM-4",
                "posted_at": "2024-01-15T12:00:00Z",
                "amount": "100.00",
            },
        ]

        # First request with key 1
        response1 = client.post(
            f"/tenants/{sample_tenant['id']}/bank-transactions/import",
            json={"transactions": transactions},
            headers={"Idempotency-Key": "idem-key-003"},
        )
        assert response1.status_code == 201
        assert response1.json()["imported"] == 1

        # Change external_id for second import
        transactions[0]["external_id"] = "TXN-IDEM-5"

        # Second request with key 2
        response2 = client.post(
            f"/tenants/{sample_tenant['id']}/bank-transactions/import",
            json={"transactions": transactions},
            headers={"Idempotency-Key": "idem-key-004"},
        )
        assert response2.status_code == 201
        assert response2.json()["imported"] == 1

    def test_import_without_idempotency_key(self, client, sample_tenant):
        """Test import works without idempotency key."""
        transactions = [
            {
                "external_id": "TXN-NO-KEY",
                "posted_at": "2024-01-15T12:00:00Z",
                "amount": "100.00",
            },
        ]

        response = client.post(
            f"/tenants/{sample_tenant['id']}/bank-transactions/import",
            json={"transactions": transactions},
        )

        assert response.status_code == 201
        assert response.json()["imported"] == 1
