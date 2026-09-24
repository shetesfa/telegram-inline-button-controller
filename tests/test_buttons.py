"""Tests for Button CRUD, validation, reordering, and keyboard generation."""

import pytest
from app.services.button_service import ButtonService
from app.services.destination_service import DestinationService


@pytest.mark.asyncio
async def test_add_and_get_button():
    """Verify adding and retrieving a button."""
    dest, _ = await DestinationService.add_destination(
        chat_id=-1001111111,
        title="Test Channel",
        chat_type="channel",
        use_default_buttons=False,
    )

    btn, err = await ButtonService.add_button(
        destination_id=dest.id,
        label="Official Website",
        url="https://example.com",
        emoji="🌐",
    )
    assert err is None
    assert btn is not None
    assert btn.label == "Official Website"
    assert btn.emoji == "🌐"
    assert btn.display_text == "🌐 Official Website"
    assert btn.url == "https://example.com"
    assert btn.is_enabled is True

    fetched = await ButtonService.get_button(btn.id)
    assert fetched is not None
    assert fetched.id == btn.id


@pytest.mark.asyncio
async def test_button_url_and_label_validation():
    """Verify invalid button URLs and labels are rejected."""
    # Invalid empty label
    btn, err = await ButtonService.add_button(
        destination_id=None,
        label="",
        url="https://example.com",
    )
    assert btn is None
    assert "empty" in err.lower()

    # Invalid URL scheme
    btn, err = await ButtonService.add_button(
        destination_id=None,
        label="Bad URL",
        url="ftp://invalid.url",
    )
    assert btn is None
    assert "https://" in err.lower() or "http://" in err.lower()


@pytest.mark.asyncio
async def test_toggle_and_update_button():
    """Verify updating and toggling button properties."""
    btn, _ = await ButtonService.add_button(
        destination_id=None,
        label="Initial",
        url="https://example.com",
    )

    # Update
    updated, err = await ButtonService.update_button(
        btn.id, label="Updated Label", url="https://updated.com", emoji="🔥"
    )
    assert err is None
    assert updated.label == "Updated Label"
    assert updated.display_text == "🔥 Updated Label"
    assert updated.url == "https://updated.com"

    # Toggle
    status = await ButtonService.toggle_button(btn.id)
    assert status is False
    status = await ButtonService.toggle_button(btn.id)
    assert status is True


@pytest.mark.asyncio
async def test_button_reordering():
    """Verify moving buttons up and down."""
    dest, _ = await DestinationService.add_destination(
        chat_id=-1002222222,
        title="Reorder Test",
        chat_type="channel",
        use_default_buttons=False,
    )

    b1, _ = await ButtonService.add_button(dest.id, "Button 1", "https://1.com")
    b2, _ = await ButtonService.add_button(dest.id, "Button 2", "https://2.com")
    b3, _ = await ButtonService.add_button(dest.id, "Button 3", "https://3.com")

    # Move b3 up
    moved = await ButtonService.move_button(b3.id, "up")
    assert moved is True

    buttons = await ButtonService.list_for_destination(dest.id)
    assert [b.id for b in buttons] == [b1.id, b3.id, b2.id]

    # Move b1 down
    moved = await ButtonService.move_button(b1.id, "down")
    assert moved is True

    buttons = await ButtonService.list_for_destination(dest.id)
    assert [b.id for b in buttons] == [b3.id, b1.id, b2.id]


@pytest.mark.asyncio
async def test_keyboard_layouts():
    """Verify InlineKeyboardMarkup construction for vertical and horizontal 2-col."""
    dest, _ = await DestinationService.add_destination(
        chat_id=-1003333333,
        title="Layout Test",
        chat_type="channel",
        use_default_buttons=False,
    )

    await ButtonService.add_button(dest.id, "Btn 1", "https://1.com", emoji="1️⃣")
    await ButtonService.add_button(dest.id, "Btn 2", "https://2.com", emoji="2️⃣")
    await ButtonService.add_button(dest.id, "Btn 3", "https://3.com", emoji="3️⃣")

    buttons = await ButtonService.list_for_destination(dest.id)

    # Vertical: 3 rows of 1 button each
    kb_vertical = ButtonService.build_inline_keyboard(buttons, layout_mode="vertical")
    assert len(kb_vertical.inline_keyboard) == 3
    assert len(kb_vertical.inline_keyboard[0]) == 1
    assert len(kb_vertical.inline_keyboard[1]) == 1
    assert len(kb_vertical.inline_keyboard[2]) == 1

    # Horizontal 2-col: row 1 has 2 buttons, row 2 has 1 button
    kb_horizontal = ButtonService.build_inline_keyboard(
        buttons, layout_mode="horizontal_2col"
    )
    assert len(kb_horizontal.inline_keyboard) == 2
    assert len(kb_horizontal.inline_keyboard[0]) == 2
    assert len(kb_horizontal.inline_keyboard[1]) == 1
