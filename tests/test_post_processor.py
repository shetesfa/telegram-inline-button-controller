"""Tests for Post Processor automation, duplicate prevention, albums, and error isolation."""

from unittest.mock import AsyncMock, MagicMock
import pytest
from telegram import Chat, Message, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from app.services.button_service import ButtonService
from app.services.destination_service import DestinationService
from app.services.post_service import PostService
from app.services.system_service import SystemService
from app.telegram.post_processor import handle_incoming_post


@pytest.mark.asyncio
async def test_post_processor_attaches_keyboard_to_new_post():
    """Verify incoming channel post receives configured inline keyboard."""
    # 1. Setup channel and buttons
    dest, _ = await DestinationService.add_destination(
        chat_id=-1007777777,
        title="Automated Channel",
        chat_type="channel",
        use_default_buttons=False,
    )
    await ButtonService.add_button(dest.id, "Join Group", "https://t.me/group", emoji="👥")
    await ButtonService.add_button(dest.id, "Contact Bot", "https://t.me/bot", emoji="🤖")

    # 2. Mock incoming channel post
    mock_bot = MagicMock()
    mock_bot.edit_message_reply_markup = AsyncMock()

    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = mock_bot

    msg = Message(
        message_id=101,
        date=None,
        chat=Chat(id=-1007777777, type="channel", title="Automated Channel"),
        text="📚 Test Educational Post Content",
    )
    update = Update(update_id=1, channel_post=msg)

    # 3. Process update
    await handle_incoming_post(update, context)

    # 4. Assert edit_message_reply_markup was called
    mock_bot.edit_message_reply_markup.assert_called_once()
    call_kwargs = mock_bot.edit_message_reply_markup.call_args.kwargs
    assert call_kwargs["chat_id"] == -1007777777
    assert call_kwargs["message_id"] == 101
    assert call_kwargs["reply_markup"] is not None
    assert len(call_kwargs["reply_markup"].inline_keyboard) == 2


@pytest.mark.asyncio
async def test_duplicate_post_protection():
    """Verify duplicate update for same message_id is ignored."""
    dest, _ = await DestinationService.add_destination(
        chat_id=-1008888888,
        title="Dup Check Channel",
        chat_type="channel",
        use_default_buttons=False,
    )
    await ButtonService.add_button(dest.id, "Test", "https://t.me/test")

    mock_bot = MagicMock()
    mock_bot.edit_message_reply_markup = AsyncMock()
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = mock_bot

    msg = Message(
        message_id=202,
        date=None,
        chat=Chat(id=-1008888888, type="channel"),
        text="Post content",
    )
    update = Update(update_id=2, channel_post=msg)

    # First call
    await handle_incoming_post(update, context)
    assert mock_bot.edit_message_reply_markup.call_count == 1

    # Duplicate call (same chat and msg)
    await handle_incoming_post(update, context)
    # Should still be 1, not called again
    assert mock_bot.edit_message_reply_markup.call_count == 1


@pytest.mark.asyncio
async def test_album_media_group_deduplication():
    """Verify only first item of a media group receives inline buttons."""
    dest, _ = await DestinationService.add_destination(
        chat_id=-1009999999,
        title="Album Channel",
        chat_type="channel",
        use_default_buttons=False,
    )
    await ButtonService.add_button(dest.id, "Test", "https://t.me/test")

    mock_bot = MagicMock()
    mock_bot.edit_message_reply_markup = AsyncMock()
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = mock_bot

    album_id = "album_unique_998877"

    # Message 1 of album
    msg1 = Message(
        message_id=301,
        date=None,
        chat=Chat(id=-1009999999, type="channel"),
        media_group_id=album_id,
        caption="Album Photo 1",
    )
    # Message 2 of album
    msg2 = Message(
        message_id=302,
        date=None,
        chat=Chat(id=-1009999999, type="channel"),
        media_group_id=album_id,
    )

    update1 = Update(update_id=3, channel_post=msg1)
    update2 = Update(update_id=4, channel_post=msg2)

    await handle_incoming_post(update1, context)
    await handle_incoming_post(update2, context)

    # Only msg1 should have been edited
    assert mock_bot.edit_message_reply_markup.call_count == 1
    call_kwargs = mock_bot.edit_message_reply_markup.call_args.kwargs
    assert call_kwargs["message_id"] == 301


@pytest.mark.asyncio
async def test_post_skipped_when_automation_disabled():
    """Verify posts are skipped when automation is disabled for destination."""
    dest, _ = await DestinationService.add_destination(
        chat_id=-1004444444,
        title="Disabled Auto Channel",
        chat_type="channel",
        use_default_buttons=False,
    )
    await ButtonService.add_button(dest.id, "Test", "https://t.me/test")
    await DestinationService.toggle_automation(dest.id)  # Pause automation

    mock_bot = MagicMock()
    mock_bot.edit_message_reply_markup = AsyncMock()
    context = MagicMock()
    context.bot = mock_bot

    msg = Message(
        message_id=401,
        date=None,
        chat=Chat(id=-1004444444, type="channel"),
        text="Hello",
    )
    update = Update(update_id=5, channel_post=msg)

    await handle_incoming_post(update, context)
    mock_bot.edit_message_reply_markup.assert_not_called()


@pytest.mark.asyncio
async def test_telegram_api_error_isolation():
    """Verify Telegram API failure on one post is handled gracefully and logged without crashing."""
    dest, _ = await DestinationService.add_destination(
        chat_id=-1003333333,
        title="Error Isolation Channel",
        chat_type="channel",
        use_default_buttons=False,
    )
    await ButtonService.add_button(dest.id, "Test", "https://t.me/test")

    mock_bot = MagicMock()
    mock_bot.edit_message_reply_markup = AsyncMock(
        side_effect=BadRequest("Message can't be edited")
    )
    context = MagicMock()
    context.bot = mock_bot

    msg = Message(
        message_id=501,
        date=None,
        chat=Chat(id=-1003333333, type="channel"),
        text="Hello",
    )
    update = Update(update_id=6, channel_post=msg)

    # Should execute without raising exception
    await handle_incoming_post(update, context)
    mock_bot.edit_message_reply_markup.assert_called_once()
