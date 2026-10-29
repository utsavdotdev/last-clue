"""WebSocket room manager with per-player private projections and rate limiting."""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from typing import Any
from fastapi import WebSocket

from last_clue.ai.service import HauntedAIService
from last_clue.config import Settings
from last_clue.game_engine import GameEngine, GameRuleError, PlayerSession
from last_clue.hardware.matrix_adapter import MatrixAdapter
from last_clue.models import GhostMatrixState
from last_clue.networking import detect_lan_ips, generate_qr_svg, primary_join_url

logger = logging.getLogger(__name__)

MAX_INVALID_ACTIONS_PER_WINDOW = 10
RATE_LIMIT_WINDOW_SECONDS = 10.0


class RoomManager:
    """Coordinates a single active room on the UNO Q, managing WebSockets and timers."""

    def __init__(
        self,
        *,
        settings: Settings,
        matrix: MatrixAdapter,
        ai_service: HauntedAIService,
        room_code: str | None = None,
    ) -> None:
        code = room_code or self._generate_room_code()
        self.settings = settings
        self.matrix = matrix
        self.ai_service = ai_service
        self.engine = GameEngine(
            room_code=code,
            matrix=matrix,
            ai_service=ai_service,
            discussion_seconds=settings.discussion_seconds,
            voting_seconds=settings.voting_seconds,
            clue_timeout_seconds=settings.clue_timeout_seconds,
            final_guess_seconds=settings.final_guess_seconds,
        )
        self._lock = asyncio.Lock()
        self._player_sockets: dict[str, set[WebSocket]] = {}
        self._observer_sockets: set[WebSocket] = set()
        self._invalid_counts: dict[str, list[float]] = {}

    @staticmethod
    def _generate_room_code() -> str:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        rng = secrets.SystemRandom()
        return "".join(rng.choice(alphabet) for _ in range(6))

    def network_info(self) -> dict[str, Any]:
        ips = detect_lan_ips()
        join_url = primary_join_url(self.settings.port, self.engine.room_code)
        return {
            "room_code": self.engine.room_code,
            "port": self.settings.port,
            "lan_ips": ips,
            "join_url": join_url,
            "qr_svg": generate_qr_svg(join_url),
            "hardware_connected": self.matrix.hardware_connected,
        }

    async def register_socket(
        self,
        websocket: WebSocket,
        *,
        player_id: str | None = None,
        token: str | None = None,
    ) -> PlayerSession | None:
        async with self._lock:
            if player_id and token:
                player = self.engine.authenticate_player(player_id, token)
                player.connected = True
                self._player_sockets.setdefault(player_id, set()).add(websocket)
                return player
            self._observer_sockets.add(websocket)
            return None

    async def unregister_socket(self, websocket: WebSocket, player_id: str | None) -> None:
        should_broadcast = False
        async with self._lock:
            self._observer_sockets.discard(websocket)
            if player_id and player_id in self._player_sockets:
                sockets = self._player_sockets[player_id]
                sockets.discard(websocket)
                if not sockets:
                    del self._player_sockets[player_id]
                    self.engine.disconnect_player(player_id)
                    should_broadcast = True
        if should_broadcast:
            await self.broadcast_state()

    def _record_invalid_action(self, key: str) -> bool:
        """Return True if rate limit is exceeded."""
        now = time.monotonic()
        bucket = [t for t in self._invalid_counts.get(key, []) if now - t < RATE_LIMIT_WINDOW_SECONDS]
        bucket.append(now)
        self._invalid_counts[key] = bucket
        return len(bucket) > MAX_INVALID_ACTIONS_PER_WINDOW

    async def handle_client_message(
        self,
        websocket: WebSocket,
        player_id: str | None,
        token: str | None,
        raw_msg: Any,
    ) -> None:
        rate_key = player_id or str(id(websocket))
        if not isinstance(raw_msg, dict):
            await self._send_error(websocket, "Malformed message payload.")
            return

        action = str(raw_msg.get("type", "")).strip()
        if not action:
            await self._send_error(websocket, "Missing message action type.")
            return

        try:
            async with self._lock:
                await self._dispatch_action_locked(websocket, player_id, token, action, raw_msg)
            await self.broadcast_state()
        except GameRuleError as exc:
            exceeded = self._record_invalid_action(rate_key)
            msg = "Too many invalid actions. Slow down." if exceeded else str(exc)
            await self._send_error(websocket, msg)

    async def _dispatch_action_locked(
        self,
        websocket: WebSocket,
        player_id: str | None,
        token: str | None,
        action: str,
        payload: dict[str, Any],
    ) -> None:
        if action == "ping":
            await websocket.send_json({"type": "pong"})
            return

        if action == "start_round":
            self.engine.require_host(player_id=player_id, token=token)
            use_ai = bool(payload.get("use_ai_intro", self.ai_service.enabled))
            self.engine.start_round(use_ai_intro=use_ai)
            return

        if action == "acknowledge_role":
            if not player_id:
                raise GameRuleError("Authentication required.")
            self.engine.mark_role_acknowledged(player_id)
            return

        if action == "begin_clue_round":
            self.engine.require_host(player_id=player_id, token=token)
            self.engine.begin_clue_round()
            return

        if action == "submit_clue":
            if not player_id:
                raise GameRuleError("Authentication required.")
            clue_text = str(payload.get("clue", ""))
            self.engine.submit_clue(player_id, clue_text)
            return

        if action == "skip_speaker":
            self.engine.require_host(player_id=player_id, token=token)
            self.engine.skip_current_speaker()
            return

        if action == "begin_voting":
            self.engine.require_host(player_id=player_id, token=token)
            self.engine.begin_voting()
            return

        if action == "cast_vote":
            if not player_id:
                raise GameRuleError("Authentication required.")
            target_id = str(payload.get("target_id", "")).strip()
            self.engine.cast_vote(player_id, target_id)
            return

        if action == "finalize_voting":
            self.engine.require_host(player_id=player_id, token=token)
            self.engine.finalize_voting()
            return

        if action == "submit_final_guess":
            if not player_id:
                raise GameRuleError("Authentication required.")
            guess = str(payload.get("guess", ""))
            self.engine.submit_final_guess(player_id, guess)
            return

        if action == "play_again":
            self.engine.require_host(player_id=player_id, token=token)
            use_ai = bool(payload.get("use_ai_intro", self.ai_service.enabled))
            self.engine.start_round(use_ai_intro=use_ai)
            return

        if action == "return_to_lobby":
            self.engine.require_host(player_id=player_id, token=token)
            self.engine.return_to_lobby()
            return

        if action == "reset_scores":
            self.engine.require_host(player_id=player_id, token=token)
            self.engine.reset_scores()
            return

        if action == "update_settings":
            self.engine.require_host(player_id=player_id, token=token)
            self.engine.update_settings(
                selected_category=payload.get("selected_category"),
                discussion_seconds=(
                    int(payload["discussion_seconds"])
                    if payload.get("discussion_seconds") is not None
                    else None
                ),
                voting_seconds=(
                    int(payload["voting_seconds"])
                    if payload.get("voting_seconds") is not None
                    else None
                ),
                ai_enabled=(
                    bool(payload["ai_enabled"])
                    if payload.get("ai_enabled") is not None
                    else None
                ),
            )
            return

        if action == "test_matrix_state":
            self.engine.require_host(player_id=player_id, token=token)
            raw_state = str(payload.get("state", "IDLE")).upper()
            try:
                ghost_state = GhostMatrixState(raw_state)
            except ValueError as exc:
                raise GameRuleError(f"Unknown matrix state: {raw_state}") from exc
            self.matrix.set_state(ghost_state, force=True)
            return

        if action == "leave_room":
            if player_id:
                self.engine.leave_player(player_id)
            return

        raise GameRuleError(f"Unsupported action: {action}")

    async def broadcast_state(self) -> None:
        """Send public state to all sockets and tailored private state to each authenticated player."""
        async with self._lock:
            public_payload = self.engine.build_public_state().model_dump(mode="json")
            player_targets: list[tuple[WebSocket, dict[str, Any]]] = []
            for pid, sockets in list(self._player_sockets.items()):
                if pid not in self.engine.players:
                    continue
                private_payload = self.engine.build_private_payload(pid).model_dump(mode="json")
                envelope = {
                    "type": "state_sync",
                    "public": public_payload,
                    "private": private_payload,
                }
                for ws in list(sockets):
                    player_targets.append((ws, envelope))

            observer_envelope = {
                "type": "state_sync",
                "public": public_payload,
                "private": None,
            }
            observer_targets = [(ws, observer_envelope) for ws in list(self._observer_sockets)]

        for ws, message in player_targets + observer_targets:
            try:
                await ws.send_json(message)
            except Exception:
                pass

    async def _send_error(self, websocket: WebSocket, detail: str) -> None:
        try:
            await websocket.send_json({"type": "error", "message": detail})
        except Exception:
            pass

    async def tick_timers(self) -> None:
        """Periodic check to advance expired server timers and broadcast state."""
        changed = False
        async with self._lock:
            changed = self.engine.check_and_advance_expired_timer()
        if changed:
            await self.broadcast_state()
