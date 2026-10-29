"""Arduino App Lab entry point for the Linux MPU side of The Last Clue."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_PYTHON_ROOT = Path(__file__).resolve().parent
if str(_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYTHON_ROOT))

import uvicorn  # noqa: E402
from last_clue.app import create_app  # noqa: E402
from last_clue.config import load_settings  # noqa: E402
from last_clue.hardware.matrix_adapter import create_matrix_adapter  # noqa: E402
from last_clue.networking import detect_lan_ips, primary_join_url  # noqa: E402


def main() -> None:
    """Start The Last Clue multiplayer server on the Arduino UNO Q or macOS."""
    settings = load_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("last_clue.main")

    matrix = create_matrix_adapter()
    app = create_app(settings, matrix=matrix)
    room_code = app.state.room_manager.engine.room_code
    lan_ips = detect_lan_ips()
    join_url = primary_join_url(settings.port, room_code)

    logger.info("==========================================================")
    logger.info("THE LAST CLUE - Haunted Game Master for Arduino UNO Q")
    logger.info("Room Code       : %s", room_code)
    logger.info("Listening on    : http://%s:%d", settings.host, settings.port)
    logger.info("LAN Join URL    : %s", join_url)
    if lan_ips:
        logger.info("Detected LAN IPs: %s", ", ".join(lan_ips))
    else:
        logger.warning("No non-loopback LAN IP detected; using localhost.")
    logger.info(
        "8x13 LED Matrix : %s",
        "UNO Q Router Bridge Connected" if matrix.hardware_connected else "Simulated Mode",
    )
    logger.info("Local AI Model  : %s (%s)", settings.llm_model, settings.llm_url)
    logger.info("==========================================================")

    try:
        uvicorn.run(
            app,
            host=settings.host,
            port=settings.port,
            log_level=settings.log_level.lower(),
        )
    except OSError as exc:
        logger.error(
            "Could not bind to %s:%d (%s). Set LAST_CLUE_PORT to another port if %d is in use.",
            settings.host,
            settings.port,
            exc,
            settings.port,
        )
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
