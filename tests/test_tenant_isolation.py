"""Tests for multi-tenant isolation."""

import pytest


class TestTenantIsolation:
    """Tests to verify data isolation between tenants."""

    def test_invoice_isolation(self, client):
        """Test that invoices are isolated between tenants."""
        # Create two tenants
        tenant1 = client.post("/tenants", json={"name": "Tenant 1"}).json()
        tenant2 = client.post("/tenants", json={"name": "Tenant 2"}).json()

        # Create invoice for tenant 1
        invoice = client.post(
            f"/tenants/{tenant1['id']}/invoices",
            json={"amount": "100.00", "description": "Tenant 1 invoice"},
        ).json()

        # Tenant 1 should see the invoice
        response = client.get(f"/tenants/{tenant1['id']}/invoices")
        assert response.json()["total"] == 1

        # Tenant 2 should NOT see the invoice
        response = client.get(f"/tenants/{tenant2['id']}/invoices")
        assert response.json()["total"] == 0

        # Tenant 2 should NOT be able to access tenant 1's invoice directly
        response = client.get(f"/tenants/{tenant2['id']}/invoices/{invoice['id']}")
        assert response.status_code == 404

    def test_bank_transaction_isolation(self, client):
        """Test that bank transactions are isolated between tenants."""
        tenant1 = client.post("/tenants", json={"name": "Tenant A"}).json()
        tenant2 = client.post("/tenants", json={"name": "Tenant B"}).json()

        # Import transactions for tenant 1
        client.post(
            f"/tenants/{tenant1['id']}/bank-transactions/import",
            json={
                "transactions": [
                    {
                        "external_id": "ISO-TXN-1",
                        "posted_at": "2024-01-15T12:00:00Z",
                        "amount": "500.00",
                    },
                ]
            },
        )

        # Tenant 1 should see the transaction
        response = client.get(f"/tenants/{tenant1['id']}/bank-transactions")
        assert response.json()["total"] == 1

        # Tenant 2 should NOT see the transaction
        response = client.get(f"/tenants/{tenant2['id']}/bank-transactions")
        assert response.json()["total"] == 0

    def test_match_isolation(self, client):
        """Test that matches are isolated between tenants."""
        tenant1 = client.post("/tenants", json={"name": "Match Tenant 1"}).json()
        tenant2 = client.post("/tenants", json={"name": "Match Tenant 2"}).json()

        # Create invoice for tenant 1
        client.post(
            f"/tenants/{tenant1['id']}/invoices",
            json={"amount": "1000.00", "invoice_date": "2024-05-15"},
        )

        # Import transaction for tenant 1
        client.post(
            f"/tenants/{tenant1['id']}/bank-transactions/import",
            json={
                "transactions": [
                    {
                        "external_id": "MATCH-ISO-1",
                        "posted_at": "2024-05-15T12:00:00Z",
                        "amount": "1000.00",
                    },
                ]
            },
        )

        # Run reconciliation for tenant 1
        client.post(f"/tenants/{tenant1['id']}/reconcile")

        # Tenant 1 should see matches
        response = client.get(f"/tenants/{tenant1['id']}/matches")
        assert len(response.json()["items"]) >= 1

        # Tenant 2 should NOT see any matches
        response = client.get(f"/tenants/{tenant2['id']}/matches")
        assert len(response.json()["items"]) == 0

    def test_vendor_isolation(self, client):
        """Test that vendors are isolated between tenants."""
        tenant1 = client.post("/tenants", json={"name": "Vendor Tenant 1"}).json()
        tenant2 = client.post("/tenants", json={"name": "Vendor Tenant 2"}).json()

        # Create vendor for tenant 1
        vendor = client.post(
            f"/tenants/{tenant1['id']}/vendors",
            json={"name": "Exclusive Vendor"},
        ).json()

        # Tenant 1 should see the vendor
        response = client.get(f"/tenants/{tenant1['id']}/vendors")
        assert len(response.json()["items"]) == 1

        # Tenant 2 should NOT see the vendor
        response = client.get(f"/tenants/{tenant2['id']}/vendors")
        assert len(response.json()["items"]) == 0

        # Tenant 2 should NOT be able to access tenant 1's vendor
        response = client.get(f"/tenants/{tenant2['id']}/vendors/{vendor['id']}")
        assert response.status_code == 404

    def test_cannot_delete_other_tenant_invoice(self, client):
        """Test that one tenant cannot delete another tenant's invoice."""
        tenant1 = client.post("/tenants", json={"name": "Delete Test 1"}).json()
        tenant2 = client.post("/tenants", json={"name": "Delete Test 2"}).json()

        # Create invoice for tenant 1
        invoice = client.post(
            f"/tenants/{tenant1['id']}/invoices",
            json={"amount": "100.00"},
        ).json()

        # Tenant 2 tries to delete tenant 1's invoice
        response = client.delete(f"/tenants/{tenant2['id']}/invoices/{invoice['id']}")
        assert response.status_code == 404

        # Invoice should still exist for tenant 1
        response = client.get(f"/tenants/{tenant1['id']}/invoices/{invoice['id']}")
        assert response.status_code == 200

    def test_idempotency_tenant_scoped(self, client):
        """Test that idempotency keys are tenant-scoped."""
        tenant1 = client.post("/tenants", json={"name": "Idem Tenant 1"}).json()
        tenant2 = client.post("/tenants", json={"name": "Idem Tenant 2"}).json()

        transactions = [
            {
                "external_id": "IDEM-SCOPE-1",
                "posted_at": "2024-06-15T12:00:00Z",
                "amount": "100.00",
            },
        ]

        # Same idempotency key used by different tenants should work independently
        idempotency_key = "shared-key-123"

        # Tenant 1 uses the key
        response1 = client.post(
            f"/tenants/{tenant1['id']}/bank-transactions/import",
            json={"transactions": transactions},
            headers={"Idempotency-Key": idempotency_key},
        )
        assert response1.status_code == 201

        # Tenant 2 uses the same key - should work (different tenant scope)
        transactions[0]["external_id"] = "IDEM-SCOPE-2"
        response2 = client.post(
            f"/tenants/{tenant2['id']}/bank-transactions/import",
            json={"transactions": transactions},
            headers={"Idempotency-Key": idempotency_key},
        )
        # This should succeed because idempotency is tenant-scoped
        assert response2.status_code == 201
