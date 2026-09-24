"""Handlers for managing Telegram Channels."""

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
from app.utils.helpers import format_datetime, format_status_badge
from app.utils.validation import clean_chat_identifier

WAITING_CHANNEL_INPUT, WAITING_TEMPLATE_CHOICE = range(2)


@admin_required
async def list_channels_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show list of all configured channels."""
    channels = await DestinationService.list_channels()
    reply_markup = destinations_list_kb(channels, dest_type="channel")

    text = (
        "📢 <b>CONFIGURED TELEGRAM CHANNELS</b>\n\n"
        f"Total channels: <b>{len(channels)}</b>\n\n"
        "<i>Select a channel below to configure buttons and settings, or add a new channel:</i>"
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
async def view_channel_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show details and configuration for a specific channel."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    dest_id = int(query.data.split(":")[-1])
    dest = await DestinationService.get_destination(dest_id)
    if not dest:
        await query.edit_message_text(
            "⚠️ Channel not found or was deleted.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ Back to Channels", callback_data="menu:channels")]]
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
        f"📢 <b>CHANNEL: {dest.title}</b>\n\n"
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


@admin_required
async def toggle_channel_enabled_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Toggle destination is_enabled status."""
    query = update.callback_query
    if not query or not query.data:
        return
    dest_id = int(query.data.split(":")[-1])
    new_status = await DestinationService.toggle_enabled(dest_id)
    msg = "🟢 Channel enabled" if new_status else "🔴 Channel disabled"
    await query.answer(msg)
    await view_channel_handler(update, context)


@admin_required
async def toggle_channel_auto_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Toggle destination automation_enabled status."""
    query = update.callback_query
    if not query or not query.data:
        return
    dest_id = int(query.data.split(":")[-1])
    new_status = await DestinationService.toggle_automation(dest_id)
    msg = "🟢 Auto-post enabled" if new_status else "🔴 Auto-post paused"
    await query.answer(msg)
    await view_channel_handler(update, context)


@admin_required
async def toggle_channel_layout_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Toggle button layout mode between vertical and horizontal_2col."""
    query = update.callback_query
    if not query or not query.data:
        return
    dest_id = int(query.data.split(":")[-1])
    dest = await DestinationService.get_destination(dest_id)
    if dest:
        new_mode = (
            "vertical" if dest.layout_mode == "horizontal_2col" else "horizontal_2col"
        )
        await DestinationService.set_layout_mode(dest_id, new_mode)
        await query.answer(f"Layout changed to {new_mode}")
    await view_channel_handler(update, context)


@admin_required
async def delete_channel_confirm_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show confirmation prompt before deleting a channel."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()
    dest_id = int(query.data.split(":")[-1])
    dest = await DestinationService.get_destination(dest_id)
    if not dest:
        await query.edit_message_text("Channel not found.")
        return

    text = (
        f"⚠️ <b>Delete Channel Configuration?</b>\n\n"
        f"Are you sure you want to remove <b>{dest.title}</b>?\n\n"
        "This will delete all custom button settings for this channel. "
        "Future posts in this channel will no longer receive automated buttons."
    )
    reply_markup = confirm_dialog_kb(
        confirm_callback=f"dest:delete_exec:{dest_id}",
        cancel_callback=f"dest:view:{dest_id}",
        confirm_label="🗑 Delete Permanently",
    )
    await query.edit_message_text(
        text, parse_mode="HTML", reply_markup=reply_markup
    )


@admin_required
async def delete_channel_exec_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Execute channel deletion."""
    query = update.callback_query
    if not query or not query.data:
        return
    dest_id = int(query.data.split(":")[-1])
    await DestinationService.delete_destination(dest_id)
    await query.answer("🗑 Channel removed successfully.", show_alert=True)
    await list_channels_handler(update, context)


@admin_required
async def reset_channel_confirm_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show confirmation dialog to reset buttons to default template."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()
    dest_id = int(query.data.split(":")[-1])

    text = (
        "🔄 <b>Reset Channel Buttons?</b>\n\n"
        "This will clear the current button list for this channel and copy the "
        "global default button template."
    )
    reply_markup = confirm_dialog_kb(
        confirm_callback=f"dest:reset_exec:{dest_id}",
        cancel_callback=f"dest:view:{dest_id}",
        confirm_label="🔄 Yes, Reset Buttons",
    )
    await query.edit_message_text(
        text, parse_mode="HTML", reply_markup=reply_markup
    )


@admin_required
async def reset_channel_exec_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Execute channel buttons reset."""
    query = update.callback_query
    if not query or not query.data:
        return
    dest_id = int(query.data.split(":")[-1])
    await DestinationService.reset_buttons(dest_id, load_defaults=True)
    await query.answer("Buttons reset to default template.", show_alert=True)
    await view_channel_handler(update, context)


