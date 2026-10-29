"""macOS and Host Console simulator for the 8x13 LED Matrix."""

from __future__ import annotations

from last_clue.hardware.frames import COLS, ROWS, render_ghost_frame
from last_clue.models import GhostMatrixState


def format_ascii_matrix(state: GhostMatrixState, beat: int = 0) -> str:
    """Render an 8x13 ASCII frame for terminal diagnostics."""
    pixels = render_ghost_frame(state, beat=beat)
    lines: list[str] = []
    for row in range(ROWS):
        row_chars = "".join(
            "#" if pixels[row * COLS + col] else "." for col in range(COLS)
        )
        lines.append(row_chars)
    return "\n".join(lines)
