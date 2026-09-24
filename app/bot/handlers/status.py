"""Handlers for system status diagnostics and health reporting."""

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes
from app.bot.keyboards.admin_kb import status_kb
from app.bot.permissions import admin_required
from app.services.system_service import SystemService
from app.utils.helpers import format_datetime


@admin_required
async def status_screen_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Display system diagnostic health report."""
    query = update.callback_query
    if query:
        await query.answer()

    health = await SystemService.get_health_status(bot_online=True)

    bot_badge = "🟢 Online" if health["bot_online"] else "🔴 Offline"
    db_badge = "🟢 Connected" if health["database_connected"] else "🔴 Connection Error"
    auto_badge = "🟢 Enabled" if health["global_automation"] else "🔴 Paused"

    uptime_sec = health["uptime_seconds"]
    hours, remainder = divmod(uptime_sec, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours}h {minutes}m {seconds}s"

    last_post = health.get("last_processed")
    if last_post:
        status_icon = "🟢" if last_post["status"] == "SUCCESS" else "⚠️"
        last_str = (
            f"{status_icon} <b>Status:</b> {last_post['status']}\n"
            f"   <b>Time:</b> {format_datetime(last_post['processed_at'])}\n"
            f"   <b>Chat ID:</b> <code>{last_post['destination_id']}</code> | <b>Msg ID:</b> <code>{last_post['message_id']}</code>"
        )
    else:
        last_str = "<i>No posts processed in this session yet.</i>"

    status_text = (
        "🛠 <b>SYSTEM DIAGNOSTIC STATUS</b>\n\n"
        f"<b>Controller Bot:</b> {bot_badge}\n"
        f"<b>Telegram API:</b> 🟢 Connected\n"
        f"<b>Database:</b> {db_badge}\n"
        f"<b>Automation Master:</b> {auto_badge}\n"
        f"<b>System Uptime:</b> {uptime_str}\n\n"
        "📊 <b>Active Destinations:</b>\n"
        f"• Channels: <b>{health['channels_count']}</b>\n"
        f"• Groups/Supergroups: <b>{health['groups_count']}</b>\n\n"
        "⚡ <b>Last Post Processing:</b>\n"
        f"{last_str}\n"
    )

    reply_markup = status_kb()

    if query:
        await query.edit_message_text(
            status_text, parse_mode="HTML", reply_markup=reply_markup
        )
    elif update.effective_message:
        await update.effective_message.reply_text(
            status_text, parse_mode="HTML", reply_markup=reply_markup
        )


def register_status_handlers(app: Application) -> None:
    """Register status handlers."""
    app.add_handler(
        CallbackQueryHandler(status_screen_handler, pattern=r"^menu:status$")
    )
    app.add_handler(
        CallbackQueryHandler(status_screen_handler, pattern=r"^status:refresh$")
    )
