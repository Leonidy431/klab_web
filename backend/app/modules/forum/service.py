"""
Forum Service - Topic and post management.
"""

from datetime import datetime
from typing import Any

from slugify import slugify
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.forum import ForumCategory, ForumPost, ForumReaction, ForumTopic


class ForumService:
    """
    Service for managing forum categories, topics, and posts.

    Usage:
        forum = ForumService(db_session)
        topics = await forum.get_topics(category_slug="rov-discussion")
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize forum service with database session."""
        self.db = db

    # ==================== Categories ====================

    async def get_categories(self) -> list[ForumCategory]:
        """Get all active categories."""
        query = (
            select(ForumCategory)
            .where(ForumCategory.is_active == True)
            .order_by(ForumCategory.sort_order)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_category(self, slug: str) -> ForumCategory | None:
        """Get category by slug."""
        query = select(ForumCategory).where(ForumCategory.slug == slug)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_category(
        self,
        name: str,
        slug: str,
        description: str | None = None,
        icon: str | None = None,
        color: str | None = None,
    ) -> ForumCategory:
        """Create new forum category."""
        category = ForumCategory(
            name=name,
            slug=slug,
            description=description,
            icon=icon,
            color=color,
        )
        self.db.add(category)
        await self.db.flush()
        return category

    # ==================== Topics ====================

    async def get_topics(
        self,
        category_slug: str | None = None,
        pinned_first: bool = True,
        limit: int = 20,
        offset: int = 0,
    ) -> list[ForumTopic]:
        """
        Get topics with pagination.

        Args:
            category_slug: Filter by category
            pinned_first: Show pinned topics first
            limit: Max results
            offset: Pagination offset

        Returns:
            List of topics
        """
        query = (
            select(ForumTopic)
            .options(selectinload(ForumTopic.author), selectinload(ForumTopic.category))
            .where(ForumTopic.is_approved == True)
        )

        if category_slug:
            query = query.join(ForumCategory).where(ForumCategory.slug == category_slug)

        if pinned_first:
            query = query.order_by(
                ForumTopic.is_pinned.desc(),
                ForumTopic.last_post_at.desc().nullsfirst(),
                ForumTopic.created_at.desc(),
            )
        else:
            query = query.order_by(ForumTopic.created_at.desc())

        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_topic(self, topic_id: int) -> ForumTopic | None:
        """Get topic by ID with author info."""
        query = (
            select(ForumTopic)
            .options(
                selectinload(ForumTopic.author),
                selectinload(ForumTopic.category),
            )
            .where(ForumTopic.id == topic_id)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_topic_by_slug(
        self,
        category_slug: str,
        topic_slug: str,
    ) -> ForumTopic | None:
        """Get topic by category and topic slugs."""
        query = (
            select(ForumTopic)
            .options(
                selectinload(ForumTopic.author),
                selectinload(ForumTopic.category),
            )
            .join(ForumCategory)
            .where(
                ForumCategory.slug == category_slug,
                ForumTopic.slug == topic_slug,
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_topic(
        self,
        category_id: int,
        author_id: int,
        title: str,
        content: str,
    ) -> ForumTopic:
        """
        Create new forum topic.

        Args:
            category_id: Category ID
            author_id: Author user ID
            title: Topic title
            content: First post content

        Returns:
            Created topic
        """
        # Generate slug
        base_slug = slugify(title)[:200]
        slug = base_slug

        # Ensure unique slug
        counter = 1
        while True:
            existing = await self.db.execute(
                select(ForumTopic).where(ForumTopic.slug == slug)
            )
            if not existing.scalar_one_or_none():
                break
            slug = f"{base_slug}-{counter}"
            counter += 1

        topic = ForumTopic(
            category_id=category_id,
            author_id=author_id,
            title=title,
            slug=slug,
            content=content,
            last_post_at=datetime.utcnow(),
        )

        self.db.add(topic)
        await self.db.flush()

        # Update category stats
        await self.db.execute(
            update(ForumCategory)
            .where(ForumCategory.id == category_id)
            .values(topic_count=ForumCategory.topic_count + 1)
        )

        return topic

    async def increment_view_count(self, topic_id: int) -> None:
        """Increment topic view count."""
        await self.db.execute(
            update(ForumTopic)
            .where(ForumTopic.id == topic_id)
            .values(view_count=ForumTopic.view_count + 1)
        )

    # ==================== Posts ====================

    async def get_posts(
        self,
        topic_id: int,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[ForumPost]:
        """
        Get posts in topic.

        Args:
            topic_id: Topic ID
            limit: Max results (None for all)
            offset: Pagination offset

        Returns:
            List of posts
        """
        limit = limit or settings.forum_posts_per_page

        query = (
            select(ForumPost)
            .options(selectinload(ForumPost.author))
            .where(
                ForumPost.topic_id == topic_id,
                ForumPost.is_approved == True,
            )
            .order_by(ForumPost.created_at)
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create_post(
        self,
        topic_id: int,
        author_id: int,
        content: str,
        parent_id: int | None = None,
    ) -> ForumPost:
        """
        Create new post in topic.

        Args:
            topic_id: Topic ID
            author_id: Author user ID
            content: Post content (markdown)
            parent_id: Parent post ID for replies

        Returns:
            Created post
        """
        post = ForumPost(
            topic_id=topic_id,
            author_id=author_id,
            content=content,
            parent_id=parent_id,
        )

        self.db.add(post)
        await self.db.flush()

        # Update topic stats
        now = datetime.utcnow()
        await self.db.execute(
            update(ForumTopic)
            .where(ForumTopic.id == topic_id)
            .values(
                reply_count=ForumTopic.reply_count + 1,
                last_post_id=post.id,
                last_post_at=now,
            )
        )

        # Update category stats
        topic = await self.get_topic(topic_id)
        if topic:
            await self.db.execute(
                update(ForumCategory)
                .where(ForumCategory.id == topic.category_id)
                .values(post_count=ForumCategory.post_count + 1)
            )

        return post

    async def update_post(
        self,
        post_id: int,
        content: str,
    ) -> ForumPost | None:
        """Update post content."""
        query = select(ForumPost).where(ForumPost.id == post_id)
        result = await self.db.execute(query)
        post = result.scalar_one_or_none()

        if not post:
            return None

        post.content = content
        post.is_edited = True
        post.updated_at = datetime.utcnow()

        await self.db.flush()
        return post

    # ==================== Reactions ====================

    async def add_reaction(
        self,
        user_id: int,
        topic_id: int | None = None,
        post_id: int | None = None,
        reaction_type: str = "like",
    ) -> bool:
        """
        Add reaction to topic or post.

        Args:
            user_id: User ID
            topic_id: Topic ID (mutually exclusive with post_id)
            post_id: Post ID (mutually exclusive with topic_id)
            reaction_type: Reaction type (like, heart, etc.)

        Returns:
            True if reaction was added (False if already exists)
        """
        # Check existing reaction
        query = select(ForumReaction).where(ForumReaction.user_id == user_id)

        if topic_id:
            query = query.where(ForumReaction.topic_id == topic_id)
        elif post_id:
            query = query.where(ForumReaction.post_id == post_id)
        else:
            return False

        result = await self.db.execute(query)
        if result.scalar_one_or_none():
            return False  # Already reacted

        reaction = ForumReaction(
            user_id=user_id,
            topic_id=topic_id,
            post_id=post_id,
            reaction_type=reaction_type,
        )
        self.db.add(reaction)

        # Update like count
        if topic_id:
            await self.db.execute(
                update(ForumTopic)
                .where(ForumTopic.id == topic_id)
                .values(like_count=ForumTopic.like_count + 1)
            )
        elif post_id:
            await self.db.execute(
                update(ForumPost)
                .where(ForumPost.id == post_id)
                .values(like_count=ForumPost.like_count + 1)
            )

        await self.db.flush()
        return True

    async def remove_reaction(
        self,
        user_id: int,
        topic_id: int | None = None,
        post_id: int | None = None,
    ) -> bool:
        """Remove user's reaction from topic or post."""
        query = select(ForumReaction).where(ForumReaction.user_id == user_id)

        if topic_id:
            query = query.where(ForumReaction.topic_id == topic_id)
        elif post_id:
            query = query.where(ForumReaction.post_id == post_id)
        else:
            return False

        result = await self.db.execute(query)
        reaction = result.scalar_one_or_none()

        if not reaction:
            return False

        await self.db.delete(reaction)

        # Update like count
        if topic_id:
            await self.db.execute(
                update(ForumTopic)
                .where(ForumTopic.id == topic_id)
                .values(like_count=ForumTopic.like_count - 1)
            )
        elif post_id:
            await self.db.execute(
                update(ForumPost)
                .where(ForumPost.id == post_id)
                .values(like_count=ForumPost.like_count - 1)
            )

        await self.db.flush()
        return True
