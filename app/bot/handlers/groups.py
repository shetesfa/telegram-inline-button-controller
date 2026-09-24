"""Handlers for managing Telegram Groups and Supergroups."""

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
    cancel_kb,
    confirm_dialog_kb,
    destination_detail_kb,
    destinations_list_kb,
)
from app.bot.permissions import admin_required
from app.services.button_service import ButtonService
from app.services.destination_service import DestinationService
from app.telegram.permissions import check_bot_permissions
from app.utils.helpers import format_chat_type, format_datetime, format_status_badge
from app.utils.validation import clean_chat_identifier

WAITING_GROUP_INPUT, WAITING_GROUP_TEMPLATE_CHOICE = range(2)


@admin_required
async def list_groups_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show list of all configured groups and supergroups."""
    groups = await DestinationService.list_groups()
    reply_markup = destinations_list_kb(groups, dest_type="group")

    text = (
        "👥 <b>CONFIGURED TELEGRAM GROUPS</b>\n\n"
        f"Total groups: <b>{len(groups)}</b>\n\n"
        "<i>Select a group below to configure buttons and settings, or add a new group:</i>"
    )

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text, parse_mode="HTML", reply_markup=reply_markup
        )
    elif update.effective_message:
        await update.effective_message.reply_text(
            text, parse_mode="HTML", reply_markup=reply_markup
        )


@admin_required
async def view_group_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show details and configuration for a specific group."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    dest_id = int(query.data.split(":")[-1])
    dest = await DestinationService.get_destination(dest_id)
    if not dest:
        await query.edit_message_text(
            "⚠️ Group not found or was deleted.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ Back to Groups", callback_data="menu:groups")]]
            ),
        )
        return

    buttons = await ButtonService.list_for_destination(dest.id)
    active_buttons_count = sum(1 for b in buttons if b.is_enabled)

    layout_display = (
        "2-Columns (Horizontal)"
        if dest.layout_mode == "horizontal_2col"
        else "1-Column (Vertical)"
    )

    text = (
        f"👥 <b>GROUP: {dest.title}</b>\n\n"
        f"<b>Type:</b> {format_chat_type(dest.chat_type)}\n"
        f"<b>Username/ID:</b> {dest.username or dest.telegram_chat_id}\n"
        f"<b>Chat ID:</b> <code>{dest.telegram_chat_id}</code>\n"
        f"<b>Status:</b> {format_status_badge(dest.is_enabled)}\n"
        f"<b>Automation:</b> {format_status_badge(dest.automation_enabled)}\n"
        f"<b>Button Layout:</b> {layout_display}\n"
        f"<b>Configured Buttons:</b> {active_buttons_count} active / {len(buttons)} total\n"
        f"<b>Created:</b> {format_datetime(dest.created_at)}\n"
    )

    reply_markup = destination_detail_kb(dest)
    await query.edit_message_text(
        text, parse_mode="HTML", reply_markup=reply_markup
    )


# ==========================================
# ADD GROUP WIZARD (CONVERSATION HANDLER)
# ==========================================


@admin_required
async def start_add_group(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Start the add group conversation."""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "➕ <b>ADD TELEGRAM GROUP</b>\n\n"
            "1. Ensure the bot is added to your group as an Administrator.\n"
            "2. Send the group <b>@username</b> (e.g., <code>@mygroup</code>) or numeric <b>Chat ID</b> (e.g., <code>-100987654321</code>), or forward a message from the group here:\n",
            parse_mode="HTML",
            reply_markup=cancel_kb("menu:groups"),
        )
    return WAITING_GROUP_INPUT


