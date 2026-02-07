"""
Shop Module - E-commerce functionality.

Features:
- Product catalog with categories
- Shopping cart
- Checkout with Stripe payments
- Order management
- Inventory tracking
"""

from app.modules.shop.service import ShopService
from app.modules.shop.cart import CartService
from app.modules.shop.payment import PaymentService

__all__ = [
    "ShopService",
    "CartService",
    "PaymentService",
]
