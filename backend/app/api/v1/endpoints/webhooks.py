"""
Webhook Endpoints.

Handles incoming webhooks from external services:
- Revolut Business (financial transactions)
- Stripe (payment confirmations)
"""

from fastapi import APIRouter, HTTPException, Request, Response
from loguru import logger

from app.modules.fintech.revolut import (
    RevolutWebhookHandler,
    get_revolut_handler,
)
from app.modules.fintech.telegram import (
    TelegramNotifier,
    get_telegram_notifier,
)

router = APIRouter()


@router.post("/revolut", status_code=200)
async def revolut_webhook(request: Request) -> Response:
    """
    Revolut Business Webhook Endpoint.

    Receives transaction events from Revolut and sends
    notifications via Telegram.

    Security:
    - Validates HMAC-SHA256 signature
    - Returns 401 on invalid signature
    - Returns 200 on success (to acknowledge receipt)

    Headers Required:
    - Revolut-Signature: v1=<signature>,t=<timestamp>
    """
    # Get raw body for signature verification
    body = await request.body()
    signature = request.headers.get("Revolut-Signature")

    # Get handlers
    revolut: RevolutWebhookHandler = get_revolut_handler()
    telegram: TelegramNotifier = get_telegram_notifier()

    # Verify signature (CRITICAL)
    if not revolut.verify_signature(body, signature):
        logger.warning(
            f"Invalid Revolut webhook signature from {request.client.host}"
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid signature",
        )

    # Parse event type
    event_type = revolut.get_event_type(body)
    logger.info(f"Received Revolut webhook: {event_type}")

    # Handle transaction events
    if event_type.startswith("Transaction"):
        transaction = revolut.parse_transaction(body)

        if transaction:
            # Send Telegram notification
            success = await telegram.send_transaction(transaction)

            if success:
                logger.info(
                    f"Sent notification for transaction {transaction.transaction_id}"
                )
            else:
                logger.warning(
                    f"Failed to send notification for {transaction.transaction_id}"
                )

    # Always return 200 to acknowledge receipt
    # (Revolut will retry if we return error)
    return Response(status_code=200)


@router.post("/stripe", status_code=200)
async def stripe_webhook(request: Request) -> Response:
    """
    Stripe Webhook Endpoint.

    Handles payment confirmations, refunds, and disputes.
    """
    from app.modules.shop.payment import PaymentService

    body = await request.body()
    signature = request.headers.get("Stripe-Signature")

    if not signature:
        raise HTTPException(status_code=401, detail="Missing signature")

    payment = PaymentService()
    event = await payment.verify_webhook(body, signature)

    if not event:
        raise HTTPException(status_code=401, detail="Invalid signature")

    event_type = event["type"]
    logger.info(f"Received Stripe webhook: {event_type}")

    # Handle specific events
    if event_type == "checkout.session.completed":
        # Payment successful
        session = event["data"]
        order_number = session.get("metadata", {}).get("order_number")
        logger.info(f"Payment completed for order {order_number}")

        # TODO: Update order status in database

    elif event_type == "payment_intent.payment_failed":
        # Payment failed
        intent = event["data"]
        logger.warning(f"Payment failed: {intent.get('id')}")

    return Response(status_code=200)


@router.get("/health")
async def webhook_health() -> dict:
    """Health check for webhook endpoints."""
    revolut = get_revolut_handler()
    telegram = get_telegram_notifier()

    return {
        "status": "healthy",
        "revolut_configured": bool(revolut.signing_secret),
        "telegram_configured": bool(telegram.bot_token and telegram.chat_id),
    }
