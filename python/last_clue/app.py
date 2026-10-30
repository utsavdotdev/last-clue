"""FastAPI application factory, REST endpoints, QR endpoints, WebSocket handler, and static file serving."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from last_clue.ai.service import HauntedAIService
from last_clue.config import Settings, load_settings
from last_clue.game_engine import GameRuleError
from last_clue.hardware.matrix_adapter import MatrixAdapter, create_matrix_adapter
from last_clue.models import (
    GhostMatrixState,
    HostSettingsUpdate,
    JoinRoomRequest,
    JoinRoomResponse,
)
from last_clue.networking import (
    generate_qr_png,
    generate_qr_svg,
    primary_join_url,
    resolve_join_url,
)
from last_clue.room_manager import RoomManager

logger = logging.getLogger(__name__)


def _request_host_header(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-host")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.headers.get("host")


def create_app(
    settings: Settings | None = None,
    *,
    matrix: MatrixAdapter | None = None,
    ai_service: HauntedAIService | None = None,
    room_code: str | None = None,
) -> FastAPI:
    """Create the FastAPI application for The Last Clue."""
    resolved_settings = settings if settings is not None else load_settings()
    resolved_matrix = matrix if matrix is not None else create_matrix_adapter()
    resolved_ai = (
        ai_service
        if ai_service is not None
        else HauntedAIService(
            llm_url=resolved_settings.llm_url,
            llm_model=resolved_settings.llm_model,
            timeout_seconds=resolved_settings.llm_timeout_seconds,
            enabled=resolved_settings.ai_enabled,
            hardware_connected=resolved_matrix.hardware_connected,
        )
    )
    manager = RoomManager(
        settings=resolved_settings,
        matrix=resolved_matrix,
        ai_service=resolved_ai,
        room_code=room_code,
    )

    app = FastAPI(
        title="The Last Clue",
        description="Haunted LAN Multiplayer Social-Deduction Game for Arduino UNO Q",
        version="1.0.0",
    )
    app.state.settings = resolved_settings
    app.state.matrix = resolved_matrix
    app.state.ai_service = resolved_ai
    app.state.room_manager = manager

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "room_code": manager.engine.room_code,
            "phase": manager.engine.phase,
            "hardware_connected": resolved_matrix.hardware_connected,
            "ai_status": resolved_ai.status_view().model_dump(mode="json"),
        }

    @app.get("/api/network")
    async def get_network_info(
        request: Request,
        host: str | None = Query(default=None),
        room: str | None = Query(default=None),
    ) -> dict[str, Any]:
        req_host = _request_host_header(request)
        return manager.network_info(
            request_host=req_host,
            preferred_host=host,
            room_code=room,
        )

    @app.get("/api/qr.png")
    async def get_qr_png(
        request: Request,
        room: str | None = Query(default=None),
        host: str | None = Query(default=None),
    ) -> Response:
        target_room = (room or manager.engine.room_code).strip().upper()
        req_host = _request_host_header(request)
        join_url, reachable, _ = resolve_join_url(
            resolved_settings.port,
            target_room,
            request_host=req_host,
            preferred_host=host,
        )
        png_bytes = generate_qr_png(join_url)
        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "X-Join-Url": join_url,
                "X-Room-Code": target_room,
                "X-Network-Reachable": "true" if reachable else "false",
            },
        )

    @app.get("/api/qr.svg")
    async def get_qr_svg(
        request: Request,
        room: str | None = Query(default=None),
        host: str | None = Query(default=None),
    ) -> Response:
        target_room = (room or manager.engine.room_code).strip().upper()
        req_host = _request_host_header(request)
        join_url, reachable, _ = resolve_join_url(
            resolved_settings.port,
            target_room,
            request_host=req_host,
            preferred_host=host,
        )
        svg_text = generate_qr_svg(join_url)
        return Response(
            content=svg_text,
            media_type="image/svg+xml",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "X-Join-Url": join_url,
                "X-Room-Code": target_room,
                "X-Network-Reachable": "true" if reachable else "false",
            },
        )

    @app.post("/api/room/new")
    async def create_new_room(
        request: Request,
        room_code: str | None = Query(default=None),
        host: str | None = Query(default=None),
    ) -> dict[str, Any]:
        async with manager._lock:
            new_code = manager.create_new_room_locked(custom_code=room_code)
        await manager.broadcast_state()
        req_host = _request_host_header(request)
        return manager.network_info(
            request_host=req_host,
            preferred_host=host,
            room_code=new_code,
        )

    @app.get("/api/state")
    async def get_public_state(
        player_id: str | None = Query(default=None),
        token: str | None = Query(default=None),
    ) -> dict[str, Any]:
        async with manager._lock:
            public = manager.engine.build_public_state().model_dump(mode="json")
            private = None
            if player_id and token:
                try:
                    manager.engine.authenticate_player(player_id, token)
                    private = manager.engine.build_private_payload(player_id).model_dump(mode="json")
                except GameRuleError:
                    private = None
            return {"public": public, "private": private}

    @app.post("/api/join", response_model=JoinRoomResponse)
    async def join_room(req: JoinRoomRequest, request: Request) -> JoinRoomResponse:
        try:
            async with manager._lock:
                if req.as_host and req.create_new_room:
                    manager.create_new_room_locked(custom_code=req.room_code)
                elif (
                    req.room_code
                    and req.room_code.strip().upper() != manager.engine.room_code
                ):
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Room code '{req.room_code.strip().upper()}' does not match "
                            f"active room '{manager.engine.room_code}'."
                        ),
                    )
                session = manager.engine.join_player(
                    req.nickname,
                    reconnect_token=req.reconnect_token,
                    as_host=req.as_host,
                )
                active_code = manager.engine.room_code
            await manager.broadcast_state()
        except GameRuleError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        req_host = _request_host_header(request)
        join_url = primary_join_url(
            resolved_settings.port,
            active_code,
            request_host=req_host,
        )
        return JoinRoomResponse(
            player_id=session.player_id,
            nickname=session.nickname,
            room_code=active_code,
            reconnect_token=session.reconnect_token,
            is_host=session.is_host,
            join_url=join_url,
        )

    @app.post("/api/host/settings")
    async def update_host_settings(
        update: HostSettingsUpdate,
        player_id: str | None = Query(default=None),
        token: str | None = Query(default=None),
    ) -> dict[str, Any]:
        try:
            async with manager._lock:
                manager.engine.require_host(player_id=player_id, token=token)
                manager.engine.update_settings(
                    selected_category=update.selected_category,
                    ai_enabled=update.ai_enabled,
                )
            await manager.broadcast_state()
            return {"ok": True}
        except GameRuleError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @app.post("/api/host/ai/generate-words")
    async def generate_ai_words(
        category: str = Query(default="Haunted Relics"),
        player_id: str | None = Query(default=None),
        token: str | None = Query(default=None),
    ) -> dict[str, Any]:
        try:
            async with manager._lock:
                manager.engine.require_host(player_id=player_id, token=token)
            entries = await asyncio.to_thread(
                resolved_ai.generate_custom_words,
                category,
                3,
            )
            await manager.broadcast_state()
            return {
                "ok": True,
                "generated": [e.model_dump(mode="json") for e in entries],
            }
        except GameRuleError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except Exception as exc:
            await manager.broadcast_state()
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/host/matrix/{state_name}")
    async def trigger_matrix_state(
        state_name: str,
        player_id: str | None = Query(default=None),
        token: str | None = Query(default=None),
    ) -> dict[str, Any]:
        try:
            async with manager._lock:
                manager.engine.require_host(player_id=player_id, token=token)
                try:
                    ghost_state = GhostMatrixState(state_name.upper())
                except ValueError as exc:
                    raise GameRuleError(f"Unknown ghost matrix state: {state_name}") from exc
                snapshot = resolved_matrix.set_state(ghost_state, force=True)
            await manager.broadcast_state()
            return {"ok": True, "matrix": snapshot.model_dump(mode="json")}
        except GameRuleError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.websocket("/ws")
    async def websocket_endpoint(
        websocket: WebSocket,
        player_id: str | None = Query(default=None),
        token: str | None = Query(default=None),
    ) -> None:
        await websocket.accept()
        try:
            await manager.register_socket(websocket, player_id=player_id, token=token)
        except GameRuleError as exc:
            await websocket.send_json({"type": "error", "message": str(exc)})
            await websocket.close(code=4001)
            return

        await manager.broadcast_state()
        try:
            while True:
                raw_text = await websocket.receive_text()
                try:
                    data = json.loads(raw_text)
                except json.JSONDecodeError:
                    await websocket.send_json(
                        {"type": "error", "message": "Invalid JSON message."}
                    )
                    continue
                await manager.handle_client_message(websocket, player_id, token, data)
        except WebSocketDisconnect:
            pass
        finally:
            await manager.unregister_socket(websocket, player_id)

    static_dir: Path = resolved_settings.static_dir
    assets_dir = static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/", response_model=None)
    async def serve_index():
        index_file = static_dir / "index.html"
        if index_file.is_file():
            return FileResponse(index_file)
        return HTMLResponse(
            content=(
                "<!doctype html><html><head><meta charset='utf-8'>"
                "<title>The Last Clue</title></head>"
                "<body style='background:#f9fafb;color:#00142f;font-family:sans-serif;padding:2rem;'>"
                "<h1>The Last Clue Server Active</h1>"
                "<p>Run <code>./scripts/build.sh</code> to compile the frontend bundle.</p>"
                "</body></html>"
            )
        )

    @app.get("/{full_path:path}", response_model=None)
    async def serve_spa_fallback(full_path: str):
        if full_path.startswith("api/") or full_path == "ws":
            return JSONResponse({"detail": "Not found"}, status_code=404)
        candidate = (static_dir / full_path).resolve()
        if str(candidate).startswith(str(static_dir.resolve())) and candidate.is_file():
            return FileResponse(candidate)
        index_file = static_dir / "index.html"
        if index_file.is_file():
            return FileResponse(index_file)
        return JSONResponse({"detail": "Frontend asset not found"}, status_code=404)

    return app
