"""Configuration management for the Telegram Post Manager application."""

import os
from pathlib import Path
from typing import Set
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    """Application configuration loaded from environment variables."""

    def __init__(self) -> None:
        self.load_from_env()

    def load_from_env(self) -> None:
        """Load and parse settings from environment variables."""
        self.BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
        self.DATABASE_URL: str = os.getenv(
            "DATABASE_URL", "sqlite+aiosqlite:///telegram_manager.db"
        ).strip()
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper().strip()
        self.APP_ENV: str = os.getenv("APP_ENV", "development").lower().strip()

        # Parse admin IDs from comma-separated list
        admin_ids_raw: str = os.getenv("ADMIN_IDS", "").strip()
        self.ADMIN_IDS: Set[int] = set()

        if admin_ids_raw:
            for part in admin_ids_raw.split(","):
                part_cleaned = part.strip()
                if part_cleaned.isdigit() or (
                    part_cleaned.startswith("-") and part_cleaned[1:].isdigit()
                ):
                    self.ADMIN_IDS.add(int(part_cleaned))

    def is_admin(self, user_id: int | None) -> bool:
        """Check whether a Telegram user ID is an authorized administrator."""
        if user_id is None:
            return False
        return user_id in self.ADMIN_IDS

    def validate(self) -> None:
        """Validate required configuration values."""
        errors = []
        if not self.BOT_TOKEN or self.BOT_TOKEN.startswith("YOUR_") or ":" not in self.BOT_TOKEN:
            errors.append(
                "BOT_TOKEN is missing or invalid. Set a valid token from @BotFather in .env"
            )
        if not self.ADMIN_IDS:
            errors.append(
                "ADMIN_IDS is empty. Set at least one Telegram user ID in .env (e.g., ADMIN_IDS=123456789)"
            )
        if errors:
            raise ValueError("\n".join(errors))

    def masked_token(self) -> str:
        """Return masked bot token safe for logging."""
        if not self.BOT_TOKEN:
            return "[NOT SET]"
        if ":" in self.BOT_TOKEN:
            bot_id, secret = self.BOT_TOKEN.split(":", 1)
            masked_secret = secret[:3] + "..." + secret[-3:] if len(secret) > 6 else "..."
            return f"{bot_id}:{masked_secret}"
        return self.BOT_TOKEN[:4] + "..." + self.BOT_TOKEN[-4:] if len(self.BOT_TOKEN) > 8 else "***"


config = Config()
