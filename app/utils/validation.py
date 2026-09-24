"""Validation helpers for URLs, chat identifiers, and button labels."""

import re
from urllib.parse import urlparse
from typing import Tuple, Optional


URL_REGEX = re.compile(
    r"^(?:https?:\/\/|tg:\/\/)[^\s/$.?#].[^\s]*$",
    re.IGNORECASE,
)


def validate_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a button destination URL.
    Supports https://, http://, and tg:// deep links.
    Returns (is_valid, error_message).
    """
    cleaned = url.strip()
    if not cleaned:
        return False, "URL cannot be empty."

    if not (
        cleaned.startswith("http://")
        or cleaned.startswith("https://")
        or cleaned.startswith("tg://")
    ):
        return False, "URL must begin with https://, http://, or tg://"

    if not URL_REGEX.match(cleaned):
        return False, "URL format is invalid."

    try:
        parsed = urlparse(cleaned)
        if cleaned.startswith("http://") or cleaned.startswith("https://"):
            if not parsed.netloc or "." not in parsed.netloc:
                return False, "URL domain name is incomplete or invalid."
    except Exception:
        return False, "Could not parse URL structure."

    return True, None


def validate_button_label(label: str) -> Tuple[bool, Optional[str]]:
    """
    Validate button label text.
    Must not be empty, max 64 characters.
    """
    cleaned = label.strip()
    if not cleaned:
        return False, "Button label cannot be empty."
    if len(cleaned) > 64:
        return False, "Button label must be 64 characters or fewer."
    return True, None


def clean_chat_identifier(chat_input: str) -> Tuple[Optional[int], Optional[str]]:
    """
    Parse user input into either a numeric chat_id or a clean @username.
    Returns (chat_id, username).
    """
    cleaned = chat_input.strip()

    # If it's a numeric ID (like -100123456789 or 123456789)
    if cleaned.startswith("-") and cleaned[1:].isdigit():
        return int(cleaned), None
    if cleaned.isdigit():
        return int(cleaned), None

    # If it's a t.me link
    if "t.me/" in cleaned:
        match = re.search(r"t\.me\/([a-zA-Z0-9_]+)", cleaned)
        if match:
            username = match.group(1)
            return None, f"@{username}"

    # If it starts with @
    if cleaned.startswith("@"):
        return None, cleaned

    # Otherwise if it's alphanumeric with underscores
    if re.match(r"^[a-zA-Z0-9_]{5,32}$", cleaned):
        return None, f"@{cleaned}"

    return None, None
