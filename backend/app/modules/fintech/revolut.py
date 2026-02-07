"""
Revolut Business Webhook Handler.

Handles incoming webhooks from Revolut Business API with:
- Signature verification (HMAC-SHA256)
- Transaction parsing
- Event routing

Revolut Webhook Documentation:
https://developer.revolut.com/docs/business/webhooks

Security Note:
All webhooks MUST be verified using the Revolut-Signature header
before processing. Never trust unverified payloads.
"""

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class RevolutSettings(BaseSettings):
    """Revolut webhook configuration."""

    revolut_signing_secret: str = ""
    revolut_webhook_enabled: bool = True

    class Config:
        env_file = ".env"


class TransactionType(str, Enum):
    """Revolut transaction types."""

    CARD_PAYMENT = "card_payment"
    CARD_REFUND = "card_refund"
    TRANSFER = "transfer"
    EXCHANGE = "exchange"
    ATM = "atm"
    FEE = "fee"
    TOPUP = "topup"
    REWARD = "reward"


class TransactionState(str, Enum):
    """Transaction states."""

    PENDING = "pending"
    COMPLETED = "completed"
    DECLINED = "declined"
    FAILED = "failed"
    REVERTED = "reverted"


@dataclass
class ParsedTransaction:
    """Parsed transaction data for notifications."""

    transaction_id: str
    type: TransactionType
    state: TransactionState
    amount: Decimal
    currency: str
    counterparty_name: str
    counterparty_account: str | None
    description: str | None
    reference: str | None
    balance_after: Decimal | None
    created_at: datetime
    completed_at: datetime | None
    is_income: bool

    @property
    def formatted_amount(self) -> str:
        """Format amount with sign and currency symbol."""
        symbols = {
            "EUR": "€",
            "USD": "$",
            "GBP": "£",
            "RUB": "₽",
            "UAH": "₴",
            "PLN": "zł",
        }
        symbol = symbols.get(self.currency, self.currency)
        sign = "+" if self.is_income else "-"
        return f"{sign}{symbol}{abs(self.amount):,.2f}"

    @property
    def formatted_balance(self) -> str | None:
        """Format balance with currency symbol."""
        if self.balance_after is None:
            return None
        symbols = {
            "EUR": "€",
            "USD": "$",
            "GBP": "£",
            "RUB": "₽",
            "UAH": "₴",
            "PLN": "zł",
        }
        symbol = symbols.get(self.currency, self.currency)
        return f"{symbol}{self.balance_after:,.2f}"


class RevolutWebhookPayload(BaseModel):
    """Revolut webhook payload structure."""

    event: str
    timestamp: str
    data: dict[str, Any]


