"""8x13 LED Matrix pixel-art sprites and frame calculations for The Last Clue.

The Arduino UNO Q built-in LED matrix is 8 rows by 13 columns (104 LEDs).
Each row mask is a 13-bit integer where bit 0 is column 0 and bit 12 is column 12.
The exact same masks are compiled into sketch/sketch.ino for the STM32 MCU.
"""

from __future__ import annotations

from last_clue.models import GhostMatrixState

ROWS = 8
COLS = 13
FRAME_LENGTH = ROWS * COLS
MASK_MAX = (1 << COLS) - 1

GHOST_STATE_CODES: dict[GhostMatrixState, int] = {
    GhostMatrixState.BOOT: 1,
    GhostMatrixState.LOBBY: 2,
    GhostMatrixState.ROLES_ASSIGNED: 3,
    GhostMatrixState.CLUE_PHASE: 4,
    GhostMatrixState.VOTING_PHASE: 5,
    GhostMatrixState.RUNOFF: 6,
    GhostMatrixState.IMPOSTER_DISCOVERED: 7,
    GhostMatrixState.SURVIVORS_WIN: 8,
    GhostMatrixState.IMPOSTER_WINS: 9,
    GhostMatrixState.IDLE: 10,
}

CODE_TO_GHOST_STATE: dict[int, GhostMatrixState] = {
    code: state for state, code in GHOST_STATE_CODES.items()
}

STATE_LABELS: dict[GhostMatrixState, str] = {
    GhostMatrixState.BOOT: "Ghost materializing on boot",
    GhostMatrixState.LOBBY: "Calm floating ghost in lobby",
    GhostMatrixState.ROLES_ASSIGNED: "Suspenseful role assignment pulse",
    GhostMatrixState.CLUE_PHASE: "Curious ghost listening to clues",
    GhostMatrixState.VOTING_PHASE: "Flashing suspicious eyes during vote",
    GhostMatrixState.RUNOFF: "Rapidly blinking runoff ghost",
    GhostMatrixState.IMPOSTER_DISCOVERED: "Angry ghost: Imposter caught",
    GhostMatrixState.SURVIVORS_WIN: "Defeated dissolving ghost: Survivors win",
    GhostMatrixState.IMPOSTER_WINS: "Evil victorious ghost: Imposter wins",
    GhostMatrixState.IDLE: "Subtle idle breathing ghost",
}


def _rows_from_ascii(art: tuple[str, ...]) -> tuple[int, ...]:
    """Convert an 8-row by 13-col ASCII grid ('#' lit, '.' off) into 8 13-bit masks."""
    if len(art) != ROWS:
        raise ValueError(f"Expected {ROWS} rows, got {len(art)}")
    masks: list[int] = []
    for row_str in art:
        if len(row_str) != COLS:
            raise ValueError(f"Expected {COLS} columns, got {len(row_str)} in {row_str!r}")
        mask = 0
        for col, ch in enumerate(row_str):
            if ch != ".":
                mask |= 1 << col
        masks.append(mask)
    return tuple(masks)


# 8x13 Pixel-Art Ghost Sprites (centered around columns 3..9)
SPRITE_CALM_A = _rows_from_ascii(
    (
        "....#####....",
        "...#######...",
        "..##.#.#.##..",
        "..#########..",
        "..#########..",
        "..#########..",
        "..##.###.##..",
        "..#...#...#..",
    )
)

SPRITE_CALM_B = _rows_from_ascii(
    (
        ".............",
        "....#####....",
        "...#######...",
        "..##.#.#.##..",
        "..#########..",
        "..#########..",
        "..###.#.###..",
        "...#.....#...",
    )
)

SPRITE_BOOT_A = _rows_from_ascii(
    (
        ".............",
        ".....###.....",
        "....#.#.#....",
        "....#####....",
        ".....###.....",
        "......#......",
        ".............",
        ".............",
    )
)

SPRITE_ROLES_PULSE = _rows_from_ascii(
    (
        "#...#####...#",
        "...#######...",
        "..#..#.#..#..",
        "..#########..",
        "..###.#.###..",
        "..#########..",
        "..#.#.#.#.#..",
        "#...........#",
    )
)

SPRITE_CLUE_CURIOUS = _rows_from_ascii(
    (
        "....#####..##",
        "...#######..#",
        "..###.#..##..",
        "..#########..",
        "..#########.#",
        "..#########..",
        "..##.###.##..",
        "...#..#..#...",
    )
)

SPRITE_VOTING_EYES_LEFT = _rows_from_ascii(
    (
        ".............",
        "..####.####..",
        ".##..#.##..#.",
        ".##..#.##..#.",
        "..####.####..",
        ".............",
        "....#####....",
        ".............",
    )
)