# ==========================================
# ADD CHANNEL WIZARD (CONVERSATION HANDLER)
# ==========================================


@admin_required
async def start_add_channel(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Start the add channel conversation."""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "➕ <b>ADD TELEGRAM CHANNEL</b>\n\n"
            "1. Ensure the bot is added as an <b>Administrator</b> in your channel with <b>Edit Messages</b> permission.\n"
            "2. Send the channel <b>@username</b> (e.g., <code>@mychannel</code>) or numeric <b>Chat ID</b> (e.g., <code>-100123456789</code>), or forward a post from the channel here:\n",
            parse_mode="HTML",
            reply_markup=cancel_kb("menu:channels"),
        )
    return WAITING_CHANNEL_INPUT


@admin_required
async def process_channel_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Process channel username, ID, or forwarded post."""
    msg = update.effective_message
    if not msg:
        return WAITING_CHANNEL_INPUT

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
            await list_channels_handler(update, context)
            return ConversationHandler.END

    chat_id_input = None
    username_input = None

    # Check if user forwarded a message from a channel (PTB 22+ uses forward_origin)
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
            "⚠️ Invalid format. Please provide a valid username like <code>@mychannel</code>, "
            "a numeric ID like <code>-100123456789</code>, or forward a message from the channel.",
            parse_mode="HTML",
            reply_markup=cancel_kb("menu:channels"),
        )
        return WAITING_CHANNEL_INPUT

    # Verify access and bot permissions via Telegram API
    await msg.reply_text("🔍 <i>Verifying channel access and bot permissions...</i>", parse_mode="HTML")

    is_valid, chat_info, error_msg = await check_bot_permissions(
        context.bot, identifier
    )

    if not is_valid:
        error_display = (
            f"⚠️ <b>Permission / Access Issue</b>\n\n"
            f"{error_msg}\n\n"
            "<b>Troubleshooting:</b>\n"
            "1. Open channel settings in Telegram.\n"
            "2. Go to <i>Administrators</i> -> <i>Add Administrator</i>.\n"
            "3. Search for this bot and grant <b>Edit Messages of Others</b> rights.\n"
            "4. Try sending the channel @username or ID again."
        )
        await msg.reply_text(
            error_display,
            parse_mode="HTML",
            reply_markup=cancel_kb("menu:channels"),
        )
        return WAITING_CHANNEL_INPUT

    if not chat_info or chat_info["type"] != "channel":
        await msg.reply_text(
            f"⚠️ Found destination is a <b>{chat_info['type'] if chat_info else 'unknown'}</b>, not a channel.\n"
            "To add a group, use the Groups menu.",
            parse_mode="HTML",
            reply_markup=cancel_kb("menu:channels"),
        )
        return WAITING_CHANNEL_INPUT

    # Save validated info into user_data for next step
    if context.user_data is not None:
        context.user_data["new_channel_info"] = chat_info

    prompt_text = (
        f"✅ <b>Channel Verified!</b>\n\n"
        f"<b>Title:</b> {chat_info['title']}\n"
        f"<b>Username:</b> {chat_info['username'] or 'None (Private)'}\n"
        f"<b>Chat ID:</b> <code>{chat_info['id']}</code>\n"
        f"<b>Permissions:</b> 🟢 Bot can edit messages\n\n"
        "How would you like to initialize button configuration for this channel?"
    )

    choice_kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✨ Start Clean (0 Buttons - Recommended)",
                    callback_data="addchan_tpl:empty",
                )
            ],
            [
                InlineKeyboardButton(
                    "🔘 Pre-fill Sample Buttons",
                    callback_data="addchan_tpl:default",
                )
            ],
            [InlineKeyboardButton("❌ Cancel", callback_data="menu:channels")],
        ]
    )

    await msg.reply_text(prompt_text, parse_mode="HTML", reply_markup=choice_kb)
    return WAITING_TEMPLATE_CHOICE


