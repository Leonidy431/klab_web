"""
API Version 1 Router.

Combines all API endpoints under /api/v1 prefix.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import blueos, forum, shop, webhooks

router = APIRouter()

# Include endpoint routers
router.include_router(blueos.router, prefix="/rov", tags=["ROV / BlueOS"])
router.include_router(shop.router, prefix="/shop", tags=["Shop"])
router.include_router(forum.router, prefix="/forum", tags=["Forum"])
router.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
