"""
AI Explanation Service.

This module provides AI-powered explanations for match decisions using OpenAI.
It includes graceful fallback to deterministic explanations when AI is unavailable.
Supports mock client for testing without real API calls.
"""

import asyncio
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AIServiceError, NotFoundError
from app.models.bank_transaction import BankTransaction
from app.models.invoice import Invoice
from app.schemas.explanation import ExplanationResponse
from app.services.invoice import InvoiceService
from app.services.bank_transaction import BankTransactionService
from app.services.reconciliation import ReconciliationEngine


@dataclass
class MockMessage:
    """Mock message for AI response."""
    content: str


@dataclass
class MockChoice:
    """Mock choice for AI response."""
    message: MockMessage


@dataclass
class MockCompletion:
    """Mock completion response."""
    choices: list[MockChoice]


class MockAIClient:
    """
    Mock AI client for testing without real API calls.
    
    Generates realistic-looking AI explanations based on the input context.
    """

    class chat:
        class completions:
            @staticmethod
            def create(model: str, messages: list, **kwargs) -> MockCompletion:
                """Generate a mock AI response based on the prompt context."""
                user_message = messages[-1]["content"] if messages else ""
                
                # Extract score from context
                score_match = re.search(r"Overall Score: ([\d.]+)%", user_message)
                score = float(score_match.group(1)) / 100 if score_match else 0.5
                
                # Extract amounts
                invoice_amount = re.search(r"Invoice.*?Amount: ([\d.]+)", user_message)
                txn_amount = re.search(r"Bank Transaction.*?Amount: ([\d.]+)", user_message, re.DOTALL)
                
                # Generate contextual explanation
                if score >= 0.8:
                    confidence = "HIGH"
                    explanation = (
                        "This is a strong match. The invoice and bank transaction show excellent alignment "
                        "across key reconciliation factors. The amounts match precisely, the timing is appropriate, "
                        "and there are clear textual references linking the transaction to this invoice. "
                        "I recommend confirming this match with high confidence."
                    )
                elif score >= 0.6:
                    confidence = "MEDIUM"
                    explanation = (
                        "This appears to be a reasonable match with some minor discrepancies. "
                        "The core financial data aligns well, though the textual correlation could be stronger. "
                        "The date proximity and amount matching suggest this transaction likely corresponds to this invoice. "
                        "Manual review is recommended before confirmation."
                    )
                else:
                    confidence = "LOW"
                    explanation = (
                        "This match has significant uncertainty. While some factors align, "
                        "there are notable discrepancies in the data that warrant careful review. "
                        "The match score indicates potential but not conclusive correspondence. "
                        "Additional verification is strongly recommended before accepting this match."
                    )
                
                response_text = f"EXPLANATION: {explanation}\nCONFIDENCE: {confidence}"
                
                return MockCompletion(
                    choices=[MockChoice(message=MockMessage(content=response_text))]
                )


class AIExplanationService:
    """
    Service for generating AI-powered explanations of match decisions.

    Features:
    - Uses OpenAI GPT models for natural language explanations
    - Falls back to deterministic explanations on AI failure
    - Only sends tenant-authorized data to AI
    - Configurable timeouts and error handling
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.invoice_service = InvoiceService(db)
        self.transaction_service = BankTransactionService(db)
        self.reconciliation_engine = ReconciliationEngine(db)

    def _get_ai_client(self):
        """Get AI client - either mock or real OpenAI."""
        if not self.settings.ai_enabled:
            return None

        # Use mock client for testing
        if self.settings.use_mock_ai:
            return MockAIClient()

        # Use real OpenAI client
        if not self.settings.openai_api_key:
            return None

        try:
            from openai import OpenAI
            return OpenAI(
                api_key=self.settings.openai_api_key,
                timeout=self.settings.ai_timeout_seconds,
            )
        except Exception:
            return None

    def _prepare_context(
        self,
        invoice: Invoice,
        transaction: BankTransaction,
        score_details: dict[str, Any],
    ) -> str:
        """Prepare context for AI prompt with only tenant-authorized data."""
        vendor_name = invoice.vendor.name if invoice.vendor else "Unknown"

        return f"""
Invoice Details:
- Amount: {invoice.amount} {invoice.currency}
- Date: {invoice.invoice_date or 'Not specified'}
- Invoice Number: {invoice.invoice_number or 'Not specified'}
- Vendor: {vendor_name}
- Description: {invoice.description or 'None'}

Bank Transaction Details:
- Amount: {transaction.amount} {transaction.currency}
- Posted Date: {transaction.posted_at.date()}
- Description/Memo: {transaction.description or 'None'}

Match Score Analysis:
- Overall Score: {score_details['final_score']:.2%}
- Amount Match Score: {score_details['breakdown']['amount']['score']:.2%}
- Date Proximity Score: {score_details['breakdown']['date']['score']:.2%}
- Text Similarity Score: {score_details['breakdown']['text']['score']:.2%}
- Currency Match Score: {score_details['breakdown']['currency']['score']:.2%}
"""

    def _generate_ai_explanation(
        self,
        context: str,
    ) -> tuple[str, str | None]:
        """
        Generate explanation using AI.

        Returns:
            Tuple of (explanation, confidence_label)
        """
        client = self._get_ai_client()
        if not client:
            raise AIServiceError("AI client not available")

        prompt = f"""You are a financial reconciliation assistant. Analyze the following invoice and bank transaction data to explain why they may or may not be a good match.