@admin_required
async def process_group_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Process group username, ID, or forwarded message."""
    msg = update.effective_message
    if not msg:
        return WAITING_GROUP_INPUT

    # Allow user to break out of wizard with /start or /cancel
    if msg.text and msg.text.strip().lower() in ["/start", "/cancel"]:
        if context.user_data is not None:
            context.user_data.clear()
        if msg.text.strip().lower() == "/start":
            from app.bot.handlers.start import start_command
            await start_command(update, context)
            return ConversationHandler.END
        else:
            await msg.reply_text("Operation cancelled.")
            await list_groups_handler(update, context)
            return ConversationHandler.END

    chat_id_input = None
    username_input = None

    # Check if user forwarded a message from a group (PTB 22+ uses forward_origin)
    if hasattr(msg, "forward_origin") and msg.forward_origin:
        origin = msg.forward_origin
        origin_chat = getattr(origin, "chat", None) or getattr(origin, "sender_chat", None)
        if origin_chat:
            chat_id_input = origin_chat.id
            username_input = f"@{origin_chat.username}" if origin_chat.username else None
    elif getattr(msg, "forward_from_chat", None):
        chat_id_input = msg.forward_from_chat.id
        username_input = (
            f"@{msg.forward_from_chat.username}"
            if msg.forward_from_chat.username
            else None
        )
    elif msg.text:
        chat_id_input, username_input = clean_chat_identifier(msg.text)

    identifier = chat_id_input or username_input
    if not identifier:
        await msg.reply_text(
            "⚠️ Invalid format. Please provide a valid username like <code>@mygroup</code>, "
            "a numeric ID like <code>-100987654321</code>, or forward a message from the group.",
            parse_mode="HTML",
            reply_markup=cancel_kb("menu:groups"),
        )
        return WAITING_GROUP_INPUT

    await msg.reply_text("🔍 <i>Verifying group access and bot permissions...</i>", parse_mode="HTML")

    is_valid, chat_info, error_msg = await check_bot_permissions(
        context.bot, identifier
    )

    if not is_valid:
        error_display = (
            f"⚠️ <b>Permission / Access Issue</b>\n\n"
            f"{error_msg}\n\n"
            "<b>Troubleshooting:</b>\n"
            "1. Open group settings in Telegram.\n"
            "2. Add the bot to the group members/administrators.\n"
            "3. Try sending the group @username or ID again."
        )
        await msg.reply_text(
            error_display,
            parse_mode="HTML",
            reply_markup=cancel_kb("menu:groups"),
        )
        return WAITING_GROUP_INPUT

    if not chat_info or chat_info["type"] not in ("group", "supergroup"):
        await msg.reply_text(
            f"⚠️ Found destination is a <b>{chat_info['type'] if chat_info else 'unknown'}</b>, not a group.\n"
            "To add a channel, use the Channels menu.",
            parse_mode="HTML",
            reply_markup=cancel_kb("menu:groups"),
        )
        return WAITING_GROUP_INPUT

    if context.user_data is not None:
        context.user_data["new_group_info"] = chat_info

    prompt_text = (
        f"✅ <b>Group Verified!</b>\n\n"
        f"<b>Title:</b> {chat_info['title']}\n"
        f"<b>Type:</b> {format_chat_type(chat_info['type'])}\n"
        f"<b>Chat ID:</b> <code>{chat_info['id']}</code>\n\n"
        "How would you like to initialize button configuration for this group?"
    )

    choice_kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔘 Use Default Buttons Template",
                    callback_data="addgrp_tpl:default",
                )
            ],
            [
                InlineKeyboardButton(
                    "✨ Start Empty (No Buttons)",
                    callback_data="addgrp_tpl:empty",
                )
            ],
            [InlineKeyboardButton("❌ Cancel", callback_data="menu:groups")],
        ]
    )

    await msg.reply_text(prompt_text, parse_mode="HTML", reply_markup=choice_kb)
    return WAITING_GROUP_TEMPLATE_CHOICE


@admin_required
async def process_group_template_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Finalize group addition based on template selection."""
    query = update.callback_query
    if not query or not query.data:
        return ConversationHandler.END
    await query.answer()

    use_defaults = query.data == "addgrp_tpl:default"
    group_info = (
        context.user_data.get("new_group_info")
        if context.user_data
        else None
    )

    if not group_info:
        await query.edit_message_text(
            "⚠️ Session expired. Please start over from the groups menu.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("👥 Groups", callback_data="menu:groups")]]
            ),
        )
        return ConversationHandler.END

    dest, created = await DestinationService.add_destination(
        chat_id=group_info["id"],
        title=group_info["title"],
        chat_type=group_info["type"],
        username=group_info["username"],
        use_default_buttons=use_defaults,
    )

    if context.user_data is not None:
        context.user_data.clear()

    btn_count = len(await ButtonService.list_for_destination(dest.id))
    success_text = (
        f"🎉 <b>Group Successfully Added!</b>\n\n"
        f"<b>Group:</b> {dest.title}\n"
        f"<b>Type:</b> {format_chat_type(dest.chat_type)}\n"
        f"<b>Status:</b> 🟢 Automation Enabled\n"
        f"<b>Buttons Configured:</b> {btn_count}\n\n"
        "Whenever a new post is published in this group, the system will automatically attach the configured inline keyboard buttons."
    )

    after_kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔘 Manage Group Buttons",
                    callback_data=f"buttons:dest:{dest.id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "👥 Back to Groups", callback_data="menu:groups"
                ),
                InlineKeyboardButton("🏠 Main Menu", callback_data="menu:home"),
            ],
        ]
    )

    await query.edit_message_text(
        success_text, parse_mode="HTML", reply_markup=after_kb
    )
    return ConversationHandler.END


@admin_required
async def cancel_add_group(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Cancel the add group conversation."""
    if context.user_data is not None:
        context.user_data.clear()
    query = update.callback_query
    if query:
        await query.answer("Operation cancelled.")
        await list_groups_handler(update, context)
    return ConversationHandler.END


def get_add_group_conversation() -> ConversationHandler:
    """Create ConversationHandler for adding a group."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_add_group, pattern=r"^dest:add:group$")
        ],
        states={
            WAITING_GROUP_INPUT: [
                MessageHandler(
                    filters.TEXT | filters.FORWARDED, process_group_input
                ),
                CallbackQueryHandler(cancel_add_group, pattern=r"^menu:groups$"),
            ],
            WAITING_GROUP_TEMPLATE_CHOICE: [
                CallbackQueryHandler(
                    process_group_template_choice,
                    pattern=r"^addgrp_tpl:(default|empty)$",
                ),
                CallbackQueryHandler(cancel_add_group, pattern=r"^menu:groups$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_add_group, pattern=r"^menu:groups$"),
            CommandHandler("cancel", cancel_add_group),
        ],
        per_user=True,
        per_chat=True,
        per_message=False,
    )


def register_groups_handlers(app: Application) -> None:
    """Register callbacks for group management."""
    app.add_handler(
        CallbackQueryHandler(list_groups_handler, pattern=r"^menu:groups$")
    )
    # view_channel_handler and toggles in channels.py handle both channels and groups via dest:view:<id>
