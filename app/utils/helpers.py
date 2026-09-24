"""Helper functions for formatting text, UI badges, and layout conversions."""

from datetime import datetime, timezone
from typing import Optional


def format_chat_type(chat_type: str) -> str:
    """Return user-friendly emoji and name for a Telegram chat type."""
    mapping = {
        "channel": "📢 Channel",
        "group": "👥 Group",
        "supergroup": "👥 Supergroup",
    }
    return mapping.get(chat_type.lower(), f"💬 {chat_type.capitalize()}")


def format_status_badge(is_active: bool) -> str:
    """Return status emoji badge."""
    return "🟢 Enabled" if is_active else "🔴 Disabled"


def format_datetime(dt: Optional[datetime]) -> str:
    """Format datetime object into readable string."""
    if not dt:
        return "Never"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def truncate_text(text: str, max_length: int = 30) -> str:
    """Truncate long text with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."