@admin_required
async def process_template_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Finalize channel addition based on template selection."""
    query = update.callback_query
    if not query or not query.data:
        return ConversationHandler.END
    await query.answer()

    use_defaults = query.data == "addchan_tpl:default"
    channel_info = (
        context.user_data.get("new_channel_info")
        if context.user_data
        else None
    )

    if not channel_info:
        await query.edit_message_text(
            "⚠️ Session expired. Please start over from the channels menu.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("📢 Channels", callback_data="menu:channels")]]
            ),
        )
        return ConversationHandler.END

    dest, created = await DestinationService.add_destination(
        chat_id=channel_info["id"],
        title=channel_info["title"],
        chat_type="channel",
        username=channel_info["username"],
        use_default_buttons=use_defaults,
    )

    if context.user_data is not None:
        context.user_data.clear()

    btn_count = len(await ButtonService.list_for_destination(dest.id))
    success_text = (
        f"🎉 <b>Channel Successfully Added!</b>\n\n"
        f"<b>Channel:</b> {dest.title}\n"
        f"<b>Status:</b> 🟢 Automation Enabled\n"
        f"<b>Buttons Configured:</b> {btn_count}\n\n"
        "Whenever a new post is published in this channel, the system will automatically attach the configured inline keyboard buttons."
    )

    after_kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔘 Manage Channel Buttons",
                    callback_data=f"buttons:dest:{dest.id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "📢 Back to Channels", callback_data="menu:channels"
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
async def cancel_add_channel(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Cancel the add channel conversation."""
    if context.user_data is not None:
        context.user_data.clear()
    query = update.callback_query
    if query:
        await query.answer("Operation cancelled.")
        await list_channels_handler(update, context)
    return ConversationHandler.END


def get_add_channel_conversation() -> ConversationHandler:
    """Create ConversationHandler for adding a channel."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_add_channel, pattern=r"^dest:add:channel$")
        ],
        states={
            WAITING_CHANNEL_INPUT: [
                MessageHandler(
                    filters.TEXT | filters.FORWARDED, process_channel_input
                ),
                CallbackQueryHandler(cancel_add_channel, pattern=r"^menu:channels$"),
            ],
            WAITING_TEMPLATE_CHOICE: [
                CallbackQueryHandler(
                    process_template_choice, pattern=r"^addchan_tpl:(default|empty)$"
                ),
                CallbackQueryHandler(cancel_add_channel, pattern=r"^menu:channels$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_add_channel, pattern=r"^menu:channels$"),
            CommandHandler("cancel", cancel_add_channel),
        ],
        per_user=True,
        per_chat=True,
        per_message=False,
    )


def register_channels_handlers(app: Application) -> None:
    """Register standard callbacks for channels management."""
    app.add_handler(
        CallbackQueryHandler(list_channels_handler, pattern=r"^menu:channels$")
    )
    app.add_handler(
        CallbackQueryHandler(view_channel_handler, pattern=r"^dest:view:\d+$")
    )
    app.add_handler(
        CallbackQueryHandler(toggle_channel_enabled_handler, pattern=r"^dest:toggle_en:\d+$")
    )
    app.add_handler(
        CallbackQueryHandler(toggle_channel_auto_handler, pattern=r"^dest:toggle_auto:\d+$")
    )
    app.add_handler(
        CallbackQueryHandler(toggle_channel_layout_handler, pattern=r"^dest:toggle_layout:\d+$")
    )
    app.add_handler(
        CallbackQueryHandler(delete_channel_confirm_handler, pattern=r"^dest:delete_confirm:\d+$")
    )
    app.add_handler(
        CallbackQueryHandler(delete_channel_exec_handler, pattern=r"^dest:delete_exec:\d+$")
    )
    app.add_handler(
        CallbackQueryHandler(reset_channel_confirm_handler, pattern=r"^dest:reset_confirm:\d+$")
    )
    app.add_handler(
        CallbackQueryHandler(reset_channel_exec_handler, pattern=r"^dest:reset_exec:\d+$")
    )
