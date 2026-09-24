"""Service layer for system-wide settings, health status diagnostics, and metrics."""

import time
from datetime import datetime, timezone
from typing import Any, Dict
from sqlalchemy import text
from app.database.database import get_session
from app.database.repository import DestinationRepository, SettingRepository
from app.services.post_service import PostService
from app.utils.logging import logger

START_TIME = time.time()


class SystemService:
    """System configuration and diagnostic health checks."""

    @staticmethod
    async def is_global_automation_enabled() -> bool:
        """Check if global automation master switch is ON."""
        async with get_session() as session:
            val = await SettingRepository.get(
                session, "global_automation", default="true"
            )
            return val.lower() == "true"

    @staticmethod
    async def set_global_automation(enabled: bool) -> None:
        """Set global automation master switch."""
        async with get_session() as session:
            await SettingRepository.set(
                session, "global_automation", "true" if enabled else "false"
            )
            logger.info(f"Global automation set to: {enabled}")

    @staticmethod
    async def get_default_layout() -> str:
        """Get default button layout mode ('vertical' or 'horizontal_2col')."""
        async with get_session() as session:
            return await SettingRepository.get(
                session, "default_layout", default="vertical"
            )

    @staticmethod
    async def set_default_layout(layout: str) -> None:
        """Set default button layout mode."""
        async with get_session() as session:
            await SettingRepository.set(session, "default_layout", layout)
            logger.info(f"Default button layout set to: {layout}")

    @staticmethod
    async def get_health_status(bot_online: bool = True) -> Dict[str, Any]:
        """Collect live health check diagnostics."""
        db_ok = False
        counts = {"channel": 0, "group": 0, "supergroup": 0}

        try:
            async with get_session() as session:
                await session.execute(text("SELECT 1"))
                db_ok = True
                counts = await DestinationRepository.count_by_type(session)
        except Exception as e:
            logger.error(f"Database health check failed: {e}")

        automation_on = await SystemService.is_global_automation_enabled()
        last_post = await PostService.get_last_processed_info()
        uptime_seconds = int(time.time() - START_TIME)

        return {
            "bot_online": bot_online,
            "database_connected": db_ok,
            "global_automation": automation_on,
            "channels_count": counts.get("channel", 0),
            "groups_count": counts.get("group", 0) + counts.get("supergroup", 0),
            "last_processed": last_post,
            "uptime_seconds": uptime_seconds,
        }
