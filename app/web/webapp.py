"""aiohttp Web server and REST API for Telegram Mini App."""

import json
from pathlib import Path
from aiohttp import web
from app.config import config
from app.services.destination_service import DestinationService
from app.services.button_service import ButtonService
from app.services.system_service import SystemService
from app.utils.logging import logger
from app.database.database import get_session
from app.database.repository import ButtonRepository

STATIC_DIR = Path(__file__).parent / "static"
INDEX_HTML = STATIC_DIR / "index.html"


def cors_headers(response: web.Response) -> web.Response:
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response


async def handle_options(request: web.Request) -> web.Response:
    return cors_headers(web.Response(status=200))


async def handle_health(request: web.Request) -> web.Response:
    """Render health check endpoint."""
    return web.Response(text="OK", content_type="text/plain")


async def handle_webapp(request: web.Request) -> web.Response:
    """Serve the Mini App Single Page Application HTML."""
    if INDEX_HTML.exists():
        content = INDEX_HTML.read_text(encoding="utf-8")
        return web.Response(text=content, content_type="text/html")
    return web.Response(text="<h1>Mini App Loading...</h1>", content_type="text/html")


async def handle_status(request: web.Request) -> web.Response:
    """Return JSON system status."""
    counts = await DestinationService.get_summary_counts()
    global_auto = await SystemService.is_global_automation_enabled()
    data = {
        "status": "online",
        "env": config.APP_ENV,
        "master_automation": global_auto,
        "total_channels": counts.get("channel", 0),
        "total_groups": counts.get("group", 0) + counts.get("supergroup", 0),
    }
    return cors_headers(web.json_response(data))


async def handle_list_channels(request: web.Request) -> web.Response:
    """List all configured channels and groups."""
    channels = await DestinationService.list_channels()
    result = []
    for c in channels:
        btns = await ButtonService.list_for_destination(c.id)
        result.append({
            "id": c.id,
            "title": c.title,
            "username": c.username,
            "chat_id": c.telegram_chat_id,
            "chat_type": c.chat_type,
            "is_enabled": c.is_enabled,
            "automation_enabled": c.automation_enabled,
            "layout_mode": c.layout_mode,
            "button_count": len(btns),
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return cors_headers(web.json_response(result))


async def handle_toggle_channel(request: web.Request) -> web.Response:
    """Toggle channel is_enabled, automation_enabled, or layout."""
    dest_id = int(request.match_info["id"])
    try:
        body = await request.json()
    except Exception:
        body = {}
    
    target = body.get("target", "automation")
    if target == "automation":
        new_val = await DestinationService.toggle_automation(dest_id)
        return cors_headers(web.json_response({"success": True, "automation_enabled": new_val}))
    elif target == "enabled":
        new_val = await DestinationService.toggle_enabled(dest_id)
        return cors_headers(web.json_response({"success": True, "is_enabled": new_val}))
    elif target == "layout":
        mode = body.get("mode", "vertical")
        await DestinationService.set_layout_mode(dest_id, mode)
        return cors_headers(web.json_response({"success": True, "layout_mode": mode}))
    return cors_headers(web.json_response({"error": "Invalid target"}, status=400))


async def handle_list_buttons(request: web.Request) -> web.Response:
    """List buttons for a destination."""
    dest_id = int(request.match_info["id"])
    buttons = await ButtonService.list_for_destination(dest_id)
    result = [
        {
            "id": b.id,
            "destination_id": b.destination_id,
            "display_text": b.display_text,
            "label": b.label,
            "emoji": b.emoji or "",
            "url": b.url,
            "is_enabled": b.is_enabled,
            "sort_order": b.sort_order,
        }
        for b in buttons
    ]
    return cors_headers(web.json_response(result))


async def handle_add_button(request: web.Request) -> web.Response:
    """Add a new button for a destination."""
    dest_id = int(request.match_info["id"])
    data = await request.json()
    label = data.get("label", "").strip()
    url = data.get("url", "").strip()
    emoji = data.get("emoji", "").strip()
    is_enabled = bool(data.get("is_enabled", True))

    btn, err = await ButtonService.add_button(
        destination_id=dest_id,
        label=label,
        url=url,
        emoji=emoji,
        is_enabled=is_enabled,
    )
    if err:
        return cors_headers(web.json_response({"error": err}, status=400))
    return cors_headers(web.json_response({
        "success": True,
        "button": {
            "id": btn.id,
            "label": btn.label,
            "emoji": btn.emoji,
            "display_text": btn.display_text,
            "url": btn.url,
            "is_enabled": btn.is_enabled,
            "sort_order": btn.sort_order,
        }
    }))


async def handle_update_button(request: web.Request) -> web.Response:
    """Update an existing button."""
    btn_id = int(request.match_info["id"])
    data = await request.json()
    btn, err = await ButtonService.update_button(
        button_id=btn_id,
        label=data.get("label"),
        url=data.get("url"),
        emoji=data.get("emoji"),
        is_enabled=data.get("is_enabled"),
    )
    if err:
        return cors_headers(web.json_response({"error": err}, status=400))
    return cors_headers(web.json_response({"success": True}))


async def handle_delete_button(request: web.Request) -> web.Response:
    """Delete a single button."""
    btn_id = int(request.match_info["id"])
    success = await ButtonService.delete_button(btn_id)
    return cors_headers(web.json_response({"success": success}))


async def handle_reorder_buttons(request: web.Request) -> web.Response:
    """Reorder buttons using an ordered array of button IDs."""
    data = await request.json()
    button_ids = data.get("button_ids", [])
    if button_ids:
        async with get_session() as session:
            await ButtonRepository.reorder_buttons(session, button_ids)
    return cors_headers(web.json_response({"success": True}))


async def handle_clear_buttons(request: web.Request) -> web.Response:
    """Clear all buttons for a destination."""
    dest_id = int(request.match_info["id"])
    await DestinationService.reset_buttons(dest_id, load_defaults=False)
    return cors_headers(web.json_response({"success": True}))


def create_web_app() -> web.Application:
    """Build and configure the aiohttp web application."""
    app = web.Application()

    # Static / HTML
    app.router.add_get("/", handle_webapp)
    app.router.add_get("/webapp", handle_webapp)
    app.router.add_get("/health", handle_health)

    # API Routes
    app.router.add_get("/api/status", handle_status)
    app.router.add_get("/api/channels", handle_list_channels)
    app.router.add_post("/api/channels/{id}/toggle", handle_toggle_channel)
    app.router.add_get("/api/channels/{id}/buttons", handle_list_buttons)
    app.router.add_post("/api/channels/{id}/buttons", handle_add_button)
    app.router.add_put("/api/buttons/{id}", handle_update_button)
    app.router.add_delete("/api/buttons/{id}", handle_delete_button)
    app.router.add_post("/api/channels/{id}/buttons/reorder", handle_reorder_buttons)
    app.router.add_post("/api/channels/{id}/buttons/clear", handle_clear_buttons)

    # CORS Options
    app.router.add_route("OPTIONS", "/{tail:.*}", handle_options)

    return app
