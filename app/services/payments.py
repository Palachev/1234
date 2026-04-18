from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from yookassa import Payment


class PaymentService:
    """Service layer for invoice lifecycle and payment gateway orchestration."""

    async def create_invoice(self, telegram_id: int, tariff_code: str, amount_minor: int):
        raise NotImplementedError

    async def create_yookassa_payment(
        self,
        invoice_id: str,
        amount_minor: int,
        description: str,
    ) -> str:
        """Create external YooKassa payment and return confirmation URL.

        amount_minor is expected in kopecks and converted to RUB value.
        """
        amount_rub = (Decimal(amount_minor) / Decimal("100")).quantize(Decimal("0.01"))

        payment = Payment.create(
            {
                "amount": {
                    "value": str(amount_rub),
                    "currency": "RUB",
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": "https://example.com/return",
                },
                "capture": True,
                "description": description,
                "metadata": {
                    "invoice_id": invoice_id,
                },
            },
            uuid4().hex,
        )

        return payment.confirmation.confirmation_url
