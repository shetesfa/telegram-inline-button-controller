"""Handlers for managing Inline Buttons (CRUD, reordering, live preview)."""

from typing import Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from app.bot.keyboards.admin_kb import (
    button_detail_kb,
    buttons_list_kb,
    cancel_kb,
    confirm_dialog_kb,
)
from app.bot.keyboards.post_kb import build_preview_keyboard
from app.bot.permissions import admin_required
from app.services.button_service import ButtonService
from app.services.destination_service import DestinationService
from app.utils.helpers import format_status_badge
from app.utils.validation import validate_button_label, validate_url

(
    WAITING_BTN_LABEL,
    WAITING_BTN_URL,
    WAITING_EDIT_LABEL,
    WAITING_EDIT_URL,
    WAITING_EDIT_EMOJI,
) = range(5)


@admin_required
async def list_buttons_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """List buttons for a specific destination or the default template."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    data = query.data
    dest_id: Optional[int] = None
    title = "Default Template Buttons"

    if data.startswith("buttons:dest:"):
        dest_id = int(data.split(":")[-1])
        dest = await DestinationService.get_destination(dest_id)
        if dest:
            title = f"Buttons for {dest.title}"
        buttons = await ButtonService.list_for_destination(dest_id)
    else:
        # Default buttons template
        buttons = await ButtonService.list_default_templates()

    reply_markup = buttons_list_kb(buttons, dest_id=dest_id)

    text = (
        f"🔘 <b>{title.upper()}</b>\n\n"
        f"Total buttons: <b>{len(buttons)}</b>\n\n"
        "<i>Click a button to edit its label, URL, emoji, or order:</i>"
    )

    await query.edit_message_text(
        text, parse_mode="HTML", reply_markup=reply_markup
    )


@admin_required
async def view_button_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """View details and options for an individual button."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    btn_id = int(query.data.split(":")[-1])
    btn = await ButtonService.get_button(btn_id)
    if not btn:
        await query.edit_message_text(
            "⚠️ Button not found.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏠 Main Menu", callback_data="menu:home")]]
            ),
        )
        return

    # Check position in list to conditionally disable up/down buttons
    if btn.destination_id is None:
        all_btns = await ButtonService.list_default_templates()
    else:
        all_btns = await ButtonService.list_for_destination(btn.destination_id)

    ids = [b.id for b in all_btns]
    idx = ids.index(btn.id) if btn.id in ids else 0
    is_first = idx == 0
    is_last = idx == len(ids) - 1

    text = (
        f"🔘 <b>BUTTON: {btn.display_text}</b>\n\n"
        f"<b>Label:</b> {btn.label}\n"
        f"<b>Emoji:</b> {btn.emoji or '(None)'}\n"
        f"<b>URL:</b> <code>{btn.url}</code>\n"
        f"<b>Status:</b> {format_status_badge(btn.is_enabled)}\n"
        f"<b>Position:</b> #{btn.sort_order}\n"
    )

    reply_markup = button_detail_kb(btn, is_first=is_first, is_last=is_last)
    await query.edit_message_text(
        text, parse_mode="HTML", reply_markup=reply_markup
    )


@admin_required
async def toggle_button_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Toggle a button between active and disabled."""
    query = update.callback_query
    if not query or not query.data:
        return
    btn_id = int(query.data.split(":")[-1])
    new_state = await ButtonService.toggle_button(btn_id)
    msg = "🟢 Button enabled" if new_state else "🔴 Button disabled"
    await query.answer(msg)
    await view_button_handler(update, context)


@admin_required
async def move_button_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Move button up or down in order."""
    query = update.callback_query
    if not query or not query.data:
        return
    parts = query.data.split(":")  # btn:move:up:123
    direction = parts[2]
    btn_id = int(parts[3])

    moved = await ButtonService.move_button(btn_id, direction)
    if moved:
        await query.answer(f"Moved {direction}")
    else:
        await query.answer("Cannot move further in that direction", show_alert=False)

    await view_button_handler(update, context)


@admin_required
async def delete_button_confirm_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Confirmation prompt before deleting a button."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    btn_id = int(query.data.split(":")[-1])
    btn = await ButtonService.get_button(btn_id)
    if not btn:
        await query.edit_message_text("Button not found.")
        return

    dest_str = f"dest:{btn.destination_id}" if btn.destination_id else "default"

    text = (
        f"⚠️ <b>Delete Button?</b>\n\n"
        f"Are you sure you want to delete <b>{btn.display_text}</b>?\n"
        "It will no longer appear on future automated posts."
    )
    reply_markup = confirm_dialog_kb(
        confirm_callback=f"btn:delete_exec:{btn.id}",
        cancel_callback=f"btn:view:{btn.id}",
        confirm_label="🗑 Delete",
    )
    await query.edit_message_text(
        text, parse_mode="HTML", reply_markup=reply_markup
    )


