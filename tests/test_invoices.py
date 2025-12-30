"""Tests for invoice endpoints."""

import pytest
from datetime import date


class TestCreateInvoice:
    """Tests for invoice creation."""

    @pytest.mark.asyncio
    async def test_create_invoice_success(self, client, sample_tenant, sample_vendor):
        """Test successful invoice creation."""
        response = await client.post(
            f"/tenants/{sample_tenant['id']}/invoices",
            json={
                "vendor_id": sample_vendor["id"],
                "invoice_number": "INV-002",
                "amount": "500.00",
                "currency": "USD",
                "invoice_date": "2024-01-20",
                "description": "Product purchase",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["invoice_number"] == "INV-002"
        assert data["amount"] == "500.00"
        assert data["currency"] == "USD"
        assert data["status"] == "open"
        assert data["tenant_id"] == sample_tenant["id"]

    @pytest.mark.asyncio
    async def test_create_invoice_without_vendor(self, client, sample_tenant):
        """Test creating invoice without vendor."""
        response = await client.post(
            f"/tenants/{sample_tenant['id']}/invoices",
            json={
                "amount": "750.00",
                "description": "Misc expense",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["vendor_id"] is None
        assert data["amount"] == "750.00"

    @pytest.mark.asyncio
    async def test_create_invoice_invalid_tenant(self, client):
        """Test creating invoice with non-existent tenant."""
        response = await client.post(
            "/tenants/non-existent-tenant/invoices",
            json={"amount": "100.00"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_invoice_missing_amount(self, client, sample_tenant):
        """Test creating invoice without required amount."""
        response = await client.post(
            f"/tenants/{sample_tenant['id']}/invoices",
            json={"description": "No amount"},
        )

        assert response.status_code == 422


class TestListInvoices:
    """Tests for invoice listing and filtering."""

    @pytest.mark.asyncio
    async def test_list_invoices_empty(self, client, sample_tenant):
        """Test listing invoices when none exist."""
        response = await client.get(f"/tenants/{sample_tenant['id']}/invoices")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_invoices_with_data(self, client, sample_tenant, sample_invoice):
        """Test listing invoices with existing data."""
        response = await client.get(f"/tenants/{sample_tenant['id']}/invoices")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == sample_invoice["id"]

    @pytest.mark.asyncio
    async def test_list_invoices_filter_by_status(self, client, sample_tenant, sample_invoice):
        """Test filtering invoices by status."""
        # Filter by open status
        response = await client.get(
            f"/tenants/{sample_tenant['id']}/invoices",
            params={"status": "open"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

        # Filter by matched status
        response = await client.get(
            f"/tenants/{sample_tenant['id']}/invoices",
            params={"status": "matched"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_invoices_filter_by_amount_range(
        self, client, sample_tenant, sample_vendor
    ):
        """Test filtering invoices by amount range."""
        # Create invoices with different amounts
        for amount in ["100.00", "500.00", "1000.00"]:
            await client.post(
                f"/tenants/{sample_tenant['id']}/invoices",
                json={"amount": amount},
            )

        # Filter by amount range
        response = await client.get(
            f"/tenants/{sample_tenant['id']}/invoices",
            params={"amount_min": "400", "amount_max": "600"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["amount"] == "500.00"

    @pytest.mark.asyncio
    async def test_list_invoices_filter_by_vendor(
        self, client, sample_tenant, sample_vendor, sample_invoice
    ):
        """Test filtering invoices by vendor."""
        # Create another invoice without vendor
        await client.post(
            f"/tenants/{sample_tenant['id']}/invoices",
            json={"amount": "200.00"},
        )

        response = await client.get(
            f"/tenants/{sample_tenant['id']}/invoices",
            params={"vendor_id": sample_vendor["id"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["vendor_id"] == sample_vendor["id"]


class TestDeleteInvoice:
    """Tests for invoice deletion."""

    @pytest.mark.asyncio
    async def test_delete_invoice_success(self, client, sample_tenant, sample_invoice):
        """Test successful invoice deletion."""
        response = await client.delete(
            f"/tenants/{sample_tenant['id']}/invoices/{sample_invoice['id']}"
        )

        assert response.status_code == 204

        # Verify deletion
        response = await client.get(
            f"/tenants/{sample_tenant['id']}/invoices/{sample_invoice['id']}"
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_invoice_not_found(self, client, sample_tenant):
        """Test deleting non-existent invoice."""
        response = await client.delete(
            f"/tenants/{sample_tenant['id']}/invoices/non-existent-id"
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_invoice_wrong_tenant(self, client, sample_invoice):
        """Test deleting invoice from wrong tenant (isolation test)."""
        # Create another tenant
        response = await client.post("/tenants", json={"name": "Other Company"})
        other_tenant = response.json()

        # Try to delete invoice from wrong tenant
        response = await client.delete(
            f"/tenants/{other_tenant['id']}/invoices/{sample_invoice['id']}"
        )

        assert response.status_code == 404
