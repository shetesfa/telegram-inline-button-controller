"""Telegram Bot Application initialization, handler routing, and lifecycle execution."""

import asyncio
import os
import sys
from typing import Any
from telegram import Update
from telegram.error import NetworkError, TelegramError
from telegram.request import HTTPXRequest
from telegram.ext import (
    Application,
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)
from app.bot.handlers.buttons import (
    get_add_button_conversation,
    get_edit_emoji_conversation,
    get_edit_label_conversation,
    get_edit_url_conversation,
    register_buttons_handlers,
)
from app.bot.handlers.channels import (
    get_add_channel_conversation,
    register_channels_handlers,
)
from app.bot.handlers.groups import (
    get_add_group_conversation,
    register_groups_handlers,
)
from app.bot.handlers.settings import register_settings_handlers
from app.bot.handlers.start import register_start_handlers
from app.bot.handlers.status import register_status_handlers
from app.config import config
from app.database.database import close_db, init_db
from app.services.button_service import ButtonService
from app.services.destination_service import DestinationService
from app.services.system_service import SystemService
from app.telegram.post_processor import handle_incoming_post
from app.utils.logging import logger


async def global_error_handler(
    update: object, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle uncaught errors across the application without crashing or leaking secrets."""
    error = context.error
    if isinstance(error, NetworkError):
        logger.warning(f"Telegram network transient issue: {error}")
        return

    logger.error(
        f"Exception while handling update {update}: {error}", exc_info=context.error
    )


def create_bot_app() -> Application:
    """Instantiate and configure the python-telegram-bot Application."""
    req = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0, write_timeout=30.0)
    app = ApplicationBuilder().token(config.BOT_TOKEN).request(req).build()

    # 1. Register Conversation Handlers (High Priority)
    app.add_handler(get_add_channel_conversation())
    app.add_handler(get_add_group_conversation())
    app.add_handler(get_add_button_conversation())
    app.add_handler(get_edit_label_conversation())
    app.add_handler(get_edit_url_conversation())
    app.add_handler(get_edit_emoji_conversation())

    # 2. Register Interactive UI & Callback Handlers
    register_start_handlers(app)
    register_channels_handlers(app)
    register_groups_handlers(app)
    register_buttons_handlers(app)
    register_settings_handlers(app)
    register_status_handlers(app)

    # 3. Register Post Processor Handlers (Incoming New Channel Posts & Group Messages)
    # Listens to channel posts
    app.add_handler(
        MessageHandler(
            filters.ChatType.CHANNEL & ~filters.COMMAND,
            handle_incoming_post,
        )
    )

    # Listens to group & supergroup messages
    app.add_handler(
        MessageHandler(
            (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP) & ~filters.COMMAND,
            handle_incoming_post,
        )
    )

    # 4. Register global error handler
    app.add_error_handler(global_error_handler)

    return app


async def print_startup_banner() -> None:
    """Display startup diagnostics in console."""
    counts = await DestinationService.get_summary_counts()
    global_auto = await SystemService.is_global_automation_enabled()
    auto_status = "ENABLED (ON)" if global_auto else "DISABLED (PAUSED)"

    banner = f"""
=====================================================
   TELEGRAM MULTI-DESTINATION POST AUTOMATION SYSTEM
=====================================================
 Environment       : {config.APP_ENV.upper()}
 Bot Token         : {config.masked_token()}
 Authorized Admins : {len(config.ADMIN_IDS)} admin ID(s) configured
 Database          : OK (SQLite async)
 Channels Active   : {counts.get('channel', 0)}
 Groups Active     : {counts.get('group', 0) + counts.get('supergroup', 0)}
 Master Automation : {auto_status}
 Mode              : Future-post automation (zero history scan)
=====================================================
🤖 System is running and listening for Telegram updates...
"""
    logger.info(banner)


async def start_web_server(port: int):
    """Start full aiohttp Web server serving Telegram Mini App and REST API."""
    from aiohttp import web
    from app.web.webapp import create_web_app

    webapp = create_web_app()
    runner = web.AppRunner(webapp)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Telegram Mini App & REST API listening on port {port} (Render ready)")
    return runner


async def run_bot_async() -> None:
    """Async main routine."""
    try:
        config.validate()
    except ValueError as e:
        logger.error(f"Configuration error:\n{e}")
        sys.exit(1)

    # Initialize database
    await init_db()
    await ButtonService.init_default_templates_if_empty()

    # Create PTB application
    app = create_bot_app()

    await app.initialize()
    await app.start()

    await print_startup_banner()

    # Start web server if PORT is set (Render Web Service or local test)
    port_env = os.environ.get("PORT")
    web_runner = None
    if port_env:
        try:
            web_runner = await start_web_server(int(port_env))
        except Exception as e:
            logger.warning(f"Could not bind web server to port {port_env}: {e}")

    # Start receiving updates via long polling
    await app.updater.start_polling(
        allowed_updates=[
            Update.MESSAGE,
            Update.CHANNEL_POST,
            Update.CALLBACK_QUERY,
        ],
        drop_pending_updates=True,  # Guarantee: do NOT process old posts while offline
    )

    # Run indefinitely until interrupted
    stop_signal = asyncio.Event()
    try:
        await stop_signal.wait()
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Shutdown signal received...")
    finally:
        logger.info("Stopping Telegram updater...")
        if web_runner:
            await web_runner.cleanup()
        if app.updater.running:
            await app.updater.stop()
        if app.running:
            await app.stop()
        await app.shutdown()
        await close_db()
        logger.info("Application shut down gracefully.")


def run_bot() -> None:
    """Synchronous launcher entry point."""
    try:
        asyncio.run(run_bot_async())
    except KeyboardInterrupt:
        logger.info("Process terminated by user.")
