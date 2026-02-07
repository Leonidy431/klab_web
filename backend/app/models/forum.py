"""
Forum models for community discussions.

Includes:
- Categories (sections)
- Topics (threads)
- Posts (replies)
- Reactions
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class ForumCategory(Base):
    """Forum category/section."""

    __tablename__ = "forum_categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(String(50))  # Icon class name
    color: Mapped[str | None] = mapped_column(String(20))  # Hex color
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Moderation
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)

    # Stats (denormalized for performance)
    topic_count: Mapped[int] = mapped_column(Integer, default=0)
    post_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    topics: Mapped[list["ForumTopic"]] = relationship(back_populates="category")

    def __repr__(self) -> str:
        return f"<ForumCategory {self.name}>"


class ForumTopic(Base):
    """Forum topic/thread."""

    __tablename__ = "forum_topics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("forum_categories.id"))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    title: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), index=True)
    content: Mapped[str] = mapped_column(Text)  # First post content

    # Status
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=True)

    # Stats
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    reply_count: Mapped[int] = mapped_column(Integer, default=0)
    like_count: Mapped[int] = mapped_column(Integer, default=0)

    # Last activity
    last_post_id: Mapped[int | None] = mapped_column(Integer)
    last_post_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_post_by: Mapped[str | None] = mapped_column(String(100))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    category: Mapped["ForumCategory"] = relationship(back_populates="topics")
    author: Mapped["User"] = relationship(back_populates="forum_topics")
    posts: Mapped[list["ForumPost"]] = relationship(back_populates="topic")

    def __repr__(self) -> str:
        return f"<ForumTopic {self.title[:30]}>"


class ForumPost(Base):
    """Forum post/reply."""

    __tablename__ = "forum_posts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("forum_topics.id"))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("forum_posts.id"))

    content: Mapped[str] = mapped_column(Text)
    content_html: Mapped[str | None] = mapped_column(Text)  # Rendered markdown

    # Status
    is_approved: Mapped[bool] = mapped_column(Boolean, default=True)
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False)

    # Stats
    like_count: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    topic: Mapped["ForumTopic"] = relationship(back_populates="posts")
    author: Mapped["User"] = relationship(back_populates="forum_posts")
    parent: Mapped["ForumPost | None"] = relationship(
        "ForumPost", remote_side=[id], back_populates="replies"
    )
    replies: Mapped[list["ForumPost"]] = relationship(
        "ForumPost", back_populates="parent"
    )

    def __repr__(self) -> str:
        return f"<ForumPost {self.id} in topic {self.topic_id}>"


class ForumReaction(Base):
    """Reaction/like on topic or post."""

    __tablename__ = "forum_reactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    # Can react to topic or post (one must be null)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("forum_topics.id"))
    post_id: Mapped[int | None] = mapped_column(ForeignKey("forum_posts.id"))

    reaction_type: Mapped[str] = mapped_column(String(20), default="like")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