SPRITE_VOTING_EYES_RIGHT = _rows_from_ascii(
    (
        ".............",
        "..####.####..",
        ".#..##.#..##.",
        ".#..##.#..##.",
        "..####.####..",
        ".............",
        "....#####....",
        ".............",
    )
)

SPRITE_RUNOFF_ALERT = _rows_from_ascii(
    (
        "#...#####...#",
        "#..#######..#",
        "..#.#...#.#..",
        "..#########..",
        "..###...###..",
        "..#########..",
        "#.#..###..#.#",
        "#..#.....#..#",
    )
)

SPRITE_ANGRY_GHOST = _rows_from_ascii(
    (
        "..#..###..#..",
        "...#######...",
        "..##.#.#.##..",
        "..###...###..",
        "..#########..",
        "..##.#.#.##..",
        "..#########..",
        "..#.#.#.#.#..",
    )
)

SPRITE_DEFEATED_GHOST = _rows_from_ascii(
    (
        ".............",
        ".............",
        ".............",
        "....#####....",
        "...#.#.#.#...",
        "..#########..",
        ".###########.",
        "##.#.###.#.##",
    )
)

SPRITE_EVIL_VICTORY = _rows_from_ascii(
    (
        ".#..#####..#.",
        "..#########..",
        ".###.#.#.###.",
        ".###########.",
        ".##.#.#.#.##.",
        ".###.#.#.###.",
        "..#########..",
        ".#..#...#..#.",
    )
)

SPRITE_IDLE = _rows_from_ascii(
    (
        ".............",
        "....#####....",
        "...#######...",
        "..##.#.#.##..",
        "..#########..",
        "..#########..",
        "..##.###.##..",
        "..#...#...#..",
    )
)

STATE_PRIMARY_SPRITES: dict[GhostMatrixState, tuple[int, ...]] = {
    GhostMatrixState.BOOT: SPRITE_BOOT_A,
    GhostMatrixState.LOBBY: SPRITE_CALM_A,
    GhostMatrixState.ROLES_ASSIGNED: SPRITE_ROLES_PULSE,
    GhostMatrixState.CLUE_PHASE: SPRITE_CLUE_CURIOUS,
    GhostMatrixState.VOTING_PHASE: SPRITE_VOTING_EYES_LEFT,
    GhostMatrixState.RUNOFF: SPRITE_RUNOFF_ALERT,
    GhostMatrixState.IMPOSTER_DISCOVERED: SPRITE_ANGRY_GHOST,
    GhostMatrixState.SURVIVORS_WIN: SPRITE_DEFEATED_GHOST,
    GhostMatrixState.IMPOSTER_WINS: SPRITE_EVIL_VICTORY,
    GhostMatrixState.IDLE: SPRITE_IDLE,
}

STATE_SECONDARY_SPRITES: dict[GhostMatrixState, tuple[int, ...]] = {
    GhostMatrixState.BOOT: SPRITE_CALM_A,
    GhostMatrixState.LOBBY: SPRITE_CALM_B,
    GhostMatrixState.ROLES_ASSIGNED: SPRITE_CALM_A,
    GhostMatrixState.CLUE_PHASE: SPRITE_CALM_A,
    GhostMatrixState.VOTING_PHASE: SPRITE_VOTING_EYES_RIGHT,
    GhostMatrixState.RUNOFF: (0, 0, 0, 0, 0, 0, 0, 0),
    GhostMatrixState.IMPOSTER_DISCOVERED: SPRITE_ROLES_PULSE,
    GhostMatrixState.SURVIVORS_WIN: SPRITE_BOOT_A,
    GhostMatrixState.IMPOSTER_WINS: SPRITE_ANGRY_GHOST,
    GhostMatrixState.IDLE: SPRITE_CALM_B,
}


def masks_to_pixels(masks: tuple[int, ...]) -> list[int]:
    """Convert 8 13-bit row masks into a flat 104-element list of 0/1 values."""
    if len(masks) != ROWS:
        raise ValueError(f"Expected {ROWS} row masks")
    pixels = [0] * FRAME_LENGTH
    for row, mask in enumerate(masks):
        for col in range(COLS):
            if mask & (1 << col):
                pixels[row * COLS + col] = 1
    return pixels


def render_ghost_frame(state: GhostMatrixState, beat: int = 0) -> list[int]:
    """Return the 104-element 0/1 pixel buffer for the given state and animation beat."""
    sprites = STATE_PRIMARY_SPRITES if (beat % 2 == 0) else STATE_SECONDARY_SPRITES
    masks = sprites.get(state, SPRITE_IDLE)
    return masks_to_pixels(masks)
