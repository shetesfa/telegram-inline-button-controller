"""Inline keyboard generators for Controller Bot menus and navigation."""

from typing import List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from app.config import config
from app.database.models import Button, Destination
from app.utils.helpers import truncate_text


def main_menu_kb(global_automation_on: bool) -> InlineKeyboardMarkup:
    """Generate the main controller dashboard keyboard."""
    auto_text = "🟢 Automation: ON" if global_automation_on else "🔴 Automation: OFF"
    keyboard = []

    # If WEBAPP_URL is configured or running on Render, add prominent Mini App button
    if config.WEBAPP_URL:
        target_url = f"{config.WEBAPP_URL.rstrip('/')}/webapp"
        keyboard.append(
            [InlineKeyboardButton("🌐 Open Web Dashboard 🚀", web_app=WebAppInfo(url=target_url))]
        )

    keyboard.extend([
        [
            InlineKeyboardButton("📢 Channels", callback_data="menu:channels"),
            InlineKeyboardButton("👥 Groups", callback_data="menu:groups"),
        ],
        [
            InlineKeyboardButton("🔘 Default Buttons", callback_data="menu:default_buttons"),
            InlineKeyboardButton("⚙️ Settings", callback_data="menu:settings"),
        ],
        [
            InlineKeyboardButton(auto_text, callback_data="toggle:global_auto"),
        ],
        [
            InlineKeyboardButton("🛠 System Status", callback_data="menu:status"),
        ],
    ])
    return InlineKeyboardMarkup(keyboard)


def destinations_list_kb(
    destinations: List[Destination], dest_type: str
) -> InlineKeyboardMarkup:
    """Generate keyboard listing destinations (channels or groups)."""
    keyboard: List[List[InlineKeyboardButton]] = []

    for d in destinations:
        status_icon = "🟢" if (d.is_enabled and d.automation_enabled) else "🔴"
        title = truncate_text(d.title, 22)
        btn_text = f"{status_icon} {title}"
        keyboard.append(
            [InlineKeyboardButton(btn_text, callback_data=f"dest:view:{d.id}")]
        )

    add_label = "➕ Add Channel" if dest_type == "channel" else "➕ Add Group"
    add_cb = f"dest:add:{dest_type}"
    keyboard.append([InlineKeyboardButton(add_label, callback_data=add_cb)])
    keyboard.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu:home")])

    return InlineKeyboardMarkup(keyboard)


def destination_detail_kb(dest: Destination) -> InlineKeyboardMarkup:
    """Generate management keyboard for a specific channel or group."""
    enabled_text = "🟢 Destination: Active" if dest.is_enabled else "🔴 Destination: Disabled"
    auto_text = "🟢 Auto-Post: ON" if dest.automation_enabled else "🔴 Auto-Post: OFF"
    layout_text = (
        "🎨 Layout: 2-Columns"
        if dest.layout_mode == "horizontal_2col"
        else "🎨 Layout: 1-Column"
    )

    back_target = "menu:channels" if dest.chat_type == "channel" else "menu:groups"

    keyboard = []
    if config.WEBAPP_URL:
        target_url = f"{config.WEBAPP_URL.rstrip('/')}/webapp"
        keyboard.append(
            [InlineKeyboardButton("🌐 Open Visual Mini App 🚀", web_app=WebAppInfo(url=target_url))]
        )

    keyboard.extend([
        [
            InlineKeyboardButton(
                "🔘 Manage Buttons", callback_data=f"buttons:dest:{dest.id}"
            )
        ],
        [
            InlineKeyboardButton(
                enabled_text, callback_data=f"dest:toggle_en:{dest.id}"
            ),
            InlineKeyboardButton(
                auto_text, callback_data=f"dest:toggle_auto:{dest.id}"
            ),
        ],
        [
            InlineKeyboardButton(
                layout_text, callback_data=f"dest:toggle_layout:{dest.id}"
            ),
            InlineKeyboardButton(
                "🗑 Clear All Buttons", callback_data=f"btn:clear_all_confirm:dest:{dest.id}"
            ),
        ],
        [
            InlineKeyboardButton(
                "🗑 Delete Destination", callback_data=f"dest:delete_confirm:{dest.id}"
            )
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data=back_target),
            InlineKeyboardButton("🏠 Home", callback_data="menu:home"),
        ],
    ])
    return InlineKeyboardMarkup(keyboard)


def buttons_list_kb(
    buttons: List[Button],
    dest_id: Optional[int] = None,
) -> InlineKeyboardMarkup:
    """Generate keyboard showing buttons configured for a destination with direct quick controls."""
    keyboard: List[List[InlineKeyboardButton]] = []
    dest_str = f"dest:{dest_id}" if dest_id else "default"

    for idx, b in enumerate(buttons, start=1):
        status_icon = "🟢" if b.is_enabled else "🔴"
        label_text = f"{idx}. {status_icon} {truncate_text(b.display_text, 22)}"
        keyboard.append(
            [InlineKeyboardButton(label_text, callback_data=f"btn:view:{b.id}")]
        )
        # Direct quick inline controls for each button
        quick_row = []
        if idx > 1:
            quick_row.append(InlineKeyboardButton("⬆️ Up", callback_data=f"btn:listmove:up:{b.id}:{dest_str}"))
        if idx < len(buttons):
            quick_row.append(InlineKeyboardButton("⬇️ Down", callback_data=f"btn:listmove:down:{b.id}:{dest_str}"))
        quick_row.append(InlineKeyboardButton("✏️ Edit", callback_data=f"btn:edit_label:{b.id}"))
        quick_row.append(InlineKeyboardButton("🗑 Delete", callback_data=f"btn:quickdel:{b.id}:{dest_str}"))
        keyboard.append(quick_row)

    # Action row: Add button and Preview
    keyboard.append(
        [
            InlineKeyboardButton(
                "➕ Add Button", callback_data=f"btn:add:{dest_str}"
            ),
            InlineKeyboardButton(
                "👁 Preview", callback_data=f"btn:preview:{dest_str}"
            ),
        ]
    )

    # Clear all buttons button if any exist
    if buttons:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "🗑 Delete All Buttons", callback_data=f"btn:clear_all_confirm:{dest_str}"
                )
            ]
        )

    back_target = f"dest:view:{dest_id}" if dest_id else "menu:settings"
    keyboard.append(
        [
            InlineKeyboardButton("⬅️ Back", callback_data=back_target),
            InlineKeyboardButton("🏠 Home", callback_data="menu:home"),
        ]
    )

    return InlineKeyboardMarkup(keyboard)


def button_detail_kb(
    btn: Button,
    is_first: bool = False,
    is_last: bool = False,
) -> InlineKeyboardMarkup:
    """Generate management keyboard for an individual button."""
    dest_str = f"dest:{btn.destination_id}" if btn.destination_id else "default"
    status_text = "🟢 Enabled" if btn.is_enabled else "🔴 Disabled"

    reorder_row = []
    if not is_first:
        reorder_row.append(
            InlineKeyboardButton("⬆️ Move Up", callback_data=f"btn:move:up:{btn.id}")
        )
    if not is_last:
        reorder_row.append(
            InlineKeyboardButton(
                "⬇️ Move Down", callback_data=f"btn:move:down:{btn.id}"
            )
        )

    keyboard = [
        [
            InlineKeyboardButton(
                "✏️ Edit Label", callback_data=f"btn:edit_label:{btn.id}"
            ),
            InlineKeyboardButton(
                "🔗 Edit URL", callback_data=f"btn:edit_url:{btn.id}"
            ),
        ],
        [
            InlineKeyboardButton(
                f"Status: {status_text}", callback_data=f"btn:toggle:{btn.id}"
            ),
            InlineKeyboardButton(
                "😀 Edit Emoji", callback_data=f"btn:edit_emoji:{btn.id}"
            ),
        ],
    ]

    if reorder_row:
        keyboard.append(reorder_row)

    keyboard.append(
        [
            InlineKeyboardButton(
                "🗑 Delete Button", callback_data=f"btn:delete_confirm:{btn.id}"
            )
        ]
    )
    keyboard.append(
        [
            InlineKeyboardButton(
                "⬅️ Back", callback_data=f"buttons:{dest_str}"
            ),
            InlineKeyboardButton("🏠 Home", callback_data="menu:home"),
        ]
    )

    return InlineKeyboardMarkup(keyboard)


def settings_kb(
    global_automation: bool, default_layout: str
) -> InlineKeyboardMarkup:
    """Generate system settings menu keyboard."""
    auto_text = (
        "🟢 Master Automation: ON" if global_automation else "🔴 Master Automation: OFF"
    )
    layout_text = (
        "🎨 Default Layout: 2-Columns"
        if default_layout == "horizontal_2col"
        else "🎨 Default Layout: 1-Column"
    )

    keyboard = [
        [InlineKeyboardButton(auto_text, callback_data="settings:toggle_auto")],
        [InlineKeyboardButton(layout_text, callback_data="settings:toggle_layout")],
        [
            InlineKeyboardButton(
                "🔘 Edit Default Buttons Template",
                callback_data="menu:default_buttons",
            )
        ],
        [InlineKeyboardButton("🔐 Admin Whitelist", callback_data="settings:admins")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu:home")],
    ]
    return InlineKeyboardMarkup(keyboard)


def status_kb() -> InlineKeyboardMarkup:
    """Generate system status screen keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="status:refresh"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="menu:home"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def cancel_kb(back_callback: str) -> InlineKeyboardMarkup:
    """Generate simple cancel/back button."""
    keyboard = [
        [InlineKeyboardButton("❌ Cancel", callback_data=back_callback)]
    ]
    return InlineKeyboardMarkup(keyboard)


def confirm_dialog_kb(
    confirm_callback: str, cancel_callback: str, confirm_label: str = "✅ Confirm"
) -> InlineKeyboardMarkup:
    """Generate confirmation yes/no keyboard."""
    keyboard = [
        [
            InlineKeyboardButton(confirm_label, callback_data=confirm_callback),
            InlineKeyboardButton("❌ Cancel", callback_data=cancel_callback),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
