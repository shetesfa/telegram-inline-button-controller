"""Telegram chat and administrator permissions checker."""

from typing import Any, Dict, Optional, Tuple
from telegram import Bot
from telegram.error import BadRequest, Forbidden, TelegramError
from app.utils.logging import logger


async def check_bot_permissions(
    bot: Bot, chat_identifier: int | str
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Verify that the bot has access to the destination and sufficient permissions.
    Returns (has_sufficient_rights, chat_info, error_message).
    """
    try:
        chat = await bot.get_chat(chat_identifier)
    except Forbidden:
        return (
            False,
            None,
            "Access denied. The bot is not a member or was removed from this chat.",
        )
    except BadRequest as e:
        return (
            False,
            None,
            f"Could not find chat '{chat_identifier}'. Ensure the username/ID is correct and the bot has been added.",
        )
    except TelegramError as e:
        return False, None, f"Telegram API error: {e.message}"

    chat_type = chat.type  # "channel", "group", "supergroup"
    chat_info = {
        "id": chat.id,
        "title": chat.title or "Untitled",
        "username": f"@{chat.username}" if chat.username else None,
        "type": chat_type,
    }

    try:
        bot_member = await bot.get_chat_member(chat.id, bot.id)
    except TelegramError as e:
        return (
            False,
            chat_info,
            f"Could not retrieve bot member status in {chat.title}: {e.message}",
        )

    # Validate channel permissions
    if chat_type == "channel":
        if bot_member.status not in ("administrator", "creator"):
            return (
                False,
                chat_info,
                "The bot is NOT an administrator in this channel. Please promote the bot to Administrator.",
            )

        # Check can_edit_messages permission
        can_edit = getattr(bot_member, "can_edit_messages", None)
        can_post = getattr(bot_member, "can_post_messages", None)

        if can_edit is False and can_post is False:
            return (
                False,
                chat_info,
                "Insufficient rights: Bot requires 'Edit Messages of Others' (can_edit_messages) permission in this channel.",
            )

        return True, chat_info, None

    # Validate group / supergroup permissions
    if chat_type in ("group", "supergroup"):
        if bot_member.status == "kicked":
            return False, chat_info, "The bot was removed/banned from this group."

        is_admin = bot_member.status in ("administrator", "creator")
        chat_info["is_admin"] = is_admin
        return True, chat_info, None

    return False, chat_info, f"Unsupported chat type: {chat_type}"
