"""Tests for AI explanation endpoint."""

import pytest
from unittest.mock import patch, MagicMock


class TestAIExplanation:
    """Tests for AI explanation endpoint."""

    @pytest.mark.asyncio
    async def test_explanation_fallback_without_ai(
        self, client, sample_tenant, sample_vendor, sample_invoice, sample_bank_transactions
    ):
        """Test fallback explanation when AI is disabled."""
        # Get first transaction ID
        tx_response = await client.get(f"/tenants/{sample_tenant['id']}/bank-transactions")
        transactions = tx_response.json()["items"]
        transaction_id = transactions[0]["id"]

        # Request explanation (AI should be disabled in test env)
        response = await client.get(
            f"/tenants/{sample_tenant['id']}/reconcile/explain",
            params={
                "invoice_id": sample_invoice["id"],
                "transaction_id": transaction_id,
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["invoice_id"] == sample_invoice["id"]
        assert data["transaction_id"] == transaction_id
        assert len(data["explanation"]) > 0
        assert data["is_fallback"] is True
        assert data["confidence"] in ["HIGH", "MEDIUM", "LOW", None]

    @pytest.mark.asyncio
    async def test_explanation_contains_relevant_info(
        self, client, sample_tenant, sample_vendor, sample_invoice, sample_bank_transactions
    ):
        """Test that explanation contains relevant information."""
        # Get first transaction ID
        tx_response = await client.get(f"/tenants/{sample_tenant['id']}/bank-transactions")
        transactions = tx_response.json()["items"]
        transaction_id = transactions[0]["id"]

        response = await client.get(
            f"/tenants/{sample_tenant['id']}/reconcile/explain",
            params={
                "invoice_id": sample_invoice["id"],
                "transaction_id": transaction_id,
            },
        )

        assert response.status_code == 200
        data = response.json()
        explanation = data["explanation"].lower()

        # Explanation should mention amounts or dates or match quality
        assert any(
            keyword in explanation
            for keyword in ["amount", "date", "match", "close", "exact", "similar"]
        )

    @pytest.mark.asyncio
    async def test_explanation_invalid_invoice(self, client, sample_tenant, sample_bank_transactions):
        """Test explanation with invalid invoice ID."""
        tx_response = await client.get(f"/tenants/{sample_tenant['id']}/bank-transactions")
        transactions = tx_response.json()["items"]
        transaction_id = transactions[0]["id"]

        response = await client.get(
            f"/tenants/{sample_tenant['id']}/reconcile/explain",
            params={
                "invoice_id": "non-existent-invoice",
                "transaction_id": transaction_id,
            },
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_explanation_invalid_transaction(self, client, sample_tenant, sample_invoice):
        """Test explanation with invalid transaction ID."""
        response = await client.get(
            f"/tenants/{sample_tenant['id']}/reconcile/explain",
            params={
                "invoice_id": sample_invoice["id"],
                "transaction_id": "non-existent-transaction",
            },
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_explanation_tenant_isolation(
        self, client, sample_tenant, sample_invoice, sample_bank_transactions
    ):
        """Test that explanation respects tenant isolation."""
        # Create another tenant
        other_tenant_response = await client.post("/tenants", json={"name": "Other Tenant"})
        other_tenant = other_tenant_response.json()

        # Get transaction from first tenant
        tx_response = await client.get(f"/tenants/{sample_tenant['id']}/bank-transactions")
        transaction_id = tx_response.json()["items"][0]["id"]

        # Try to access from other tenant
        response = await client.get(
            f"/tenants/{other_tenant['id']}/reconcile/explain",
            params={
                "invoice_id": sample_invoice["id"],
                "transaction_id": transaction_id,
            },
        )

        # Should fail because resources belong to different tenant
        assert response.status_code == 404


class TestAIExplanationMocked:
    """Tests for AI explanation with mocked OpenAI client."""

    @pytest.mark.asyncio
    async def test_explanation_with_mocked_ai(
        self, client, sample_tenant, sample_vendor, sample_invoice, sample_bank_transactions
    ):
        """Test explanation with mocked AI response."""
        # Get first transaction ID
        tx_response = await client.get(f"/tenants/{sample_tenant['id']}/bank-transactions")
        transactions = tx_response.json()["items"]
        transaction_id = transactions[0]["id"]

        # Mock the OpenAI client
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content="EXPLANATION: This is a strong match. The amounts match exactly at $1000.00 and the dates are the same. CONFIDENCE: HIGH"
                )
            )
        ]

        with patch("app.services.ai_explanation.AIExplanationService._get_ai_client") as mock_client:
            mock_openai = MagicMock()
            mock_openai.chat.completions.create.return_value = mock_response
            mock_client.return_value = mock_openai

            response = await client.get(
                f"/tenants/{sample_tenant['id']}/reconcile/explain",
                params={
                    "invoice_id": sample_invoice["id"],
                    "transaction_id": transaction_id,
                },
            )

            assert response.status_code == 200
            data = response.json()

            # When mocked AI is used, is_fallback should be False
            assert data["is_fallback"] is False
            assert "strong match" in data["explanation"].lower()
            assert data["confidence"] == "HIGH"

    @pytest.mark.asyncio
    async def test_explanation_ai_error_fallback(
        self, client, sample_tenant, sample_vendor, sample_invoice, sample_bank_transactions
    ):
        """Test fallback when AI raises an error."""
        tx_response = await client.get(f"/tenants/{sample_tenant['id']}/bank-transactions")
        transactions = tx_response.json()["items"]
        transaction_id = transactions[0]["id"]

        with patch("app.services.ai_explanation.AIExplanationService._get_ai_client") as mock_client:
            mock_openai = MagicMock()
            mock_openai.chat.completions.create.side_effect = Exception("API Error")
            mock_client.return_value = mock_openai

            response = await client.get(
                f"/tenants/{sample_tenant['id']}/reconcile/explain",
                params={
                    "invoice_id": sample_invoice["id"],
                    "transaction_id": transaction_id,
                },
            )

            assert response.status_code == 200
            data = response.json()

            # Should fall back to deterministic explanation
            assert data["is_fallback"] is True
            assert len(data["explanation"]) > 0