@admin_required
async def delete_button_exec_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Execute button deletion."""
    query = update.callback_query
    if not query or not query.data:
        return
    btn_id = int(query.data.split(":")[-1])
    btn = await ButtonService.get_button(btn_id)
    dest_str = f"dest:{btn.destination_id}" if btn and btn.destination_id else "default"

    await ButtonService.delete_button(btn_id)
    await query.answer("Button deleted.", show_alert=True)

    # Redirect to buttons list
    query.data = f"buttons:{dest_str}"
    await list_buttons_handler(update, context)


@admin_required
async def listmove_button_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Move button up or down directly from the buttons list."""
    query = update.callback_query
    if not query or not query.data:
        return
    parts = query.data.split(":")  # btn:listmove:(up|down):{id}:{dest_str}
    direction = parts[2]
    btn_id = int(parts[3])
    dest_str = ":".join(parts[4:])

    moved = await ButtonService.move_button(btn_id, direction)
    if moved:
        await query.answer(f"Moved {direction}!")
    else:
        await query.answer("Cannot move further.", show_alert=False)

    query.data = f"buttons:{dest_str}"
    await list_buttons_handler(update, context)


@admin_required
async def quickdel_button_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Immediately delete a button from the buttons list."""
    query = update.callback_query
    if not query or not query.data:
        return
    parts = query.data.split(":")  # btn:quickdel:{id}:{dest_str}
    btn_id = int(parts[2])
    dest_str = ":".join(parts[3:])

    await ButtonService.delete_button(btn_id)
    await query.answer("🗑 Button deleted!", show_alert=False)

    query.data = f"buttons:{dest_str}"
    await list_buttons_handler(update, context)


@admin_required
async def clear_all_buttons_confirm_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Ask confirmation before clearing all buttons."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    parts = query.data.split(":")  # btn:clear_all_confirm:{dest_str}
    dest_str = ":".join(parts[2:])

    text = (
        "⚠️ <b>Delete ALL Buttons?</b>\n\n"
        "Are you sure you want to delete all buttons for this channel?\n"
        "New posts will not have any inline buttons attached until you add new ones."
    )
    reply_markup = confirm_dialog_kb(
        confirm_callback=f"btn:clear_all_exec:{dest_str}",
        cancel_callback=f"buttons:{dest_str}",
        confirm_label="🗑 Yes, Delete All",
    )
    await query.edit_message_text(
        text, parse_mode="HTML", reply_markup=reply_markup
    )


@admin_required
async def clear_all_buttons_exec_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Execute clearing all buttons."""
    query = update.callback_query
    if not query or not query.data:
        return
    parts = query.data.split(":")  # btn:clear_all_exec:{dest_str}
    dest_str = ":".join(parts[2:])

    if dest_str.startswith("dest:"):
        dest_id = int(dest_str.split(":")[-1])
        await DestinationService.reset_buttons(dest_id, load_defaults=False)
    else:
        from app.database.database import get_session
        from app.database.models import Button
        from sqlalchemy import delete
        async with get_session() as session:
            await session.execute(delete(Button).where(Button.destination_id.is_(None)))
            await session.commit()

    await query.answer("🗑 All buttons deleted successfully!", show_alert=True)
    query.data = f"buttons:{dest_str}"
    await list_buttons_handler(update, context)


@admin_required
async def preview_buttons_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Render a live interactive preview of configured inline buttons."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    data = query.data  # btn:preview:dest:123 or btn:preview:default
    parts = data.split(":")
    dest_id = int(parts[3]) if parts[2] == "dest" else None

    layout_mode = "vertical"
    if dest_id:
        dest = await DestinationService.get_destination(dest_id)
        if dest:
            layout_mode = dest.layout_mode
        buttons = await ButtonService.list_for_destination(dest_id)
        back_cb = f"buttons:dest:{dest_id}"
    else:
        buttons = await ButtonService.list_default_templates()
        back_cb = "buttons:default"

    active_count = sum(1 for b in buttons if b.is_enabled)
    if active_count == 0:
        await query.edit_message_text(
            "⚠️ No active buttons to preview. Please add or enable at least one button.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ Back", callback_data=back_cb)]]
            ),
        )
        return

    preview_text = (
        "👁 <b>LIVE BUTTON PREVIEW</b>\n\n"
        "Here is how your inline buttons will appear underneath new posts:\n\n"
        "📚 <b>Sample Post Title</b>\n"
        "This is an example post caption to preview button alignment."
    )

    preview_markup = build_preview_keyboard(
        buttons=buttons, layout_mode=layout_mode, back_callback=back_cb
    )

    await query.edit_message_text(
        preview_text, parse_mode="HTML", reply_markup=preview_markup
    )


