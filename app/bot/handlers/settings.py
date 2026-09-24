"""Handlers for system configuration and global settings."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes
from app.bot.keyboards.admin_kb import settings_kb
from app.bot.permissions import admin_required
from app.config import config
from app.services.system_service import SystemService


@admin_required
async def settings_menu_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Display system settings menu."""
    global_auto = await SystemService.is_global_automation_enabled()
    default_layout = await SystemService.get_default_layout()

    layout_display = (
        "2-Columns (Horizontal)"
        if default_layout == "horizontal_2col"
        else "1-Column (Vertical)"
    )

    text = (
        "⚙️ <b>SYSTEM SETTINGS</b>\n\n"
        f"🤖 <b>Master Automation:</b> {'🟢 ON' if global_auto else '🔴 OFF'}\n"
        f"🔘 <b>Default Button Layout:</b> {layout_display}\n"
        f"🔐 <b>Authorized Admins:</b> {len(config.ADMIN_IDS)} configured\n\n"
        "<i>Configure global presets and defaults for newly added destinations:</i>"
    )

    reply_markup = settings_kb(
        global_automation=global_auto, default_layout=default_layout
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
async def toggle_settings_auto_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Toggle master automation from settings menu."""
    query = update.callback_query
    if not query:
        return
    current = await SystemService.is_global_automation_enabled()
    new_val = not current
    await SystemService.set_global_automation(new_val)
    msg = "🟢 Master Automation ENABLED" if new_val else "🔴 Master Automation PAUSED"
    await query.answer(msg)
    await settings_menu_handler(update, context)


@admin_required
async def toggle_settings_layout_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Toggle default layout mode for new destinations."""
    query = update.callback_query
    if not query:
        return
    current = await SystemService.get_default_layout()
    new_val = "horizontal_2col" if current == "vertical" else "vertical"
    await SystemService.set_default_layout(new_val)
    await query.answer(f"Default layout set to {new_val}")
    await settings_menu_handler(update, context)


@admin_required
async def view_admins_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Display authorized administrator whitelist."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    admins_list = "\n".join([f"• <code>{admin_id}</code>" for admin_id in sorted(config.ADMIN_IDS)])
    text = (
        "🔐 <b>AUTHORIZED ADMINISTRATORS</b>\n\n"
        "The following Telegram User IDs are whitelisted to control this bot:\n\n"
        f"{admins_list}\n\n"
        "<i>To add or remove administrators, modify the <code>ADMIN_IDS</code> variable in your <code>.env</code> file and restart the bot.</i>"
    )

    reply_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Back to Settings", callback_data="menu:settings")]]
    )

    await query.edit_message_text(
        text, parse_mode="HTML", reply_markup=reply_markup
    )


def register_settings_handlers(app: Application) -> None:
    """Register settings handlers."""
    app.add_handler(
        CallbackQueryHandler(settings_menu_handler, pattern=r"^menu:settings$")
    )
    app.add_handler(
        CallbackQueryHandler(
            toggle_settings_auto_handler, pattern=r"^settings:toggle_auto$"
        )
    )
    app.add_handler(
        CallbackQueryHandler(
            toggle_settings_layout_handler, pattern=r"^settings:toggle_layout$"
        )
    )
    app.add_handler(
        CallbackQueryHandler(view_admins_handler, pattern=r"^settings:admins$")
    )
