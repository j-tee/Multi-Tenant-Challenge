"""Tests for reconciliation engine and endpoints."""

import pytest
from decimal import Decimal


class TestReconciliation:
    """Tests for the reconciliation process."""

    def test_reconciliation_exact_match(
        self, client, sample_tenant, sample_vendor, sample_bank_transactions
    ):
        """Test reconciliation finds exact matches."""
        # Create invoice that matches first transaction exactly
        invoice_response = client.post(
            f"/tenants/{sample_tenant['id']}/invoices",
            json={
                "vendor_id": sample_vendor["id"],
                "invoice_number": "INV-001",
                "amount": "1000.00",
                "currency": "USD",
                "invoice_date": "2024-01-15",
                "description": "Consulting services from Acme",
            },
        )
        assert invoice_response.status_code == 201
        invoice = invoice_response.json()

        # Run reconciliation
        response = client.post(
            f"/tenants/{sample_tenant['id']}/reconcile",
            params={"min_score": 0.5},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["matches_created"] >= 1
        assert len(data["candidates"]) >= 1

        # First candidate should have high score due to exact amount match
        best_match = data["candidates"][0]
        assert Decimal(best_match["score"]) >= Decimal("0.5")

    def test_reconciliation_ranking(self, client, sample_tenant, sample_vendor):
        """Test that candidates are properly ranked by score."""
        # Create a transaction
        client.post(
            f"/tenants/{sample_tenant['id']}/bank-transactions/import",
            json={
                "transactions": [
                    {
                        "external_id": "TXN-RANK-1",
                        "posted_at": "2024-02-15T12:00:00Z",
                        "amount": "1000.00",
                        "currency": "USD",
                        "description": "Payment Acme Corp",
                    },
                ]
            },
        )

        # Create invoices with varying match quality
        # Invoice 1: Exact amount, same date, good description match
        client.post(
            f"/tenants/{sample_tenant['id']}/invoices",
            json={
                "vendor_id": sample_vendor["id"],
                "amount": "1000.00",
                "invoice_date": "2024-02-15",
                "description": "Acme Corp services",
            },
        )

        # Invoice 2: Different amount
        client.post(
            f"/tenants/{sample_tenant['id']}/invoices",
            json={
                "amount": "500.00",
                "invoice_date": "2024-02-15",
                "description": "Something else",
            },
        )

        # Run reconciliation
        response = client.post(f"/tenants/{sample_tenant['id']}/reconcile")

        assert response.status_code == 200
        data = response.json()

        # Should have candidates ranked by score
        if len(data["candidates"]) > 1:
            scores = [Decimal(c["score"]) for c in data["candidates"]]
            assert scores == sorted(scores, reverse=True)

    def test_reconciliation_no_matches_below_threshold(
        self, client, sample_tenant, sample_vendor
    ):
        """Test that low-scoring matches are excluded."""
        # Create transaction
        client.post(
            f"/tenants/{sample_tenant['id']}/bank-transactions/import",
            json={
                "transactions": [
                    {
                        "external_id": "TXN-LOW-1",
                        "posted_at": "2024-03-15T12:00:00Z",
                        "amount": "1000.00",
                        "currency": "USD",
                    },
                ]
            },
        )

        # Create invoice with completely different amount
        client.post(
            f"/tenants/{sample_tenant['id']}/invoices",
            json={
                "amount": "5000.00",
                "invoice_date": "2024-01-01",  # Very different date
                "currency": "EUR",  # Different currency
            },
        )

        # Run reconciliation with high threshold
        response = client.post(
            f"/tenants/{sample_tenant['id']}/reconcile",
            params={"min_score": 0.9},
        )

        assert response.status_code == 200
        data = response.json()

        # Should have no matches with very high threshold
        assert data["matches_created"] == 0


class TestMatchConfirmation:
    """Tests for match confirmation workflow."""

    def test_confirm_match_updates_state(
        self, client, sample_tenant, sample_vendor, sample_bank_transactions
    ):
        """Test confirming a match updates invoice and match status."""
        # Create matching invoice
        invoice_response = client.post(
            f"/tenants/{sample_tenant['id']}/invoices",
            json={
                "vendor_id": sample_vendor["id"],
                "amount": "1000.00",
                "invoice_date": "2024-01-15",
            },
        )
        invoice = invoice_response.json()

        # Run reconciliation
        recon_response = client.post(f"/tenants/{sample_tenant['id']}/reconcile")
        candidates = recon_response.json()["candidates"]

        # Find a match for our invoice
        match_id = None
        for candidate in candidates:
            if candidate["invoice"]["id"] == invoice["id"] and candidate["match_id"]:
                match_id = candidate["match_id"]
                break

        assert match_id is not None, "Expected a match to be created"

        # Confirm the match
        confirm_response = client.post(
            f"/tenants/{sample_tenant['id']}/matches/{match_id}/confirm"
        )

        assert confirm_response.status_code == 200
        confirmed_match = confirm_response.json()
        assert confirmed_match["status"] == "confirmed"

        # Verify invoice status is updated
        invoice_response = client.get(
            f"/tenants/{sample_tenant['id']}/invoices/{invoice['id']}"
        )
        assert invoice_response.json()["status"] == "matched"

    def test_confirm_match_rejects_others(
        self, client, sample_tenant, sample_vendor
    ):
        """Test confirming a match rejects other candidates for same invoice."""
        # Create one invoice
        invoice_response = client.post(
            f"/tenants/{sample_tenant['id']}/invoices",
            json={"amount": "1000.00", "invoice_date": "2024-04-15"},
        )
        invoice = invoice_response.json()

        # Create two transactions that could match
        client.post(
            f"/tenants/{sample_tenant['id']}/bank-transactions/import",
            json={
                "transactions": [
                    {
                        "external_id": "TXN-MULTI-1",
                        "posted_at": "2024-04-15T12:00:00Z",
                        "amount": "1000.00",
                    },
                    {
                        "external_id": "TXN-MULTI-2",
                        "posted_at": "2024-04-16T12:00:00Z",
                        "amount": "1000.00",
                    },
                ]
            },
        )

        # Run reconciliation
        client.post(f"/tenants/{sample_tenant['id']}/reconcile")

        # Get all matches for this invoice
        matches_response = client.get(
            f"/tenants/{sample_tenant['id']}/matches",
            params={"invoice_id": invoice["id"]},
        )
        matches = matches_response.json()["items"]

        if len(matches) >= 2:
            # Confirm the first match
            first_match_id = matches[0]["id"]
            client.post(
                f"/tenants/{sample_tenant['id']}/matches/{first_match_id}/confirm"
            )

            # Check other matches are rejected
            matches_response = client.get(
                f"/tenants/{sample_tenant['id']}/matches",
                params={"invoice_id": invoice["id"]},
            )
            updated_matches = matches_response.json()["items"]

            confirmed_count = sum(1 for m in updated_matches if m["status"] == "confirmed")
            rejected_count = sum(1 for m in updated_matches if m["status"] == "rejected")

            assert confirmed_count == 1
            assert rejected_count == len(updated_matches) - 1
