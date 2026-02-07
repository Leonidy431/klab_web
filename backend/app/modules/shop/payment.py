"""
Payment Service - Stripe integration.

Handles:
- Payment intents
- Checkout sessions
- Webhooks
- Refunds
"""

from decimal import Decimal
from typing import Any

import stripe
from loguru import logger

from app.core.config import settings


class PaymentService:
    """
    Stripe payment service.

    Usage:
        payment = PaymentService()
        session = await payment.create_checkout_session(order)
    """

    def __init__(self) -> None:
        """Initialize Stripe with API key."""
        stripe.api_key = settings.stripe_secret_key

    async def create_payment_intent(
        self,
        amount: Decimal,
        currency: str = "usd",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Create Stripe payment intent.

        Args:
            amount: Amount in dollars
            currency: Currency code
            metadata: Additional data to attach

        Returns:
            Payment intent details including client_secret
        """
        try:
            # Stripe expects amount in cents
            amount_cents = int(amount * 100)

            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency.lower(),
                metadata=metadata or {},
                automatic_payment_methods={"enabled": True},
            )

            return {
                "id": intent.id,
                "client_secret": intent.client_secret,
                "status": intent.status,
            }

        except stripe.StripeError as e:
            logger.error(f"Stripe error creating payment intent: {e}")
            raise

    async def create_checkout_session(
        self,
        order_number: str,
        items: list[dict[str, Any]],
        success_url: str,
        cancel_url: str,
        customer_email: str | None = None,
    ) -> dict[str, Any]:
        """
        Create Stripe Checkout session.

        Args:
            order_number: Order reference number
            items: List of line items [{name, price, quantity}]
            success_url: Redirect URL on success
            cancel_url: Redirect URL on cancel
            customer_email: Pre-fill customer email

        Returns:
            Checkout session with redirect URL
        """
        try:
            line_items = []
            for item in items:
                line_items.append(
                    {
                        "price_data": {
                            "currency": settings.shop_currency.lower(),
                            "product_data": {
                                "name": item["name"],
                                "description": item.get("description", ""),
                            },
                            "unit_amount": int(Decimal(str(item["price"])) * 100),
                        },
                        "quantity": item.get("quantity", 1),
                    }
                )

            session_params = {
                "payment_method_types": ["card"],
                "line_items": line_items,
                "mode": "payment",
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": {"order_number": order_number},
            }

            if customer_email:
                session_params["customer_email"] = customer_email

            session = stripe.checkout.Session.create(**session_params)

            return {
                "session_id": session.id,
                "url": session.url,
            }

        except stripe.StripeError as e:
            logger.error(f"Stripe error creating checkout session: {e}")
            raise

    async def verify_webhook(
        self,
        payload: bytes,
        signature: str,
    ) -> dict[str, Any] | None:
        """
        Verify Stripe webhook signature and return event.

        Args:
            payload: Raw request body
            signature: Stripe-Signature header

        Returns:
            Verified event data or None if invalid
        """
        try:
            event = stripe.Webhook.construct_event(
                payload,
                signature,
                settings.stripe_webhook_secret,
            )
            return {
                "type": event.type,
                "data": event.data.object,
            }

        except stripe.SignatureVerificationError:
            logger.warning("Invalid Stripe webhook signature")
            return None
        except Exception as e:
            logger.error(f"Stripe webhook error: {e}")
            return None

    async def create_refund(
        self,
        payment_intent_id: str,
        amount: Decimal | None = None,
        reason: str = "requested_by_customer",
    ) -> dict[str, Any]:
        """
        Create refund for payment.

        Args:
            payment_intent_id: Original payment intent ID
            amount: Partial refund amount (None for full refund)
            reason: Refund reason

        Returns:
            Refund details
        """
        try:
            refund_params = {
                "payment_intent": payment_intent_id,
                "reason": reason,
            }

            if amount:
                refund_params["amount"] = int(amount * 100)

            refund = stripe.Refund.create(**refund_params)

            return {
                "id": refund.id,
                "status": refund.status,
                "amount": refund.amount / 100,
            }

        except stripe.StripeError as e:
            logger.error(f"Stripe error creating refund: {e}")
            raise

    async def get_payment_status(self, payment_intent_id: str) -> dict[str, Any]:
        """Get payment intent status."""
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            return {
                "id": intent.id,
                "status": intent.status,
                "amount": intent.amount / 100,
                "currency": intent.currency,
            }
        except stripe.StripeError as e:
            logger.error(f"Stripe error retrieving payment: {e}")
            raise
