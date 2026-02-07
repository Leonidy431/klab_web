"""
Shop API Endpoints.

E-commerce functionality for ROV parts and equipment.
"""

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.shop import OrderStatus, ProductStatus
from app.modules.shop.cart import CartService, get_cart_service
from app.modules.shop.payment import PaymentService
from app.modules.shop.service import ShopService

router = APIRouter()


# ==================== Schemas ====================


class AddToCartRequest(BaseModel):
    """Add item to cart."""

    product_sku: str
    product_name: str
    price: Decimal
    quantity: int = 1
    image_url: str | None = None


class UpdateCartRequest(BaseModel):
    """Update cart item quantity."""

    product_sku: str
    quantity: int


class CreateOrderRequest(BaseModel):
    """Create new order."""

    shipping_name: str
    shipping_address: str
    shipping_city: str
    shipping_country: str
    shipping_postal_code: str
    shipping_phone: str | None = None


class CheckoutRequest(BaseModel):
    """Initiate checkout."""

    success_url: str
    cancel_url: str


# ==================== Categories ====================


@router.get("/categories")
async def get_categories(
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get all product categories."""
    shop = ShopService(db)
    categories = await shop.get_categories()

    return [
        {
            "id": cat.id,
            "name": cat.name,
            "slug": cat.slug,
            "description": cat.description,
            "image_url": cat.image_url,
        }
        for cat in categories
    ]


@router.get("/categories/{slug}")
async def get_category(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get category by slug."""
    shop = ShopService(db)
    category = await shop.get_category(slug)

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    return {
        "id": category.id,
        "name": category.name,
        "slug": category.slug,
        "description": category.description,
    }


# ==================== Products ====================


@router.get("/products")
async def get_products(
    category: str | None = Query(None, description="Filter by category slug"),
    featured: bool = Query(False, description="Only featured products"),
    search: str | None = Query(None, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Get products with filtering and pagination.

    Returns list of products with total count.
    """
    shop = ShopService(db)
    products = await shop.get_products(
        category_slug=category,
        featured_only=featured,
        search=search,
        limit=limit,
        offset=offset,
    )

    return {
        "items": [
            {
                "id": p.id,
                "sku": p.sku,
                "name": p.name,
                "slug": p.slug,
                "short_description": p.short_description,
                "price": float(p.price),
                "compare_at_price": float(p.compare_at_price) if p.compare_at_price else None,
                "image_url": p.image_url,
                "in_stock": p.is_in_stock,
                "is_featured": p.is_featured,
                "category": p.category.name if p.category else None,
            }
            for p in products
        ],
        "limit": limit,
        "offset": offset,
    }


@router.get("/products/{slug}")
async def get_product(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get product details by slug."""
    shop = ShopService(db)
    product = await shop.get_product(slug)

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    return {
        "id": product.id,
        "sku": product.sku,
        "name": product.name,
        "slug": product.slug,
        "description": product.description,
        "short_description": product.short_description,
        "price": float(product.price),
        "compare_at_price": float(product.compare_at_price) if product.compare_at_price else None,
        "image_url": product.image_url,
        "gallery_urls": product.gallery_urls,
        "in_stock": product.is_in_stock,
        "stock_quantity": product.stock_quantity if product.track_inventory else None,
        "weight_kg": float(product.weight_kg) if product.weight_kg else None,
        "dimensions": product.dimensions,
        "category": {
            "name": product.category.name,
            "slug": product.category.slug,
        } if product.category else None,
        "reviews": [
            {
                "rating": r.rating,
                "title": r.title,
                "content": r.content,
            }
            for r in product.reviews
            if r.is_approved
        ],
    }


# ==================== Cart ====================


@router.get("/cart")
async def get_cart(
    user_id: int = Query(..., description="User or session ID"),
    cart: CartService = Depends(get_cart_service),
) -> dict[str, Any]:
    """Get user's shopping cart."""
    items = await cart.get_items(user_id)
    totals = await cart.get_totals(user_id)

    return {
        "items": items,
        "totals": totals,
    }


@router.post("/cart/add")
async def add_to_cart(
    user_id: int,
    request: AddToCartRequest,
    cart: CartService = Depends(get_cart_service),
) -> dict[str, Any]:
    """Add item to cart."""
    items = await cart.add_item(
        user_id=user_id,
        product_sku=request.product_sku,
        product_name=request.product_name,
        price=request.price,
        quantity=request.quantity,
        image_url=request.image_url,
    )
    totals = await cart.get_totals(user_id)

    return {"items": items, "totals": totals}


@router.put("/cart/update")
async def update_cart(
    user_id: int,
    request: UpdateCartRequest,
    cart: CartService = Depends(get_cart_service),
) -> dict[str, Any]:
    """Update item quantity in cart."""
    items = await cart.update_quantity(
        user_id=user_id,
        product_sku=request.product_sku,
        quantity=request.quantity,
    )
    totals = await cart.get_totals(user_id)

    return {"items": items, "totals": totals}


@router.delete("/cart/{product_sku}")
async def remove_from_cart(
    product_sku: str,
    user_id: int = Query(...),
    cart: CartService = Depends(get_cart_service),
) -> dict[str, Any]:
    """Remove item from cart."""
    items = await cart.remove_item(user_id, product_sku)
    totals = await cart.get_totals(user_id)

    return {"items": items, "totals": totals}


@router.delete("/cart")
async def clear_cart(
    user_id: int = Query(...),
    cart: CartService = Depends(get_cart_service),
) -> dict[str, str]:
    """Clear entire cart."""
    await cart.clear(user_id)
    return {"status": "cleared"}


# ==================== Checkout ====================


@router.post("/checkout")
async def create_checkout(
    user_id: int,
    request: CheckoutRequest,
    cart: CartService = Depends(get_cart_service),
) -> dict[str, Any]:
    """
    Create Stripe checkout session.

    Returns URL to redirect user for payment.
    """
    items = await cart.get_items(user_id)

    if not items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    payment = PaymentService()
    session = await payment.create_checkout_session(
        order_number=f"CART-{user_id}",
        items=items,
        success_url=request.success_url,
        cancel_url=request.cancel_url,
    )

    return session


# ==================== Orders ====================


@router.get("/orders")
async def get_orders(
    user_id: int = Query(...),
    status: OrderStatus | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get user's orders."""
    shop = ShopService(db)
    orders = await shop.get_orders(
        user_id=user_id,
        status=status,
        limit=limit,
        offset=offset,
    )

    return {
        "items": [
            {
                "order_number": o.order_number,
                "status": o.status.value,
                "total": float(o.total),
                "created_at": o.created_at.isoformat(),
                "items_count": len(o.items),
            }
            for o in orders
        ]
    }


@router.get("/orders/{order_number}")
async def get_order(
    order_number: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get order details."""
    shop = ShopService(db)
    order = await shop.get_order(order_number)

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return {
        "order_number": order.order_number,
        "status": order.status.value,
        "subtotal": float(order.subtotal),
        "shipping_cost": float(order.shipping_cost),
        "total": float(order.total),
        "shipping": {
            "name": order.shipping_name,
            "address": order.shipping_address,
            "city": order.shipping_city,
            "country": order.shipping_country,
            "postal_code": order.shipping_postal_code,
        },
        "tracking_number": order.tracking_number,
        "items": [
            {
                "sku": item.product_sku,
                "name": item.product_name,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price),
                "total": float(item.total),
            }
            for item in order.items
        ],
        "created_at": order.created_at.isoformat(),
    }
