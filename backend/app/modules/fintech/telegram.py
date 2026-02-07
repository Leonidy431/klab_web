"""
Telegram Notification Service.

Sends formatted transaction notifications via Telegram Bot API.
Integrates with Aiogram for async bot operations.

Features:
- Beautiful transaction formatting with emojis
- Income/Expense distinction
- Balance tracking
- Rate limiting
"""

import asyncio
from typing import Any

import httpx
from loguru import logger
from pydantic_settings import BaseSettings

from app.modules.fintech.revolut import ParsedTransaction


class TelegramSettings(BaseSettings):
    """Telegram bot configuration."""

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_notifications_enabled: bool = True

    class Config:
        env_file = ".env"


class TelegramNotifier:
    """
    Telegram notification service for financial transactions.

    Sends beautifully formatted messages about:
    - Incoming payments (🟢)
    - Outgoing payments (🔴)
    - Balance updates

    Usage:
        notifier = TelegramNotifier()
        await notifier.send_transaction(transaction)
    """

    # Message templates
    TRANSACTION_TEMPLATE = """
{emoji} <b>{title}</b>

{direction}: <b>{counterparty}</b>
{amount_label}: <code>{amount}</code>
{reference_line}
{balance_line}

📅 {timestamp}
    """.strip()

    INCOME_EMOJI = "🟢"
    EXPENSE_EMOJI = "🔴"
    MONEY_EMOJI = "💰"

    def __init__(
        self,
        bot_token: str | None = None,
        chat_id: str | None = None,
    ) -> None:
        """
        Initialize Telegram notifier.

        Args:
            bot_token: Telegram bot token (or from env)
            chat_id: Target chat ID (or from env)
        """
        settings = TelegramSettings()

        self.bot_token = bot_token or settings.telegram_bot_token
        self.chat_id = chat_id or settings.telegram_chat_id
        self.enabled = settings.telegram_notifications_enabled

        self.api_base = f"https://api.telegram.org/bot{self.bot_token}"

        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not configured")
        if not self.chat_id:
            logger.warning("TELEGRAM_CHAT_ID not configured")

    async def send_message(
        self,
        text: str,
        chat_id: str | None = None,
        parse_mode: str = "HTML",
        disable_notification: bool = False,
    ) -> dict[str, Any] | None:
        """
        Send message via Telegram Bot API.

        Args:
            text: Message text (supports HTML/Markdown)
            chat_id: Target chat ID (uses default if not specified)
            parse_mode: HTML or Markdown
            disable_notification: Send silently

        Returns:
            API response or None on error
        """
        if not self.enabled:
            logger.debug("Telegram notifications disabled")
            return None

        if not self.bot_token:
            logger.error("Cannot send: bot token not configured")
            return None

        target_chat = chat_id or self.chat_id
        if not target_chat:
            logger.error("Cannot send: chat_id not configured")
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base}/sendMessage",
                    json={
                        "chat_id": target_chat,
                        "text": text,
                        "parse_mode": parse_mode,
                        "disable_notification": disable_notification,
                    },
                    timeout=10.0,
                )
                response.raise_for_status()
                result = response.json()

                if not result.get("ok"):
                    logger.error(f"Telegram API error: {result}")
                    return None

                return result

        except httpx.HTTPStatusError as e:
            logger.error(f"Telegram HTTP error: {e.response.status_code}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Telegram request error: {e}")
            return None

    def format_transaction(self, transaction: ParsedTransaction) -> str:
        """
        Format transaction for Telegram message.

        Args:
            transaction: Parsed transaction data

        Returns:
            Formatted HTML message
        """
        # Choose emoji and labels based on direction
        if transaction.is_income:
            emoji = self.INCOME_EMOJI
            title = "Incoming Payment"
            direction = "From"
            amount_label = "Amount"
        else:
            emoji = self.EXPENSE_EMOJI
            title = "Outgoing Payment"
            direction = "To"
            amount_label = "Amount"

        # Format reference line if present
        reference_line = ""
        if transaction.reference:
            reference_line = f"📋 Ref: <code>{transaction.reference}</code>"
        elif transaction.description:
            reference_line = f"📋 {transaction.description}"

        # Format balance line if present
        balance_line = ""
        if transaction.formatted_balance:
            balance_line = f"💼 Balance: <code>{transaction.formatted_balance}</code>"

        # Format timestamp
        timestamp = transaction.created_at.strftime("%Y-%m-%d %H:%M UTC")

        return self.TRANSACTION_TEMPLATE.format(
            emoji=emoji,
            title=title,
            direction=direction,
            counterparty=transaction.counterparty_name,
            amount_label=amount_label,
            amount=transaction.formatted_amount,
            reference_line=reference_line,
            balance_line=balance_line,
            timestamp=timestamp,
        )

    async def send_transaction(
        self,
        transaction: ParsedTransaction,
        chat_id: str | None = None,
    ) -> bool:
        """
        Send transaction notification.

        Args:
            transaction: Parsed transaction
            chat_id: Target chat (uses default if not specified)

        Returns:
            True if sent successfully
        """
        message = self.format_transaction(transaction)
        result = await self.send_message(message, chat_id=chat_id)
        return result is not None

    async def send_balance_update(
        self,
        currency: str,
        balance: float,
        change: float | None = None,
        chat_id: str | None = None,
    ) -> bool:
        """
        Send balance update notification.

        Args:
            currency: Currency code
            balance: Current balance
            change: Change since last update
            chat_id: Target chat

        Returns:
            True if sent successfully
        """
        symbols = {
            "EUR": "€",
            "USD": "$",
            "GBP": "£",
            "RUB": "₽",
        }
        symbol = symbols.get(currency, currency)

        change_text = ""
        if change is not None:
            change_emoji = "📈" if change > 0 else "📉"
            sign = "+" if change > 0 else ""
            change_text = f"\n{change_emoji} Change: {sign}{symbol}{change:,.2f}"

        message = f"""
💼 <b>Balance Update</b>

{symbol}{balance:,.2f} {currency}{change_text}
        """.strip()

        result = await self.send_message(message, chat_id=chat_id)
        return result is not None

    async def send_alert(
        self,
        title: str,
        message: str,
        chat_id: str | None = None,
    ) -> bool:
        """
        Send alert notification.

        Args:
            title: Alert title
            message: Alert message
            chat_id: Target chat

        Returns:
            True if sent successfully
        """
        text = f"⚠️ <b>{title}</b>\n\n{message}"
        result = await self.send_message(text, chat_id=chat_id)
        return result is not None


# Singleton instance
_telegram_notifier: TelegramNotifier | None = None


def get_telegram_notifier() -> TelegramNotifier:
    """Get or create Telegram notifier singleton."""
    global _telegram_notifier
    if _telegram_notifier is None:
        _telegram_notifier = TelegramNotifier()
    return _telegram_notifier
