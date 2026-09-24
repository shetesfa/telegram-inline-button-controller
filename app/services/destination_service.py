"""Service layer for managing Telegram Destinations (Channels and Groups)."""

from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.database import get_session
from app.database.models import Destination
from app.database.repository import ButtonRepository, DestinationRepository
from app.utils.logging import logger


class DestinationService:
    """Business logic for destination management."""

    @staticmethod
    async def list_channels() -> List[Destination]:
        """List all configured channels."""
        async with get_session() as session:
            return await DestinationRepository.list_by_type(session, ["channel"])

    @staticmethod
    async def list_groups() -> List[Destination]:
        """List all configured groups and supergroups."""
        async with get_session() as session:
            return await DestinationRepository.list_by_type(
                session, ["group", "supergroup"]
            )

    @staticmethod
    async def get_destination(dest_id: int) -> Optional[Destination]:
        """Get destination by internal ID."""
        async with get_session() as session:
            return await DestinationRepository.get_by_id(session, dest_id)

    @staticmethod
    async def get_by_chat_id(chat_id: int) -> Optional[Destination]:
        """Get destination by Telegram Chat ID."""
        async with get_session() as session:
            return await DestinationRepository.get_by_chat_id(session, chat_id)

    @staticmethod
    async def add_destination(
        chat_id: int,
        title: str,
        chat_type: str,
        username: Optional[str] = None,
        use_default_buttons: bool = True,
        layout_mode: str = "vertical",
    ) -> Tuple[Destination, bool]:
        """
        Add or update a destination.
        Returns (destination, created: bool).
        """
        async with get_session() as session:
            existing = await DestinationRepository.get_by_chat_id(session, chat_id)
            if existing:
                # Update existing info
                existing.title = title
                existing.username = username
                existing.chat_type = chat_type
                existing.is_enabled = True
                await session.flush()
                logger.info(
                    f"Updated destination: ID={existing.id}, Title='{title}', ChatID={chat_id}"
                )
                return existing, False

            # Create new destination
            new_dest = await DestinationRepository.create(
                session=session,
                chat_id=chat_id,
                title=title,
                chat_type=chat_type,
                username=username,
                is_enabled=True,
                automation_enabled=True,
                layout_mode=layout_mode,
            )

            if use_default_buttons:
                await ButtonRepository.copy_default_templates(session, new_dest.id)

            logger.info(
                f"Created new destination: ID={new_dest.id}, Title='{title}', Type={chat_type}, ChatID={chat_id}"
            )
            return new_dest, True

    @staticmethod
    async def toggle_enabled(dest_id: int) -> Optional[bool]:
        """Toggle is_enabled state for destination."""
        async with get_session() as session:
            dest = await DestinationRepository.get_by_id(session, dest_id)
            if not dest:
                return None
            dest.is_enabled = not dest.is_enabled
            await session.flush()
            logger.info(f"Toggled destination ID={dest_id} is_enabled to {dest.is_enabled}")
            return dest.is_enabled

    @staticmethod
    async def toggle_automation(dest_id: int) -> Optional[bool]:
        """Toggle automation_enabled state for destination."""
        async with get_session() as session:
            dest = await DestinationRepository.get_by_id(session, dest_id)
            if not dest:
                return None
            dest.automation_enabled = not dest.automation_enabled
            await session.flush()
            logger.info(
                f"Toggled destination ID={dest_id} automation_enabled to {dest.automation_enabled}"
            )
            return dest.automation_enabled

    @staticmethod
    async def set_layout_mode(dest_id: int, layout_mode: str) -> bool:
        """Set layout mode for destination buttons ('vertical' or 'horizontal_2col')."""
        async with get_session() as session:
            dest = await DestinationRepository.get_by_id(session, dest_id)
            if not dest:
                return False
            dest.layout_mode = layout_mode
            await session.flush()
            logger.info(f"Set destination ID={dest_id} layout_mode to '{layout_mode}'")
            return True

    @staticmethod
    async def delete_destination(dest_id: int) -> bool:
        """Delete destination and all associated buttons."""
        async with get_session() as session:
            success = await DestinationRepository.delete(session, dest_id)
            if success:
                logger.info(f"Deleted destination ID={dest_id}")
            return success

    @staticmethod
    async def reset_buttons(dest_id: int, load_defaults: bool = False) -> bool:
        """Clear all buttons for a destination and optionally re-populate defaults."""
        async with get_session() as session:
            dest = await DestinationRepository.get_by_id(session, dest_id)
            if not dest:
                return False
            existing_buttons = await ButtonRepository.list_for_destination(
                session, dest_id
            )
            for b in existing_buttons:
                await session.delete(b)
            if load_defaults:
                await ButtonRepository.copy_default_templates(session, dest_id)
            await session.flush()
            logger.info(
                f"Reset buttons for destination ID={dest_id}, loaded_defaults={load_defaults}"
            )
            return True

    @staticmethod
    async def get_summary_counts() -> Dict[str, int]:
        """Get summary count of destinations."""
        async with get_session() as session:
            return await DestinationRepository.count_by_type(session)
