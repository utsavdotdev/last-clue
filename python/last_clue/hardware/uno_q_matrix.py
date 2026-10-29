"""Arduino UNO Q Router Bridge implementation for the 8x13 LED Matrix."""

from __future__ import annotations

import logging
import queue
import threading

logger = logging.getLogger(__name__)


class UnoQBridgeClient:
    """Non-blocking wrapper around arduino.app_utils.Bridge."""

    def __init__(self, call_fn: object | None = None) -> None:
        if call_fn is not None:
            self._call = call_fn
        else:
            from arduino.app_utils import Bridge  # type: ignore[import-not-found]

            self._call = Bridge.call
        self._queue: queue.Queue[tuple[int, int]] = queue.Queue(maxsize=32)
        self._worker = threading.Thread(
            target=self._run_loop,
            name="last-clue-matrix-bridge",
            daemon=True,
        )
        self._worker.start()

    def send_state(self, state_code: int, generation: int) -> None:
        """Enqueue a state update without blocking the FastAPI event loop."""
        try:
            while self._queue.full():
                self._queue.get_nowait()
            self._queue.put_nowait((state_code, generation))
        except queue.Full:
            pass

    def send_state_sync(self, state_code: int, generation: int) -> None:
        """Directly invoke the RPC call (used in deterministic unit tests)."""
        self._call("set_ghost_state", int(state_code), int(generation))

    def _run_loop(self) -> None:
        while True:
            state_code, generation = self._queue.get()
            try:
                self._call("set_ghost_state", int(state_code), int(generation))
            except Exception:
                logger.warning(
                    "UNO Q Bridge matrix RPC failed for state=%s gen=%s",
                    state_code,
                    generation,
                    exc_info=True,
                )


def open_uno_q_bridge() -> UnoQBridgeClient | None:
    """Attempt to initialize the Arduino Router Bridge on UNO Q Linux MPU."""
    try:
        client = UnoQBridgeClient()
        logger.info("Connected to Arduino UNO Q Router Bridge for 8x13 LED matrix.")
        return client
    except ImportError:
        logger.info("Arduino Router Bridge not detected; using simulated 8x13 LED matrix.")
        return None
    except Exception:
        logger.warning("Failed to open Arduino Router Bridge; falling back to simulator.", exc_info=True)
        return None
