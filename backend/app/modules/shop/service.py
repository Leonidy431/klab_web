"""
Shop Service - Product and order management.
"""

from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.shop import (
    Category,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    ProductStatus,
)


class ShopService:
    """
    Service for managing products, categories, and orders.

    Usage:
        shop = ShopService(db_session)
        products = await shop.get_products(category_slug="rov-parts")
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize shop service with database session."""
        self.db = db

    # ==================== Categories ====================

    async def get_categories(self, include_inactive: bool = False) -> list[Category]:
        """Get all categories."""
        query = select(Category).order_by(Category.sort_order)
        if not include_inactive:
            query = query.where(Category.is_active == True)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_category(self, slug: str) -> Category | None:
        """Get category by slug."""
        query = select(Category).where(Category.slug == slug)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_category(
        self,
        name: str,
        slug: str,
        description: str | None = None,
        parent_id: int | None = None,
    ) -> Category:
        """Create new category."""
        category = Category(
            name=name,
            slug=slug,
            description=description,
            parent_id=parent_id,
        )
        self.db.add(category)
        await self.db.flush()
        return category

    # ==================== Products ====================

    async def get_products(
        self,
        category_slug: str | None = None,
        status: ProductStatus = ProductStatus.ACTIVE,
        featured_only: bool = False,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Product]:
        """
        Get products with filters.

        Args:
            category_slug: Filter by category
            status: Filter by status
            featured_only: Only featured products
            search: Search in name/description
            limit: Max results
            offset: Pagination offset

        Returns:
            List of products
        """
        query = (
            select(Product)
            .options(selectinload(Product.category))
            .where(Product.status == status)
        )

        if category_slug:
            query = query.join(Category).where(Category.slug == category_slug)

        if featured_only:
            query = query.where(Product.is_featured == True)

        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                Product.name.ilike(search_pattern)
                | Product.description.ilike(search_pattern)
            )

        query = query.order_by(Product.created_at.desc()).limit(limit).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_product(self, slug: str) -> Product | None:
        """Get product by slug."""
        query = (
            select(Product)
            .options(selectinload(Product.category), selectinload(Product.reviews))
            .where(Product.slug == slug)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_product_by_sku(self, sku: str) -> Product | None:
        """Get product by SKU."""
        query = select(Product).where(Product.sku == sku)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_product(
        self,
        name: str,
        slug: str,
        sku: str,
        price: Decimal,
        description: str | None = None,
        category_id: int | None = None,
        stock_quantity: int = 0,
    ) -> Product:
        """Create new product."""
        product = Product(
            name=name,
            slug=slug,
            sku=sku,
            price=price,
            description=description,
            category_id=category_id,
            stock_quantity=stock_quantity,
            status=ProductStatus.DRAFT,
        )
        self.db.add(product)
        await self.db.flush()
        return product

    async def update_stock(self, product_id: int, quantity_change: int) -> bool:
        """
        Update product stock quantity.

        Args:
            product_id: Product ID
            quantity_change: Amount to add (positive) or subtract (negative)

        Returns:
            True if successful
        """
        query = select(Product).where(Product.id == product_id)
        result = await self.db.execute(query)
        product = result.scalar_one_or_none()

        if not product:
            return False

        new_quantity = product.stock_quantity + quantity_change
        if new_quantity < 0:
            return False

        product.stock_quantity = new_quantity
        await self.db.flush()
        return True

    # ==================== Orders ====================

    async def get_orders(
        self,
        user_id: int | None = None,
        status: OrderStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Order]:
        """Get orders with filters."""
        query = select(Order).options(selectinload(Order.items))

        if user_id:
            query = query.where(Order.user_id == user_id)
        if status:
            query = query.where(Order.status == status)

        query = query.order_by(Order.created_at.desc()).limit(limit).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_order(self, order_number: str) -> Order | None:
        """Get order by order number."""
        query = (
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.order_number == order_number)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_order(
        self,
        user_id: int,
        items: list[dict[str, Any]],
        shipping_info: dict[str, Any],
        payment_method: str = "stripe",
    ) -> Order:
        """
        Create new order from cart items.

        Args:
            user_id: Customer user ID
            items: List of {product_id, quantity}
            shipping_info: Shipping address details
            payment_method: Payment method name

        Returns:
            Created order
        """
        # Generate order number
        order_number = f"KL-{uuid4().hex[:8].upper()}"

        # Calculate totals
        subtotal = Decimal("0")
        order_items = []

        for item in items:
            product = await self.get_product_by_sku(item.get("sku", ""))
            if not product:
                continue

            quantity = item.get("quantity", 1)
            item_total = product.price * quantity
            subtotal += item_total

            order_items.append(
                OrderItem(
                    product_id=product.id,
                    product_name=product.name,
                    product_sku=product.sku,
                    unit_price=product.price,
                    quantity=quantity,
                    total=item_total,
                )
            )

        # Calculate shipping (simplified)
        shipping_cost = Decimal("25.00") if subtotal < Decimal("500") else Decimal("0")
        total = subtotal + shipping_cost

        # Create order
        order = Order(
            order_number=order_number,
            user_id=user_id,
            status=OrderStatus.PENDING,
            subtotal=subtotal,
            shipping_cost=shipping_cost,
            total=total,
            payment_method=payment_method,
            shipping_name=shipping_info.get("name", ""),
            shipping_address=shipping_info.get("address", ""),
            shipping_city=shipping_info.get("city", ""),
            shipping_country=shipping_info.get("country", ""),
            shipping_postal_code=shipping_info.get("postal_code", ""),
            shipping_phone=shipping_info.get("phone"),
        )

        self.db.add(order)
        await self.db.flush()

        # Add items
        for item in order_items:
            item.order_id = order.id
            self.db.add(item)

        await self.db.flush()
        return order

    async def update_order_status(
        self,
        order_number: str,
        status: OrderStatus,
        tracking_number: str | None = None,
    ) -> Order | None:
        """Update order status."""
        order = await self.get_order(order_number)
        if not order:
            return None

        order.status = status
        if tracking_number:
            order.tracking_number = tracking_number

        await self.db.flush()
        return order
