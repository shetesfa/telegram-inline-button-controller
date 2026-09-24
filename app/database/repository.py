"""Repository layer for async database operations."""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import Button, Destination, ProcessedPost, SystemSetting


class DestinationRepository:
    """CRUD operations for Destination entities (Channels and Groups)."""

    @staticmethod
    async def get_by_id(session: AsyncSession, dest_id: int) -> Optional[Destination]:
        stmt = select(Destination).where(Destination.id == dest_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_chat_id(
        session: AsyncSession, chat_id: int
    ) -> Optional[Destination]:
        stmt = select(Destination).where(Destination.telegram_chat_id == chat_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_all(session: AsyncSession) -> List[Destination]:
        stmt = select(Destination).order_by(Destination.title.asc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def list_by_type(
        session: AsyncSession, chat_types: List[str]
    ) -> List[Destination]:
        stmt = (
            select(Destination)
            .where(Destination.chat_type.in_(chat_types))
            .order_by(Destination.title.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create(
        session: AsyncSession,
        chat_id: int,
        title: str,
        chat_type: str,
        username: Optional[str] = None,
        is_enabled: bool = True,
        automation_enabled: bool = True,
        layout_mode: str = "vertical",
    ) -> Destination:
        dest = Destination(
            telegram_chat_id=chat_id,
            title=title,
            username=username,
            chat_type=chat_type,
            is_enabled=is_enabled,
            automation_enabled=automation_enabled,
            layout_mode=layout_mode,
        )
        session.add(dest)
        await session.flush()
        return dest

    @staticmethod
    async def update(
        session: AsyncSession,
        dest_id: int,
        **kwargs,
    ) -> Optional[Destination]:
        dest = await DestinationRepository.get_by_id(session, dest_id)
        if not dest:
            return None
        for key, value in kwargs.items():
            if hasattr(dest, key):
                setattr(dest, key, value)
        dest.updated_at = datetime.now(timezone.utc)
        await session.flush()
        return dest

    @staticmethod
    async def delete(session: AsyncSession, dest_id: int) -> bool:
        dest = await DestinationRepository.get_by_id(session, dest_id)
        if not dest:
            return False
        await session.delete(dest)
        await session.flush()
        return True

    @staticmethod
    async def count_by_type(session: AsyncSession) -> Dict[str, int]:
        stmt = select(Destination.chat_type, func.count(Destination.id)).group_by(
            Destination.chat_type
        )
        result = await session.execute(stmt)
        counts = {"channel": 0, "group": 0, "supergroup": 0}
        for chat_type, count in result.all():
            counts[chat_type] = count
        return counts


class ButtonRepository:
    """CRUD operations for Button entities."""

    @staticmethod
    async def get_by_id(session: AsyncSession, button_id: int) -> Optional[Button]:
        stmt = select(Button).where(Button.id == button_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_for_destination(
        session: AsyncSession, destination_id: int, active_only: bool = False
    ) -> List[Button]:
        stmt = select(Button).where(Button.destination_id == destination_id)
        if active_only:
            stmt = stmt.where(Button.is_enabled.is_(True))
        stmt = stmt.order_by(Button.row_index.asc(), Button.sort_order.asc(), Button.id.asc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def list_default_templates(
        session: AsyncSession, active_only: bool = False
    ) -> List[Button]:
        stmt = select(Button).where(Button.destination_id.is_(None))
        if active_only:
            stmt = stmt.where(Button.is_enabled.is_(True))
        stmt = stmt.order_by(Button.row_index.asc(), Button.sort_order.asc(), Button.id.asc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create(
        session: AsyncSession,
        destination_id: Optional[int],
        label: str,
        url: str,
        emoji: str = "",
        is_enabled: bool = True,
        sort_order: int = 0,
        row_index: int = 0,
    ) -> Button:
        # Determine highest sort_order if not provided
        if sort_order == 0:
            subquery = select(func.coalesce(func.max(Button.sort_order), 0) + 1)
            if destination_id is None:
                subquery = subquery.where(Button.destination_id.is_(None))
            else:
                subquery = subquery.where(Button.destination_id == destination_id)
            result = await session.execute(subquery)
            sort_order = result.scalar_one()

        button = Button(
            destination_id=destination_id,
            label=label,
            emoji=emoji,
            url=url,
            is_enabled=is_enabled,
            sort_order=sort_order,
            row_index=row_index,
        )
        session.add(button)
        await session.flush()
        return button

    @staticmethod
    async def update(
        session: AsyncSession,
        button_id: int,
        **kwargs,
    ) -> Optional[Button]:
        button = await ButtonRepository.get_by_id(session, button_id)
        if not button:
            return None
        for key, value in kwargs.items():
            if hasattr(button, key):
                setattr(button, key, value)
        button.updated_at = datetime.now(timezone.utc)
        await session.flush()
        return button

    @staticmethod
    async def delete(session: AsyncSession, button_id: int) -> bool:
        button = await ButtonRepository.get_by_id(session, button_id)
        if not button:
            return False
        await session.delete(button)
        await session.flush()
        return True

    @staticmethod
    async def reorder_buttons(
        session: AsyncSession, button_ids: List[int]
    ) -> None:
        for idx, b_id in enumerate(button_ids):
            await session.execute(
                update(Button)
                .where(Button.id == b_id)
                .values(sort_order=idx + 1, updated_at=datetime.now(timezone.utc))
            )
        await session.flush()

    @staticmethod
    async def copy_default_templates(
        session: AsyncSession, destination_id: int
    ) -> List[Button]:
        """Copy all default template buttons to a new destination."""
        templates = await ButtonRepository.list_default_templates(session)
        created = []
        for t in templates:
            b = Button(
                destination_id=destination_id,
                label=t.label,
                emoji=t.emoji,
                url=t.url,
                is_enabled=t.is_enabled,
                sort_order=t.sort_order,
                row_index=t.row_index,
            )
            session.add(b)
            created.append(b)
        await session.flush()
        return created


class ProcessedPostRepository:
    """Idempotency repository for technical duplicate prevention."""

    @staticmethod
    async def is_processed(
        session: AsyncSession, destination_id: int, message_id: int
    ) -> bool:
        stmt = select(ProcessedPost.id).where(
            ProcessedPost.destination_id == destination_id,
            ProcessedPost.message_id == message_id,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def is_media_group_processed(
        session: AsyncSession, destination_id: int, media_group_id: str
    ) -> bool:
        if not media_group_id:
            return False
        stmt = select(ProcessedPost.id).where(
            ProcessedPost.destination_id == destination_id,
            ProcessedPost.media_group_id == media_group_id,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def record_post(
        session: AsyncSession,
        destination_id: int,
        message_id: int,
        media_group_id: Optional[str] = None,
        status: str = "SUCCESS",
    ) -> ProcessedPost:
        post = ProcessedPost(
            destination_id=destination_id,
            message_id=message_id,
            media_group_id=media_group_id,
            status=status,
        )
        session.add(post)
        await session.flush()
        return post

    @staticmethod
    async def get_last_processed(
        session: AsyncSession,
    ) -> Optional[ProcessedPost]:
        stmt = (
            select(ProcessedPost)
            .order_by(ProcessedPost.processed_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


class SettingRepository:
    """Global key-value settings storage."""

    @staticmethod
    async def get(
        session: AsyncSession, key: str, default: str = ""
    ) -> str:
        stmt = select(SystemSetting.value).where(SystemSetting.key == key)
        result = await session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if val is not None else default

    @staticmethod
    async def set(session: AsyncSession, key: str, value: str) -> None:
        stmt = select(SystemSetting).where(SystemSetting.key == key)
        result = await session.execute(stmt)
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = value
            setting.updated_at = datetime.now(timezone.utc)
        else:
            setting = SystemSetting(key=key, value=value)
            session.add(setting)
        await session.flush()