{context}

Provide a clear, concise explanation (2-6 sentences) that:
1. Identifies the key factors supporting or contradicting the match
2. Highlights any discrepancies or concerns
3. Gives an overall assessment

Also provide a confidence label: HIGH, MEDIUM, or LOW.

Format your response as:
EXPLANATION: [Your explanation here]
CONFIDENCE: [HIGH/MEDIUM/LOW]
"""

        try:
            response = client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a financial reconciliation expert. Provide clear, professional explanations for invoice-transaction matching decisions.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=300,
                temperature=0.3,
            )

            result = response.choices[0].message.content or ""

            # Parse response
            explanation = result
            confidence = None

            if "EXPLANATION:" in result and "CONFIDENCE:" in result:
                parts = result.split("CONFIDENCE:")
                explanation = parts[0].replace("EXPLANATION:", "").strip()
                confidence = parts[1].strip().upper()
                if confidence not in ["HIGH", "MEDIUM", "LOW"]:
                    confidence = None

            return explanation, confidence

        except Exception as e:
            raise AIServiceError(f"AI request failed: {str(e)}")

    def _generate_fallback_explanation(
        self,
        invoice: Invoice,
        transaction: BankTransaction,
        score_details: dict[str, Any],
    ) -> tuple[str, str | None]:
        """
        Generate a deterministic fallback explanation when AI is unavailable.

        Returns:
            Tuple of (explanation, confidence_label)
        """
        final_score = score_details['final_score']
        breakdown = score_details['breakdown']

        explanations = []

        # Amount analysis
        amount_score = breakdown['amount']['score']
        if amount_score == 1.0:
            explanations.append(
                f"The amounts match exactly ({invoice.amount} {invoice.currency})."
            )
        elif amount_score >= 0.8:
            explanations.append(
                f"The amounts are very close (Invoice: {invoice.amount}, Transaction: {transaction.amount})."
            )
        else:
            explanations.append(
                f"The amounts differ significantly (Invoice: {invoice.amount}, Transaction: {transaction.amount})."
            )

        # Date analysis
        date_score = breakdown['date']['score']
        if date_score >= 0.9:
            explanations.append("The dates are very close or matching.")
        elif date_score >= 0.7:
            explanations.append("The dates are within acceptable range.")
        elif date_score > 0:
            explanations.append("The dates are somewhat distant but within a week.")
        else:
            explanations.append("The dates are significantly different.")

        # Text similarity
        text_score = breakdown['text']['score']
        if text_score >= 0.7:
            explanations.append("There is strong textual similarity between the descriptions.")
        elif text_score >= 0.3:
            explanations.append("There is some textual overlap between the descriptions.")
        elif text_score > 0:
            explanations.append("Limited textual similarity was found.")

        # Currency
        if breakdown['currency']['score'] == 0:
            explanations.append("Note: The currencies do not match.")

        # Overall assessment
        if final_score >= 0.8:
            assessment = "This appears to be a strong match."
            confidence = "HIGH"
        elif final_score >= 0.6:
            assessment = "This is a likely match, but manual verification is recommended."
            confidence = "MEDIUM"
        elif final_score >= 0.5:
            assessment = "This is a possible match with some concerns."
            confidence = "LOW"
        else:
            assessment = "This match has significant concerns and may not be correct."
            confidence = "LOW"

        explanations.append(assessment)

        return " ".join(explanations), confidence

    def explain_match(
        self,
        tenant_id: str,
        invoice_id: str,
        transaction_id: str,
    ) -> ExplanationResponse:
        """
        Generate an explanation for a potential or actual match.

        Args:
            tenant_id: The tenant ID
            invoice_id: The invoice ID
            transaction_id: The bank transaction ID

        Returns:
            ExplanationResponse with natural language explanation
        """
        # Get entities with tenant isolation
        invoice = self.invoice_service.get_by_id(tenant_id, invoice_id)
        transaction = self.transaction_service.get_by_id(tenant_id, transaction_id)

        # Get score details
        score_details = self.reconciliation_engine.get_score_explanation(
            invoice, transaction
        )

        # Try AI explanation first
        is_fallback = False
        try:
            context = self._prepare_context(invoice, transaction, score_details)
            explanation, confidence = self._generate_ai_explanation(context)
        except AIServiceError:
            # Fall back to deterministic explanation
            explanation, confidence = self._generate_fallback_explanation(
                invoice, transaction, score_details
            )
            is_fallback = True

        return ExplanationResponse(
            invoice_id=invoice_id,
            transaction_id=transaction_id,
            explanation=explanation,
            confidence=confidence,
            is_fallback=is_fallback,
        )
