"""Inline keyboard builder for post attachments and live preview rendering."""

from typing import List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from app.database.models import Button


def build_preview_keyboard(
    buttons: List[Button],
    layout_mode: str = "vertical",
    back_callback: str = "menu:home",
) -> InlineKeyboardMarkup:
    """
    Build preview inline keyboard including active buttons plus a back control button.
    """
    active_buttons = [b for b in buttons if b.is_enabled]
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
    else:
        for btn in active_buttons:
            keyboard_rows.append(
                [InlineKeyboardButton(text=btn.display_text, url=btn.url)]
            )

    # Add navigation row at the bottom of the preview
    keyboard_rows.append(
        [InlineKeyboardButton("⬅️ Back to Editor", callback_data=back_callback)]
    )

    return InlineKeyboardMarkup(keyboard_rows)
