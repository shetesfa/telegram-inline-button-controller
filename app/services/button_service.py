"""Service layer for Button management, reordering, validation, and keyboard layout generation."""

from typing import List, Optional, Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from app.database.database import get_session
from app.database.models import Button
from app.database.repository import ButtonRepository
from app.utils.logging import logger
from app.utils.validation import validate_button_label, validate_url


class ButtonService:
    """Business logic for button configurations and keyboard construction."""

    @staticmethod
    async def list_for_destination(
        destination_id: int, active_only: bool = False
    ) -> List[Button]:
        """Fetch all buttons assigned to a specific destination."""
        async with get_session() as session:
            return await ButtonRepository.list_for_destination(
                session, destination_id, active_only=active_only
            )

    @staticmethod
    async def list_default_templates(active_only: bool = False) -> List[Button]:
        """Fetch global default template buttons."""
        async with get_session() as session:
            return await ButtonRepository.list_default_templates(
                session, active_only=active_only
            )

    @staticmethod
    async def get_button(button_id: int) -> Optional[Button]:
        """Fetch a single button by ID."""
        async with get_session() as session:
            return await ButtonRepository.get_by_id(session, button_id)

    @staticmethod
    async def add_button(
        destination_id: Optional[int],
        label: str,
        url: str,
        emoji: str = "",
        is_enabled: bool = True,
    ) -> Tuple[Optional[Button], Optional[str]]:
        """
        Validate and create a new button.
        Returns (button, error_message).
        """
        valid_label, err_label = validate_button_label(label)
        if not valid_label:
            return None, err_label

        valid_url, err_url = validate_url(url)
        if not valid_url:
            return None, err_url

        async with get_session() as session:
            button = await ButtonRepository.create(
                session=session,
                destination_id=destination_id,
                label=label.strip(),
                url=url.strip(),
                emoji=emoji.strip(),
                is_enabled=is_enabled,
            )
            logger.info(
                f"Created button: ID={button.id}, Label='{button.display_text}', Dest={destination_id}"
            )
            return button, None

    @staticmethod
    async def update_button(
        button_id: int,
        label: Optional[str] = None,
        url: Optional[str] = None,
        emoji: Optional[str] = None,
        is_enabled: Optional[bool] = None,
    ) -> Tuple[Optional[Button], Optional[str]]:
        """
        Validate and update an existing button.
        Returns (button, error_message).
        """
        kwargs = {}
        if label is not None:
            valid_label, err_label = validate_button_label(label)
            if not valid_label:
                return None, err_label
            kwargs["label"] = label.strip()

        if url is not None:
            valid_url, err_url = validate_url(url)
            if not valid_url:
                return None, err_url
            kwargs["url"] = url.strip()

        if emoji is not None:
            kwargs["emoji"] = emoji.strip()

        if is_enabled is not None:
            kwargs["is_enabled"] = is_enabled

        async with get_session() as session:
            button = await ButtonRepository.update(session, button_id, **kwargs)
            if not button:
                return None, "Button not found."
            logger.info(f"Updated button ID={button_id}: {kwargs}")
            return button, None

    @staticmethod
    async def toggle_button(button_id: int) -> Optional[bool]:
        """Toggle is_enabled state of a button."""
        async with get_session() as session:
            button = await ButtonRepository.get_by_id(session, button_id)
            if not button:
                return None
            button.is_enabled = not button.is_enabled
            await session.flush()
            logger.info(f"Toggled button ID={button_id} to {button.is_enabled}")
            return button.is_enabled

    @staticmethod
    async def delete_button(button_id: int) -> bool:
        """Delete a button."""
        async with get_session() as session:
            success = await ButtonRepository.delete(session, button_id)
            if success:
                logger.info(f"Deleted button ID={button_id}")
            return success

    @staticmethod
    async def move_button(button_id: int, direction: str) -> bool:
        """Move button 'up' or 'down' in ordering."""
        async with get_session() as session:
            button = await ButtonRepository.get_by_id(session, button_id)
            if not button:
                return False

            if button.destination_id is None:
                all_buttons = await ButtonRepository.list_default_templates(session)
            else:
                all_buttons = await ButtonRepository.list_for_destination(
                    session, button.destination_id
                )

            ids = [b.id for b in all_buttons]
            if button_id not in ids:
                return False

            current_idx = ids.index(button_id)
            if direction == "up" and current_idx > 0:
                ids[current_idx], ids[current_idx - 1] = (
                    ids[current_idx - 1],
                    ids[current_idx],
                )
            elif direction == "down" and current_idx < len(ids) - 1:
                ids[current_idx], ids[current_idx + 1] = (
                    ids[current_idx + 1],
                    ids[current_idx],
                )
            else:
                return False

            await ButtonRepository.reorder_buttons(session, ids)
            return True

    @staticmethod
    def build_inline_keyboard(
        buttons: List[Button], layout_mode: str = "vertical"
    ) -> Optional[InlineKeyboardMarkup]:
        """
        Build a Telegram InlineKeyboardMarkup from a list of Button objects.
        Supports layout modes:
        - 'vertical': 1 button per row
        - 'horizontal_2col': 2 buttons per row, with odd button on its own row
        - 'custom': respect row_index if configured, otherwise fallback to vertical
        """
        active_buttons = [b for b in buttons if b.is_enabled]
        if not active_buttons:
            return None

        keyboard_rows: List[List[InlineKeyboardButton]] = []

        if layout_mode == "horizontal_2col":
            current_row: List[InlineKeyboardButton] = []
            for btn in active_buttons:
                current_row.append(
                    InlineKeyboardButton(text=btn.display_text, url=btn.url)
                )
                if len(current_row) == 2:
                    keyboard_rows.append(current_row)
                    current_row = []
            if current_row:
                keyboard_rows.append(current_row)

        elif layout_mode == "custom":
            # Group by row_index
            rows_dict = {}
            for btn in active_buttons:
                r_idx = btn.row_index
                if r_idx not in rows_dict:
                    rows_dict[r_idx] = []
                rows_dict[r_idx].append(
                    InlineKeyboardButton(text=btn.display_text, url=btn.url)
                )
            for r_idx in sorted(rows_dict.keys()):
                keyboard_rows.append(rows_dict[r_idx])

        else:
            # Default: Vertical (1 button per row)
            for btn in active_buttons:
                keyboard_rows.append(
                    [InlineKeyboardButton(text=btn.display_text, url=btn.url)]
                )

        return InlineKeyboardMarkup(keyboard_rows)

    @staticmethod
    async def init_default_templates_if_empty() -> None:
        """Keep initial button templates clean (no dummy templates)."""
        pass
