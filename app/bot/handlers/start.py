"""Start command and main navigation handlers."""

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes
from app.bot.keyboards.admin_kb import main_menu_kb
from app.bot.permissions import admin_required
from app.services.destination_service import DestinationService
from app.services.system_service import SystemService


@admin_required
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command by displaying the main control dashboard."""
    # Clear any residual conversation user_data
    if context.user_data is not None:
        context.user_data.clear()

    counts = await DestinationService.get_summary_counts()
    global_auto = await SystemService.is_global_automation_enabled()

    channels_count = counts.get("channel", 0)
    groups_count = counts.get("group", 0) + counts.get("supergroup", 0)
    auto_badge = "🟢 ON" if global_auto else "🔴 OFF"

    dashboard_text = (
        "🤖 <b>TELEGRAM POST AUTOMATION MANAGER</b>\n\n"
        "Welcome to the central control panel for multi-channel / multi-group "
        "future-post inline button automation.\n\n"
        f"📢 <b>Configured Channels:</b> {channels_count}\n"
        f"👥 <b>Configured Groups:</b> {groups_count}\n"
        f"⚡ <b>Master Automation:</b> {auto_badge}\n\n"
        "<i>Select an option below to manage destinations, buttons, or settings:</i>"
    )

    reply_markup = main_menu_kb(global_auto)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            dashboard_text, parse_mode="HTML", reply_markup=reply_markup
        )
    elif update.effective_message:
        await update.effective_message.reply_text(
            dashboard_text, parse_mode="HTML", reply_markup=reply_markup
        )


@admin_required
async def toggle_global_auto_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Toggle the master automation switch from the main menu."""
    query = update.callback_query
    if not query:
        return

    current = await SystemService.is_global_automation_enabled()
    new_state = not current
    await SystemService.set_global_automation(new_state)

    status_msg = "🟢 Automation ENABLED" if new_state else "🔴 Automation PAUSED"
    await query.answer(status_msg, show_alert=False)

    # Refresh dashboard
    await start_command(update, context)


def register_start_handlers(app: Application) -> None:
    """Register start and home menu handlers."""
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", start_command))
    app.add_handler(CommandHandler("menu", start_command))
    app.add_handler(CallbackQueryHandler(start_command, pattern=r"^menu:home$"))
    app.add_handler(
        CallbackQueryHandler(toggle_global_auto_callback, pattern=r"^toggle:global_auto$")
    )
