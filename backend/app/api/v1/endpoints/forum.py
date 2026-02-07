"""
Forum API Endpoints.

Community discussions and posts.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.forum.service import ForumService

router = APIRouter()


# ==================== Schemas ====================


class CreateTopicRequest(BaseModel):
    """Create new topic."""

    category_id: int
    title: str
    content: str


class CreatePostRequest(BaseModel):
    """Create new post/reply."""

    content: str
    parent_id: int | None = None


class UpdatePostRequest(BaseModel):
    """Update post content."""

    content: str


# ==================== Categories ====================


@router.get("/categories")
async def get_categories(
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get all forum categories."""
    forum = ForumService(db)
    categories = await forum.get_categories()

    return [
        {
            "id": cat.id,
            "name": cat.name,
            "slug": cat.slug,
            "description": cat.description,
            "icon": cat.icon,
            "color": cat.color,
            "topic_count": cat.topic_count,
            "post_count": cat.post_count,
        }
        for cat in categories
    ]


# ==================== Topics ====================


@router.get("/topics")
async def get_topics(
    category: str | None = Query(None, description="Category slug"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get topics with pagination."""
    forum = ForumService(db)
    topics = await forum.get_topics(
        category_slug=category,
        limit=limit,
        offset=offset,
    )

    return {
        "items": [
            {
                "id": t.id,
                "title": t.title,
                "slug": t.slug,
                "author": t.author.username if t.author else "Unknown",
                "category": t.category.name if t.category else None,
                "view_count": t.view_count,
                "reply_count": t.reply_count,
                "like_count": t.like_count,
                "is_pinned": t.is_pinned,
                "is_locked": t.is_locked,
                "created_at": t.created_at.isoformat(),
                "last_post_at": t.last_post_at.isoformat() if t.last_post_at else None,
            }
            for t in topics
        ],
        "limit": limit,
        "offset": offset,
    }


@router.get("/topics/{topic_id}")
async def get_topic(
    topic_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get topic details."""
    forum = ForumService(db)
    topic = await forum.get_topic(topic_id)

    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    # Increment view count
    await forum.increment_view_count(topic_id)

    return {
        "id": topic.id,
        "title": topic.title,
        "slug": topic.slug,
        "content": topic.content,
        "author": {
            "id": topic.author.id,
            "username": topic.author.username,
            "avatar_url": topic.author.avatar_url,
        } if topic.author else None,
        "category": {
            "id": topic.category.id,
            "name": topic.category.name,
            "slug": topic.category.slug,
        } if topic.category else None,
        "view_count": topic.view_count,
        "reply_count": topic.reply_count,
        "like_count": topic.like_count,
        "is_pinned": topic.is_pinned,
        "is_locked": topic.is_locked,
        "created_at": topic.created_at.isoformat(),
    }


@router.post("/topics")
async def create_topic(
    request: CreateTopicRequest,
    user_id: int = Query(..., description="Author user ID"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create new topic."""
    forum = ForumService(db)

    topic = await forum.create_topic(
        category_id=request.category_id,
        author_id=user_id,
        title=request.title,
        content=request.content,
    )

    return {
        "id": topic.id,
        "title": topic.title,
        "slug": topic.slug,
        "created_at": topic.created_at.isoformat(),
    }


# ==================== Posts ====================


@router.get("/topics/{topic_id}/posts")
async def get_posts(
    topic_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get posts in topic."""
    forum = ForumService(db)
    posts = await forum.get_posts(topic_id, limit=limit, offset=offset)

    return {
        "items": [
            {
                "id": p.id,
                "content": p.content,
                "author": {
                    "id": p.author.id,
                    "username": p.author.username,
                    "avatar_url": p.author.avatar_url,
                } if p.author else None,
                "parent_id": p.parent_id,
                "like_count": p.like_count,
                "is_edited": p.is_edited,
                "created_at": p.created_at.isoformat(),
                "updated_at": p.updated_at.isoformat() if p.is_edited else None,
            }
            for p in posts
        ],
        "limit": limit,
        "offset": offset,
    }


@router.post("/topics/{topic_id}/posts")
async def create_post(
    topic_id: int,
    request: CreatePostRequest,
    user_id: int = Query(..., description="Author user ID"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create new post/reply in topic."""
    forum = ForumService(db)

    # Check if topic exists and not locked
    topic = await forum.get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    if topic.is_locked:
        raise HTTPException(status_code=403, detail="Topic is locked")

    post = await forum.create_post(
        topic_id=topic_id,
        author_id=user_id,
        content=request.content,
        parent_id=request.parent_id,
    )

    return {
        "id": post.id,
        "content": post.content,
        "created_at": post.created_at.isoformat(),
    }


@router.put("/posts/{post_id}")
async def update_post(
    post_id: int,
    request: UpdatePostRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update post content."""
    forum = ForumService(db)
    post = await forum.update_post(post_id, request.content)

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    return {
        "id": post.id,
        "content": post.content,
        "is_edited": post.is_edited,
        "updated_at": post.updated_at.isoformat(),
    }


# ==================== Reactions ====================


@router.post("/topics/{topic_id}/like")
async def like_topic(
    topic_id: int,
    user_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Like a topic."""
    forum = ForumService(db)
    added = await forum.add_reaction(user_id, topic_id=topic_id)

    return {"liked": added}


@router.delete("/topics/{topic_id}/like")
async def unlike_topic(
    topic_id: int,
    user_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Remove like from topic."""
    forum = ForumService(db)
    removed = await forum.remove_reaction(user_id, topic_id=topic_id)

    return {"unliked": removed}


@router.post("/posts/{post_id}/like")
async def like_post(
    post_id: int,
    user_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Like a post."""
    forum = ForumService(db)
    added = await forum.add_reaction(user_id, post_id=post_id)

    return {"liked": added}


@router.delete("/posts/{post_id}/like")
async def unlike_post(
    post_id: int,
    user_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Remove like from post."""
    forum = ForumService(db)
    removed = await forum.remove_reaction(user_id, post_id=post_id)

    return {"unliked": removed}
