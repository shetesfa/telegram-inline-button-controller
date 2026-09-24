"""Service layer for post processing validation, duplicate protection, and album handling."""

import asyncio
from collections import OrderedDict
from typing import Optional, Tuple
from app.database.database import get_session
from app.database.repository import ProcessedPostRepository
from app.utils.logging import logger


class LRUCache:
    """Thread-safe fast in-memory LRU cache to quickly filter duplicate updates."""

    def __init__(self, capacity: int = 1000):
        self.capacity = capacity
        self.cache: OrderedDict[str, bool] = OrderedDict()
        self._lock = asyncio.Lock()

    async def contains_or_add(self, key: str) -> bool:
        """Check if key exists. If exists, return True. If not, add key and return False."""
        async with self._lock:
            if key in self.cache:
                self.cache.move_to_end(key)
                return True
            self.cache[key] = True
            if len(self.cache) > self.capacity:
                self.cache.popitem(last=False)
            return False


class PostService:
    """Business logic for duplicate protection, album deduplication, and post recording."""

    _memory_cache = LRUCache(capacity=2000)
    _album_lock = asyncio.Lock()
    _processed_albums = LRUCache(capacity=500)

    @classmethod
    async def should_process(
        cls,
        destination_id: int,
        message_id: int,
        media_group_id: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Determine if this message update should be processed.
        Returns (should_process: bool, reason: str).
        """
        post_key = f"{destination_id}:{message_id}"

        # 1. Fast in-memory check
        if await cls._memory_cache.contains_or_add(post_key):
            return False, "Duplicate update in-memory"

        # 2. Check media group / album deduplication
        if media_group_id:
            album_key = f"{destination_id}:album:{media_group_id}"
            if await cls._processed_albums.contains_or_add(album_key):
                # Another item in this media group already received the keyboard
                return False, f"Media group {media_group_id} already has a keyboard attached"

        # 3. Check persistent database
        async with get_session() as session:
            if await ProcessedPostRepository.is_processed(
                session, destination_id, message_id
            ):
                return False, "Post already recorded in database"

            if media_group_id:
                if await ProcessedPostRepository.is_media_group_processed(
                    session, destination_id, media_group_id
                ):
                    return False, f"Media group {media_group_id} already recorded in database"

        return True, "Eligible for processing"

    @classmethod
    async def record_result(
        cls,
        destination_id: int,
        message_id: int,
        media_group_id: Optional[str] = None,
        status: str = "SUCCESS",
    ) -> None:
        """Record the post processing outcome to prevent duplicate runs."""
        async with get_session() as session:
            try:
                await ProcessedPostRepository.record_post(
                    session=session,
                    destination_id=destination_id,
                    message_id=message_id,
                    media_group_id=media_group_id,
                    status=status,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to write processed post log ({destination_id}:{message_id}): {e}"
                )

    @classmethod
    async def get_last_processed_info(cls) -> Optional[dict]:
        """Fetch the most recent processed post metadata."""
        async with get_session() as session:
            last = await ProcessedPostRepository.get_last_processed(session)
            if not last:
                return None
            return {
                "destination_id": last.destination_id,
                "message_id": last.message_id,
                "media_group_id": last.media_group_id,
                "processed_at": last.processed_at,
                "status": last.status,
            }
