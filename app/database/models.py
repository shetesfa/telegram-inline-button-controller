"""SQLAlchemy ORM models for the Telegram Post Manager system."""

from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Destination(Base):
    """
    Represents a Telegram channel, group, or supergroup configured for automation.
    """

    __tablename__ = "destinations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_chat_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    chat_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="channel"
    )  # channel, group, supergroup
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    automation_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    layout_mode: Mapped[str] = mapped_column(
        String(50), default="vertical", nullable=False
    )  # vertical, horizontal_2col, custom
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    buttons: Mapped[List["Button"]] = relationship(
        "Button",
        back_populates="destination",
        cascade="all, delete-orphan",
        order_by="Button.sort_order",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Destination id={self.id} chat_id={self.telegram_chat_id} title='{self.title}' type={self.chat_type}>"


class Button(Base):
    """
    Represents an inline keyboard button attached to a destination (or global default template).
    """

    __tablename__ = "buttons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    destination_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("destinations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    emoji: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    row_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    destination: Mapped[Optional["Destination"]] = relationship(
        "Destination", back_populates="buttons"
    )

    @property
    def display_text(self) -> str:
        """Return formatted button label with emoji if present."""
        if self.emoji:
            return f"{self.emoji} {self.label}".strip()
        return self.label

    def __repr__(self) -> str:
        return f"<Button id={self.id} dest_id={self.destination_id} text='{self.display_text}' order={self.sort_order}>"


class ProcessedPost(Base):
    """
    Minimal operational record for technical duplicate protection.
    Not a user-facing message history.
    """

    __tablename__ = "processed_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    destination_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    message_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    media_group_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, index=True
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50), default="SUCCESS", nullable=False
    )  # SUCCESS, SKIPPED, FAILED

    __table_args__ = (
        UniqueConstraint(
            "destination_id", "message_id", name="uq_processed_dest_msg"
        ),
    )

    def __repr__(self) -> str:
        return f"<ProcessedPost dest={self.destination_id} msg={self.message_id} status={self.status}>"


class SystemSetting(Base):
    """Key-value pair store for global runtime settings."""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String(1024), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<SystemSetting {self.key}={self.value}>"
