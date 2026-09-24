"""Tests for Destination (Channels and Groups) management and configuration."""

import pytest
from app.services.button_service import ButtonService
from app.services.destination_service import DestinationService


@pytest.mark.asyncio
async def test_add_channel_with_default_templates():
    """Verify adding a channel with default templates seeded."""
    # Seed default templates first
    await ButtonService.init_default_templates_if_empty()

    dest, created = await DestinationService.add_destination(
        chat_id=-1001234567890,
        title="Primary News",
        chat_type="channel",
        username="@primarynews",
        use_default_buttons=True,
    )
    assert created is True
    assert dest.title == "Primary News"
    assert dest.chat_type == "channel"
    assert dest.is_enabled is True
    assert dest.automation_enabled is True

    # Buttons should have been copied from default templates
    buttons = await ButtonService.list_for_destination(dest.id)
    assert len(buttons) == 3


@pytest.mark.asyncio
async def test_add_group_start_empty():
    """Verify adding a group starting with empty buttons."""
    dest, created = await DestinationService.add_destination(
        chat_id=-1009876543210,
        title="Community Group",
        chat_type="supergroup",
        username=None,
        use_default_buttons=False,
    )
    assert created is True
    assert dest.title == "Community Group"
    assert dest.chat_type == "supergroup"

    buttons = await ButtonService.list_for_destination(dest.id)
    assert len(buttons) == 0


@pytest.mark.asyncio
async def test_toggle_destination_states():
    """Verify toggling enabled and automation states."""
    dest, _ = await DestinationService.add_destination(
        chat_id=-1005555555,
        title="Toggle Test",
        chat_type="channel",
        use_default_buttons=False,
    )

    # Toggle enabled
    res = await DestinationService.toggle_enabled(dest.id)
    assert res is False
    res = await DestinationService.toggle_enabled(dest.id)
    assert res is True

    # Toggle automation
    res = await DestinationService.toggle_automation(dest.id)
    assert res is False
    res = await DestinationService.toggle_automation(dest.id)
    assert res is True


@pytest.mark.asyncio
async def test_delete_destination_cascades_buttons():
    """Verify deleting a destination removes its associated buttons."""
    dest, _ = await DestinationService.add_destination(
        chat_id=-1006666666,
        title="Delete Test",
        chat_type="channel",
        use_default_buttons=False,
    )
    btn, _ = await ButtonService.add_button(dest.id, "Test", "https://t.me")

    success = await DestinationService.delete_destination(dest.id)
    assert success is True

    # Destination should not exist
    assert await DestinationService.get_destination(dest.id) is None

    # Button should have been cascaded
    assert await ButtonService.get_button(btn.id) is None
