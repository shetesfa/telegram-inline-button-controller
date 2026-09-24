"""Main entry point for the Telegram Post Automation System."""

import sys
from app.bot.bot import run_bot
from app.utils.logging import logger

if __name__ == "__main__":
    logger.info("Starting Telegram Post Automation Manager...")
    try:
        run_bot()
    except Exception as e:
        logger.critical(f"Fatal error on startup: {e}", exc_info=True)
        sys.exit(1)
