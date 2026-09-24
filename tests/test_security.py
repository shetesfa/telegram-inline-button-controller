"""Tests for Administrator security, access control, and unauthorized user rejection."""

from unittest.mock import AsyncMock, MagicMock
import pytest
from telegram import Chat, Message, Update, User
from app.bot.permissions import admin_filter, admin_required
from app.config import config


def test_is_admin_check():
    """Verify is_admin correctly matches whitelist."""
    assert config.is_admin(12345) is True
    assert config.is_admin(67890) is True
    assert config.is_admin(99999) is False
    assert config.is_admin(None) is False


def test_admin_filter():
    """Verify UpdateFilter allows authorized users and blocks unauthorized."""
    # Authorized user
    auth_user = User(id=12345, is_bot=False, first_name="Admin")
    auth_update = Update(update_id=1, message=Message(message_id=1, date=None, chat=Chat(id=12345, type="private"), from_user=auth_user))
    assert admin_filter.filter(auth_update) is True

    # Unauthorized user
    unauth_user = User(id=99999, is_bot=False, first_name="Stranger")
    unauth_update = Update(update_id=2, message=Message(message_id=2, date=None, chat=Chat(id=99999, type="private"), from_user=unauth_user))
    assert admin_filter.filter(unauth_update) is False


@pytest.mark.asyncio
async def test_admin_required_decorator_authorized():
    """Verify decorated handler executes when called by an admin."""
    mock_handler = AsyncMock(return_value="executed_successfully")
    decorated = admin_required(mock_handler)

    update = MagicMock(spec=Update)
    update.effective_user = User(id=12345, is_bot=False, first_name="Admin")
    update.callback_query = None
    mock_msg = MagicMock()
    mock_msg.reply_text = AsyncMock()
    update.effective_message = mock_msg
    context = MagicMock()

    result = await decorated(update, context)
    assert result == "executed_successfully"
    mock_handler.assert_called_once_with(update, context)


@pytest.mark.asyncio
async def test_admin_required_decorator_unauthorized():
    """Verify decorated handler halts and rejects unauthorized callers."""
    mock_handler = AsyncMock(return_value="executed_successfully")
    decorated = admin_required(mock_handler)

    update = MagicMock(spec=Update)
    update.effective_user = User(id=99999, is_bot=False, first_name="Intruder")
    update.callback_query = None
    mock_message = MagicMock()
    mock_message.reply_text = AsyncMock()
    update.effective_message = mock_message
    context = MagicMock()

    result = await decorated(update, context)
    assert result is None
    mock_handler.assert_not_called()
    mock_message.reply_text.assert_called_once()
    args, kwargs = mock_message.reply_text.call_args
    assert "Access Denied" in args[0]