# ==========================================
# ADD BUTTON WIZARD (CONVERSATION HANDLER)
# ==========================================


@admin_required
async def start_add_button(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Start add button wizard."""
    query = update.callback_query
    if not query or not query.data:
        return ConversationHandler.END
    await query.answer()

    data = query.data  # btn:add:dest:123 or btn:add:default
    parts = data.split(":")
    dest_id = int(parts[3]) if parts[2] == "dest" else None

    if context.user_data is not None:
        context.user_data["add_btn_dest_id"] = dest_id

    back_cb = f"buttons:dest:{dest_id}" if dest_id else "buttons:default"

    await query.edit_message_text(
        "➕ <b>ADD NEW BUTTON - Step 1 of 2</b>\n\n"
        "Please send the <b>button label text</b> (with optional emoji, e.g. <code>📢 Join Channel</code>):\n",
        parse_mode="HTML",
        reply_markup=cancel_kb(back_cb),
    )
    return WAITING_BTN_LABEL


@admin_required
async def process_btn_label(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Process button label text."""
    msg = update.effective_message
    if not msg or not msg.text:
        return WAITING_BTN_LABEL

    raw_label = msg.text.strip()
    is_valid, err_msg = validate_button_label(raw_label)
    if not is_valid:
        await msg.reply_text(f"⚠️ {err_msg} Please try again:")
        return WAITING_BTN_LABEL

    if context.user_data is not None:
        context.user_data["new_btn_label"] = raw_label
        dest_id = context.user_data.get("add_btn_dest_id")
        back_cb = f"buttons:dest:{dest_id}" if dest_id else "buttons:default"

    await msg.reply_text(
        f"Label: <b>{raw_label}</b>\n\n"
        "➕ <b>Step 2 of 2: Button Destination URL</b>\n\n"
        "Please send the link for this button (e.g. <code>https://t.me/example</code>):\n",
        parse_mode="HTML",
        reply_markup=cancel_kb(back_cb),
    )
    return WAITING_BTN_URL


@admin_required
async def process_btn_url(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Process button destination URL and create button."""
    msg = update.effective_message
    if not msg or not msg.text:
        return WAITING_BTN_URL

    raw_url = msg.text.strip()
    is_valid, err_msg = validate_url(raw_url)
    if not is_valid:
        await msg.reply_text(f"⚠️ {err_msg} Please send a valid URL (e.g. https://t.me/...):")
        return WAITING_BTN_URL

    dest_id = context.user_data.get("add_btn_dest_id") if context.user_data else None
    label = context.user_data.get("new_btn_label", "Button") if context.user_data else "Button"

    # Separate emoji if user included one at the start
    emoji = ""
    parts = label.split(" ", 1)
    if len(parts) == 2 and len(parts[0]) <= 4:
        # First word is likely emoji
        emoji = parts[0]
        label = parts[1]

    btn, err = await ButtonService.add_button(
        destination_id=dest_id,
        label=label,
        url=raw_url,
        emoji=emoji,
    )

    if context.user_data is not None:
        context.user_data.clear()

    if not btn:
        await msg.reply_text(f"⚠️ Error creating button: {err}")
        return ConversationHandler.END

    dest_str = f"dest:{dest_id}" if dest_id else "default"
    success_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "👁 Preview Buttons", callback_data=f"btn:preview:{dest_str}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔘 Back to Buttons List", callback_data=f"buttons:{dest_str}"
                )
            ],
        ]
    )

    await msg.reply_text(
        f"✅ <b>Button Created!</b>\n\n"
        f"<b>Text:</b> {btn.display_text}\n"
        f"<b>URL:</b> <code>{btn.url}</code>\n",
        parse_mode="HTML",
        reply_markup=success_markup,
    )
    return ConversationHandler.END


@admin_required
async def cancel_button_wizard(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Cancel button wizard."""
    dest_id = context.user_data.get("add_btn_dest_id") if context.user_data else None
    if context.user_data is not None:
        context.user_data.clear()

    query = update.callback_query
    if query:
        await query.answer("Operation cancelled.")
        dest_str = f"dest:{dest_id}" if dest_id else "default"
        query.data = f"buttons:{dest_str}"
        await list_buttons_handler(update, context)
    return ConversationHandler.END


def get_add_button_conversation() -> ConversationHandler:
    """Create ConversationHandler for adding a button."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_add_button, pattern=r"^btn:add:(dest:\d+|default)$")
        ],
        states={
            WAITING_BTN_LABEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_btn_label),
                CallbackQueryHandler(
                    cancel_button_wizard, pattern=r"^buttons:(dest:\d+|default)$"
                ),
            ],
            WAITING_BTN_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_btn_url),
                CallbackQueryHandler(
                    cancel_button_wizard, pattern=r"^buttons:(dest:\d+|default)$"
                ),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(
                cancel_button_wizard, pattern=r"^buttons:(dest:\d+|default)$"
            ),
            CommandHandler("cancel", cancel_button_wizard),
        ],
        per_user=True,
        per_chat=True,
        per_message=False,
    )


# ==========================================
# EDIT BUTTON WIZARDS
# ==========================================


@admin_required
async def start_edit_label(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    if not query or not query.data:
        return ConversationHandler.END
    await query.answer()
    btn_id = int(query.data.split(":")[-1])
    if context.user_data is not None:
        context.user_data["edit_btn_id"] = btn_id

    await query.edit_message_text(
        "✏️ <b>Edit Button Label</b>\n\n"
        "Send the new label text for this button:\n",
        parse_mode="HTML",
        reply_markup=cancel_kb(f"btn:view:{btn_id}"),
    )
    return WAITING_EDIT_LABEL


@admin_required
async def process_edit_label(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    msg = update.effective_message
    if not msg or not msg.text:
        return WAITING_EDIT_LABEL
    btn_id = context.user_data.get("edit_btn_id") if context.user_data else None
    if not btn_id:
        return ConversationHandler.END

    new_label = msg.text.strip()
    btn, err = await ButtonService.update_button(btn_id, label=new_label)
    if err:
        await msg.reply_text(f"⚠️ {err}")
        return WAITING_EDIT_LABEL

    if context.user_data is not None:
        context.user_data.clear()

    await msg.reply_text(
        f"✅ Label updated to: <b>{btn.display_text}</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔘 View Button", callback_data=f"btn:view:{btn_id}")]]
        ),
    )
    return ConversationHandler.END


def get_edit_label_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_edit_label, pattern=r"^btn:edit_label:\d+$")
        ],
        states={
            WAITING_EDIT_LABEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_edit_label),
                CallbackQueryHandler(cancel_button_wizard, pattern=r"^btn:view:\d+$"),
            ]
        },
        fallbacks=[
            CallbackQueryHandler(cancel_button_wizard, pattern=r"^btn:view:\d+$"),
            CommandHandler("cancel", cancel_button_wizard),
        ],
        per_user=True,
        per_chat=True,
        per_message=False,
    )


@admin_required
async def start_edit_url(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    if not query or not query.data:
        return ConversationHandler.END
    await query.answer()
    btn_id = int(query.data.split(":")[-1])
    if context.user_data is not None:
        context.user_data["edit_btn_id"] = btn_id

    await query.edit_message_text(
        "🔗 <b>Edit Button URL</b>\n\n"
        "Send the new URL destination (e.g. <code>https://t.me/example</code>):\n",
        parse_mode="HTML",
        reply_markup=cancel_kb(f"btn:view:{btn_id}"),
    )
    return WAITING_EDIT_URL


@admin_required
async def process_edit_url(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    msg = update.effective_message
    if not msg or not msg.text:
        return WAITING_EDIT_URL
    btn_id = context.user_data.get("edit_btn_id") if context.user_data else None
    if not btn_id:
        return ConversationHandler.END

    new_url = msg.text.strip()
    btn, err = await ButtonService.update_button(btn_id, url=new_url)
    if err:
        await msg.reply_text(f"⚠️ {err} Please send a valid URL:")
        return WAITING_EDIT_URL

    if context.user_data is not None:
        context.user_data.clear()

    await msg.reply_text(
        f"✅ URL updated to: <code>{btn.url}</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔘 View Button", callback_data=f"btn:view:{btn_id}")]]
        ),
    )
    return ConversationHandler.END


def get_edit_url_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_edit_url, pattern=r"^btn:edit_url:\d+$")
        ],
        states={
            WAITING_EDIT_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_edit_url),
                CallbackQueryHandler(cancel_button_wizard, pattern=r"^btn:view:\d+$"),
            ]
        },
        fallbacks=[
            CallbackQueryHandler(cancel_button_wizard, pattern=r"^btn:view:\d+$"),
            CommandHandler("cancel", cancel_button_wizard),
        ],
        per_user=True,
        per_chat=True,
        per_message=False,
    )


@admin_required
async def start_edit_emoji(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    if not query or not query.data:
        return ConversationHandler.END
    await query.answer()
    btn_id = int(query.data.split(":")[-1])
    if context.user_data is not None:
        context.user_data["edit_btn_id"] = btn_id

    await query.edit_message_text(
        "😀 <b>Edit Button Emoji / Icon</b>\n\n"
        "Send the emoji (e.g. 📢, 👥, 🤖) or send <code>none</code> to remove emoji:\n",
        parse_mode="HTML",
        reply_markup=cancel_kb(f"btn:view:{btn_id}"),
    )
    return WAITING_EDIT_EMOJI


@admin_required
async def process_edit_emoji(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    msg = update.effective_message
    if not msg or not msg.text:
        return WAITING_EDIT_EMOJI
    btn_id = context.user_data.get("edit_btn_id") if context.user_data else None
    if not btn_id:
        return ConversationHandler.END

    emoji_input = msg.text.strip()
    if emoji_input.lower() == "none":
        emoji_input = ""

    btn, err = await ButtonService.update_button(btn_id, emoji=emoji_input)
    if err:
        await msg.reply_text(f"⚠️ {err}")
        return WAITING_EDIT_EMOJI

    if context.user_data is not None:
        context.user_data.clear()

    await msg.reply_text(
        f"✅ Emoji updated! Button display: <b>{btn.display_text}</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔘 View Button", callback_data=f"btn:view:{btn_id}")]]
        ),
    )
    return ConversationHandler.END


def get_edit_emoji_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_edit_emoji, pattern=r"^btn:edit_emoji:\d+$")
        ],
        states={
            WAITING_EDIT_EMOJI: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_edit_emoji),
                CallbackQueryHandler(cancel_button_wizard, pattern=r"^btn:view:\d+$"),
            ]
        },
        fallbacks=[
            CallbackQueryHandler(cancel_button_wizard, pattern=r"^btn:view:\d+$"),
            CommandHandler("cancel", cancel_button_wizard),
        ],
        per_user=True,
        per_chat=True,
        per_message=False,
    )


def register_buttons_handlers(app: Application) -> None:
    """Register callback handlers for button management."""
    app.add_handler(
        CallbackQueryHandler(
            list_buttons_handler, pattern=r"^buttons:(dest:\d+|default)$"
        )
    )
    app.add_handler(
        CallbackQueryHandler(list_buttons_handler, pattern=r"^menu:default_buttons$")
    )
    app.add_handler(
        CallbackQueryHandler(view_button_handler, pattern=r"^btn:view:\d+$")
    )
    app.add_handler(
        CallbackQueryHandler(toggle_button_handler, pattern=r"^btn:toggle:\d+$")
    )
    app.add_handler(
        CallbackQueryHandler(move_button_handler, pattern=r"^btn:move:(up|down):\d+$")
    )
    app.add_handler(
        CallbackQueryHandler(
            delete_button_confirm_handler, pattern=r"^btn:delete_confirm:\d+$"
        )
    )
    app.add_handler(
        CallbackQueryHandler(
            delete_button_exec_handler, pattern=r"^btn:delete_exec:\d+$"
        )
    )
    app.add_handler(
        CallbackQueryHandler(
            listmove_button_handler,
            pattern=r"^btn:listmove:(up|down):\d+:(dest:\d+|default)$",
        )
    )
    app.add_handler(
        CallbackQueryHandler(
            quickdel_button_handler,
            pattern=r"^btn:quickdel:\d+:(dest:\d+|default)$",
        )
    )
    app.add_handler(
        CallbackQueryHandler(
            clear_all_buttons_confirm_handler,
            pattern=r"^btn:clear_all_confirm:(dest:\d+|default)$",
        )
    )
    app.add_handler(
        CallbackQueryHandler(
            clear_all_buttons_exec_handler,
            pattern=r"^btn:clear_all_exec:(dest:\d+|default)$",
        )
    )
    app.add_handler(
        CallbackQueryHandler(
            preview_buttons_handler, pattern=r"^btn:preview:(dest:\d+|default)$"
        )
    )
