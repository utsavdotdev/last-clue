"""Unified MatrixAdapter driving both UNO Q hardware and the simulated display."""

from __future__ import annotations

import threading
import time
from last_clue.hardware.frames import (
    GHOST_STATE_CODES,
    STATE_LABELS,
    render_ghost_frame,
)
from last_clue.hardware.uno_q_matrix import UnoQBridgeClient, open_uno_q_bridge
from last_clue.models import GhostMatrixState, MatrixPreviewView


class MatrixAdapter:
    """Tracks the current ghost expression and dispatches updates to hardware + simulator."""

    def __init__(self, bridge: UnoQBridgeClient | None = None, *, sync_mode: bool = False) -> None:
        self._lock = threading.Lock()
        self._bridge = bridge
        self._sync_mode = sync_mode
        self._state: GhostMatrixState = GhostMatrixState.BOOT
        self._generation: int = 1
        self._updated_at: float = time.monotonic()
        self._history: list[tuple[GhostMatrixState, int]] = [(self._state, self._generation)]
        self._dispatch(self._state, self._generation)

    @property
    def hardware_connected(self) -> bool:
        return self._bridge is not None

    @property
    def state(self) -> GhostMatrixState:
        with self._lock:
            return self._state

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    @property
    def history(self) -> list[tuple[GhostMatrixState, int]]:
        with self._lock:
            return list(self._history)

    def set_state(self, state: GhostMatrixState, *, force: bool = False) -> MatrixPreviewView:
        """Transition the LED matrix ghost expression and notify the STM32 bridge."""
        with self._lock:
            if state == self._state and not force:
                return self._snapshot_locked()
            self._state = state
            self._generation += 1
            self._updated_at = time.monotonic()
            self._history.append((self._state, self._generation))
            gen = self._generation
            snapshot = self._snapshot_locked()

        self._dispatch(state, gen)
        return snapshot

    def snapshot(self) -> MatrixPreviewView:
        with self._lock:
            return self._snapshot_locked()

    def _snapshot_locked(self) -> MatrixPreviewView:
        elapsed_beats = int((time.monotonic() - self._updated_at) / 0.45)
        code = GHOST_STATE_CODES[self._state]
        mode_prefix = "UNO Q 8x13 MATRIX" if self.hardware_connected else "SIMULATED 8x13 MATRIX"
        return MatrixPreviewView(
            state=self._state,
            state_code=code,
            generation=self._generation,
            hardware_connected=self.hardware_connected,
            label=f"{mode_prefix}: {STATE_LABELS[self._state]}",
            pixels=render_ghost_frame(self._state, beat=elapsed_beats),
        )

    def _dispatch(self, state: GhostMatrixState, generation: int) -> None:
        if self._bridge is None:
            return
        code = GHOST_STATE_CODES[state]
        if self._sync_mode:
            self._bridge.send_state_sync(code, generation)
        else:
            self._bridge.send_state(code, generation)


def create_matrix_adapter() -> MatrixAdapter:
    """Create the default MatrixAdapter, connecting to UNO Q Bridge if present."""
    bridge = open_uno_q_bridge()
    return MatrixAdapter(bridge=bridge)