class RevolutWebhookHandler:
    """
    Handler for Revolut Business webhooks.

    Implements:
    - HMAC-SHA256 signature verification
    - Payload parsing and validation
    - Transaction event routing

    Usage:
        handler = RevolutWebhookHandler()

        # In FastAPI endpoint
        @app.post("/webhook/revolut")
        async def revolut_webhook(request: Request):
            body = await request.body()
            signature = request.headers.get("Revolut-Signature")

            if not handler.verify_signature(body, signature):
                raise HTTPException(401, "Invalid signature")

            transaction = handler.parse_transaction(body)
            await notify_telegram(transaction)
    """

    def __init__(self, signing_secret: str | None = None) -> None:
        """
        Initialize webhook handler.

        Args:
            signing_secret: Revolut webhook signing secret.
                           If not provided, loaded from environment.
        """
        settings = RevolutSettings()
        self.signing_secret = signing_secret or settings.revolut_signing_secret
        self.enabled = settings.revolut_webhook_enabled

        if not self.signing_secret:
            logger.warning(
                "REVOLUT_SIGNING_SECRET not configured. "
                "Webhook signature verification will fail!"
            )

    def verify_signature(
        self,
        payload: bytes,
        signature_header: str | None,
    ) -> bool:
        """
        Verify webhook signature using HMAC-SHA256.

        Revolut signs webhooks using:
        HMAC-SHA256(signing_secret, timestamp + "." + payload)

        The signature header format is:
        v1=<signature>,t=<timestamp>

        Args:
            payload: Raw request body bytes
            signature_header: Revolut-Signature header value

        Returns:
            True if signature is valid, False otherwise
        """
        if not signature_header:
            logger.warning("Missing Revolut-Signature header")
            return False

        if not self.signing_secret:
            logger.error("Signing secret not configured")
            return False

        try:
            # Parse signature header
            # Format: v1=<signature>,t=<timestamp>
            parts = {}
            for part in signature_header.split(","):
                key, value = part.split("=", 1)
                parts[key] = value

            signature = parts.get("v1")
            timestamp = parts.get("t")

            if not signature or not timestamp:
                logger.warning("Invalid signature header format")
                return False

            # Compute expected signature
            # Revolut uses: HMAC-SHA256(secret, timestamp.payload)
            signed_payload = f"{timestamp}.".encode() + payload
            expected_signature = hmac.new(
                self.signing_secret.encode(),
                signed_payload,
                hashlib.sha256,
            ).hexdigest()

            # Constant-time comparison to prevent timing attacks
            is_valid = hmac.compare_digest(signature, expected_signature)

            if not is_valid:
                logger.warning("Webhook signature verification failed")

            return is_valid

        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False

    def parse_webhook(self, payload: bytes) -> RevolutWebhookPayload:
        """
        Parse webhook payload into structured object.

        Args:
            payload: Raw JSON payload bytes

        Returns:
            Parsed webhook payload

        Raises:
            ValueError: If payload is invalid JSON
        """
        try:
            data = json.loads(payload)
            return RevolutWebhookPayload(**data)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON payload: {e}")
            raise ValueError("Invalid JSON payload") from e

    def parse_transaction(
        self,
        payload: bytes | dict[str, Any],
    ) -> ParsedTransaction | None:
        """
        Parse transaction data from webhook payload.

        Args:
            payload: Raw bytes or parsed dict

        Returns:
            ParsedTransaction or None if not a transaction event
        """
        if isinstance(payload, bytes):
            data = json.loads(payload)
        else:
            data = payload

        # Handle nested webhook structure
        if "data" in data:
            transaction_data = data["data"]
        else:
            transaction_data = data

        # Check if this is a transaction event
        event_type = data.get("event", "")
        if not event_type.startswith("Transaction"):
            logger.debug(f"Not a transaction event: {event_type}")
            return None

        try:
            # Extract transaction details
            legs = transaction_data.get("legs", [{}])
            leg = legs[0] if legs else {}

            amount = Decimal(str(leg.get("amount", 0)))
            is_income = amount > 0

            # Get counterparty info
            counterparty = leg.get("counterparty", {})
            counterparty_name = counterparty.get("name", "Unknown")
            counterparty_account = counterparty.get("account_id")

            # Parse timestamps
            created_at = datetime.fromisoformat(
                transaction_data.get("created_at", "").replace("Z", "+00:00")
            )
            completed_at = None
            if completed_str := transaction_data.get("completed_at"):
                completed_at = datetime.fromisoformat(
                    completed_str.replace("Z", "+00:00")
                )

            # Get balance after transaction
            balance_after = None
            if balance := leg.get("balance_after"):
                balance_after = Decimal(str(balance))

            return ParsedTransaction(
                transaction_id=transaction_data.get("id", ""),
                type=TransactionType(
                    transaction_data.get("type", "transfer").lower()
                ),
                state=TransactionState(
                    transaction_data.get("state", "completed").lower()
                ),
                amount=abs(amount),
                currency=leg.get("currency", "EUR"),
                counterparty_name=counterparty_name,
                counterparty_account=counterparty_account,
                description=leg.get("description"),
                reference=transaction_data.get("reference"),
                balance_after=balance_after,
                created_at=created_at,
                completed_at=completed_at,
                is_income=is_income,
            )

        except Exception as e:
            logger.error(f"Failed to parse transaction: {e}")
            return None

    def get_event_type(self, payload: bytes) -> str:
        """Extract event type from webhook payload."""
        try:
            data = json.loads(payload)
            return data.get("event", "unknown")
        except json.JSONDecodeError:
            return "unknown"


# Singleton instance
_revolut_handler: RevolutWebhookHandler | None = None


def get_revolut_handler() -> RevolutWebhookHandler:
    """Get or create Revolut webhook handler singleton."""
    global _revolut_handler
    if _revolut_handler is None:
        _revolut_handler = RevolutWebhookHandler()
    return _revolut_handler
