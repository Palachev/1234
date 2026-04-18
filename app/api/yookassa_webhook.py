from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.repositories.payment_repository import PaymentRepository
from app.services.subscription import SubscriptionService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/yookassa/webhook", status_code=status.HTTP_200_OK)
async def yookassa_webhook(
    request: Request,
    payment_repo: PaymentRepository,
    subscription_service: SubscriptionService,
) -> dict[str, str]:
    payload = await request.json()

    event = payload.get("event")
    if event != "payment.succeeded":
        return {"status": "ignored"}

    invoice_id = (
        payload.get("object", {})
        .get("metadata", {})
        .get("invoice_id")
    )
    if not invoice_id:
        logger.error("YooKassa webhook without invoice_id in metadata")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invoice_id is required in metadata",
        )

    invoice = await payment_repo.get_invoice(invoice_id)
    if not invoice:
        logger.error("Payment succeeded for unknown invoice_id=%s", invoice_id)
        return {"status": "unknown_invoice"}

    if invoice.status in {"paid", "completed", "paid_pending", "failed"}:
        logger.info("Duplicate webhook ignored: invoice_id=%s status=%s", invoice_id, invoice.status)
        return {"status": "duplicate"}

    await payment_repo.mark_paid(invoice_id)
    try:
        await subscription_service.process_payment_success(invoice_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Provisioning failed after webhook payment success: %s", invoice_id)
        await payment_repo.mark_paid_pending(invoice_id, str(exc))
        return {"status": "paid_pending"}

    return {"status": "ok"}
