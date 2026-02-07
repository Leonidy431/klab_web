"""
Cart Service - Shopping cart management with Redis.
"""

import json
from decimal import Decimal
from typing import Any

import redis.asyncio as redis
from loguru import logger

from app.core.config import settings


class CartService:
    """
    Shopping cart service using Redis for storage.

    Cart is stored per user/session with TTL for automatic expiration.

    Usage:
        cart = CartService()
        await cart.add_item(user_id, product_sku, quantity=2)
        items = await cart.get_items(user_id)
    """

    CART_TTL = 60 * 60 * 24 * 7  # 7 days

    def __init__(self) -> None:
        """Initialize Redis connection."""
        self._redis: redis.Redis | None = None

    async def connect(self) -> None:
        """Connect to Redis."""
        self._redis = redis.from_url(
            str(settings.redis_url),
            encoding="utf-8",
            decode_responses=True,
        )

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()

    def _cart_key(self, user_id: int | str) -> str:
        """Generate Redis key for user's cart."""
        return f"cart:{user_id}"

    async def get_items(self, user_id: int | str) -> list[dict[str, Any]]:
        """
        Get all items in user's cart.

        Returns:
            List of cart items with product info and quantities
        """
        if not self._redis:
            await self.connect()

        key = self._cart_key(user_id)
        cart_data = await self._redis.get(key)

        if not cart_data:
            return []

        try:
            return json.loads(cart_data)
        except json.JSONDecodeError:
            logger.warning(f"Invalid cart data for user {user_id}")
            return []

    async def _save_items(
        self,
        user_id: int | str,
        items: list[dict[str, Any]],
    ) -> None:
        """Save cart items to Redis."""
        key = self._cart_key(user_id)
        await self._redis.setex(
            key,
            self.CART_TTL,
            json.dumps(items),
        )

    async def add_item(
        self,
        user_id: int | str,
        product_sku: str,
        product_name: str,
        price: Decimal,
        quantity: int = 1,
        image_url: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Add item to cart or update quantity if exists.

        Args:
            user_id: User or session ID
            product_sku: Product SKU
            product_name: Product name for display
            price: Unit price
            quantity: Quantity to add
            image_url: Product image URL

        Returns:
            Updated cart items
        """
        items = await self.get_items(user_id)

        # Check if product already in cart
        for item in items:
            if item["sku"] == product_sku:
                item["quantity"] += quantity
                item["total"] = float(Decimal(str(item["price"])) * item["quantity"])
                await self._save_items(user_id, items)
                return items

        # Add new item
        new_item = {
            "sku": product_sku,
            "name": product_name,
            "price": float(price),
            "quantity": quantity,
            "total": float(price * quantity),
            "image_url": image_url,
        }
        items.append(new_item)
        await self._save_items(user_id, items)

        return items

    async def update_quantity(
        self,
        user_id: int | str,
        product_sku: str,
        quantity: int,
    ) -> list[dict[str, Any]]:
        """
        Update item quantity in cart.

        Args:
            user_id: User or session ID
            product_sku: Product SKU
            quantity: New quantity (0 to remove)

        Returns:
            Updated cart items
        """
        items = await self.get_items(user_id)

        if quantity <= 0:
            # Remove item
            items = [item for item in items if item["sku"] != product_sku]
        else:
            # Update quantity
            for item in items:
                if item["sku"] == product_sku:
                    item["quantity"] = quantity
                    item["total"] = float(Decimal(str(item["price"])) * quantity)
                    break

        await self._save_items(user_id, items)
        return items

    async def remove_item(
        self,
        user_id: int | str,
        product_sku: str,
    ) -> list[dict[str, Any]]:
        """Remove item from cart."""
        return await self.update_quantity(user_id, product_sku, 0)

    async def clear(self, user_id: int | str) -> None:
        """Clear all items from cart."""
        key = self._cart_key(user_id)
        await self._redis.delete(key)

    async def get_totals(self, user_id: int | str) -> dict[str, Any]:
        """
        Calculate cart totals.

        Returns:
            Totals including subtotal, item count, shipping estimate
        """
        items = await self.get_items(user_id)

        subtotal = Decimal("0")
        item_count = 0

        for item in items:
            subtotal += Decimal(str(item["total"]))
            item_count += item["quantity"]

        # Free shipping over $500
        shipping = Decimal("25.00") if subtotal < Decimal("500") else Decimal("0")
        total = subtotal + shipping

        return {
            "subtotal": float(subtotal),
            "shipping": float(shipping),
            "total": float(total),
            "item_count": item_count,
            "free_shipping_threshold": 500.00,
            "free_shipping_remaining": max(0, float(Decimal("500") - subtotal)),
        }


# Singleton instance
_cart_service: CartService | None = None


async def get_cart_service() -> CartService:
    """Get or create cart service singleton."""
    global _cart_service
    if _cart_service is None:
        _cart_service = CartService()
        await _cart_service.connect()
    return _cart_service
