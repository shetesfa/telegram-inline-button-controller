"""Tests for data persistence across application restarts."""

import os
import tempfile
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.database import database
from app.database.models import Base
from app.services.button_service import ButtonService
from app.services.destination_service import DestinationService
from app.services.system_service import SystemService


@pytest.mark.asyncio
async def test_database_persistence_across_restart():
    """Verify saved channels, buttons, and settings persist after session/engine restarts."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        db_path = tmp_db.name

    db_url = f"sqlite+aiosqlite:///{db_path}"

    # Phase 1: Initialize DB, save destination, buttons, and settings
    engine1 = create_async_engine(db_url, echo=False, future=True)
    sm1 = async_sessionmaker(bind=engine1, class_=AsyncSession, expire_on_commit=False)
    database._engine = engine1
    database._sessionmaker = sm1

    async with engine1.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Save data
    dest, _ = await DestinationService.add_destination(
        chat_id=-1001234567,
        title="Persistent Channel",
        chat_type="channel",
        username="@persistchan",
        use_default_buttons=False,
    )
    btn, _ = await ButtonService.add_button(
        dest.id, "Website", "https://persist.example.com", emoji="🌐"
    )
    await SystemService.set_global_automation(False)

    # Phase 2: Simulate complete shutdown
    await engine1.dispose()
    database._engine = None
    database._sessionmaker = None

    # Phase 3: Simulate restart
    engine2 = create_async_engine(db_url, echo=False, future=True)
    sm2 = async_sessionmaker(bind=engine2, class_=AsyncSession, expire_on_commit=False)
    database._engine = engine2
    database._sessionmaker = sm2

    # Verify data reloaded accurately
    reloaded_dest = await DestinationService.get_by_chat_id(-1001234567)
    assert reloaded_dest is not None
    assert reloaded_dest.title == "Persistent Channel"
    assert reloaded_dest.username == "@persistchan"

    reloaded_buttons = await ButtonService.list_for_destination(reloaded_dest.id)
    assert len(reloaded_buttons) == 1
    assert reloaded_buttons[0].display_text == "🌐 Website"
    assert reloaded_buttons[0].url == "https://persist.example.com"

    auto_state = await SystemService.is_global_automation_enabled()
    assert auto_state is False

    await engine2.dispose()
    database._engine = None
    database._sessionmaker = None

    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass
