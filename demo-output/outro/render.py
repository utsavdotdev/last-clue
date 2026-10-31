#!/usr/bin/env python3
"""Deterministic 1920x1080 / 30fps outro renderer. No third-party Python deps."""

from __future__ import annotations

import math
import os
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
PLATES = ASSETS / "plates"
RASTER = ASSETS / "raster"
FRAMES = ROOT / "frames"
AUDIO = ROOT / "audio"
FONTS = ASSETS / "fonts"

W, H = 1920, 1080
FPS = 30
DURATION = 8.0
FRAME_COUNT = int(DURATION * FPS)

GROUND = (200, 194, 198)  # #c8c2c6
INK = (0, 20, 47)  # #00142f
LED_BOARD = (11, 15, 23)  # #0b0f17
LED_ON = (56, 189, 248)  # #38bdf8
LED_OFF = (30, 38, 54)  # #1e2636

CALM_A = (
    "....#####....",
    "...#######...",
    "..##.#.#.##..",
    "..#########..",
    "..#########..",
    "..#########..",
    "..##.###.##..",
    "..#...#...#..",
)
BLINK = (
    "....#####....",
    "...#######...",
    "..##.....##..",
    "..#########..",
    "..#########..",
    "..#########..",
    "..##.###.##..",
    "..#...#...#..",
)


def clamp(v: float, a: float = 0.0, b: float = 1.0) -> float:
    return a if v < a else b if v > b else v


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def ease_out_cubic(t: float) -> float:
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in_out_cubic(t: float) -> float:
    t = clamp(t)
    return 4 * t * t * t if t < 0.5 else 1 - ((-2 * t + 2) ** 3) / 2


def rng(t: float, a: float, b: float) -> float:
    return clamp((t - a) / (b - a)) if b != a else 1.0


def blink_amount(t: float, start: float, end: float) -> float:
    u = rng(t, start, end)
    if u <= 0 or u >= 1:
        return 0.0
    return math.sin(u * math.pi)


def run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if result.returncode:
        sys.stderr.write(result.stderr.decode("utf-8", errors="replace"))
        raise subprocess.CalledProcessError(result.returncode, cmd, stderr=result.stderr)


def write_png(path: Path, width: int, height: int, rgb: bytes) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(
            ">I", zlib.crc32(tag + data) & 0xFFFFFFFF
        )

    raw = bytearray()
    row = width * 3
    for y in range(height):
        raw.append(0)
        raw.extend(rgb[y * row : (y + 1) * row])
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
        + chunk(b"IEND", b"")
    )


def write_png_rgba(path: Path, width: int, height: int, rgba: bytes) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(
            ">I", zlib.crc32(tag + data) & 0xFFFFFFFF
        )

    raw = bytearray()
    row = width * 4
    for y in range(height):
        raw.append(0)
        raw.extend(rgba[y * row : (y + 1) * row])
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
        + chunk(b"IEND", b"")
    )


def png_to_rgba(path: Path) -> tuple[int, int, bytearray]:
    probe = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0",
            str(path),
        ],
        text=True,
    ).strip()
    width, height = (int(x) for x in probe.split(","))
    raw = subprocess.check_output(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgba",
            "-",
        ]
    )
    return width, height, bytearray(raw)


def raster_svg(svg: Path, dest: Path, width: int, height: int | None = None) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    h = height or width
    run(["swift", str(ROOT / "raster_svg.swift"), str(svg), str(dest), str(width), str(h)])
    return dest


def make_text_plates() -> None:
    PLATES.mkdir(parents=True, exist_ok=True)
    run(["swift", str(ROOT / "drawtext.swift"), str(ROOT)])


def fill(rgb: bytearray, color: tuple[int, int, int]) -> None:
    r, g, b = color
    for i in range(0, len(rgb), 3):
        rgb[i] = r
        rgb[i + 1] = g
        rgb[i + 2] = b


def make_fog() -> bytes:
    buf = bytearray(W * H * 3)
    cx, cy = 0.42 * W, 0.46 * H
    for y in range(H):
        for x in range(W):
            i = (y * W + x) * 3
            r, g, b = GROUND
            dxr = (x / W) - 0.88
            dyr = (y / H) + 0.08
            red = math.exp(-(dxr * dxr * 3.2 + dyr * dyr * 4.8)) * 0.12
            r = min(255, int(r + 225 * red))
            g = min(255, int(g + 29 * red))
            b = min(255, int(b + 56 * red))
            dxn = (x / W) + 0.06
            dyn = (y / H) - 1.08
            navy = math.exp(-(dxn * dxn * 3.6 + dyn * dyn * 5.2)) * 0.12
            r = max(0, int(r * (1 - navy) + 0 * navy))
            g = max(0, int(g * (1 - navy) + 20 * navy))
            b = max(0, int(b * (1 - navy) + 47 * navy))
            dxw = x - cx
            dyw = y - cy
            warm = math.exp(-((dxw * dxw) / (640 * 640) + (dyw * dyw) / (420 * 420))) * 0.42
            r = min(255, int(r + (255 - r) * warm))
            g = min(255, int(g + (248 - g) * warm))
            b = min(255, int(b + (236 - b) * warm))
            buf[i] = r
            buf[i + 1] = g
            buf[i + 2] = b
    return bytes(buf)


def make_matrix_frame(sprite: tuple[str, ...]) -> bytes:
    buf = bytearray(W * H * 3)
    fill(buf, LED_BOARD)
    board_w, board_h = 1040, 680
    pad = 36
    x0 = (W - board_w) // 2
    y0 = (H - board_h) // 2
    inner_w = board_w - pad * 2
    inner_h = board_h - pad * 2
    gap = 10
    cell_w = (inner_w - gap * 12) / 13
    cell_h = (inner_h - gap * 7) / 8
    for y in range(y0, y0 + board_h):
        for x in range(x0, x0 + board_w):
            i = (y * W + x) * 3
            buf[i : i + 3] = bytes(LED_BOARD)
    for r, row in enumerate(sprite):
        for c, ch in enumerate(row):
            color = LED_ON if ch == "#" else LED_OFF
            cx0 = int(x0 + pad + c * (cell_w + gap))
            cy0 = int(y0 + pad + r * (cell_h + gap))
            cx1 = int(cx0 + cell_w)
            cy1 = int(cy0 + cell_h)
            for y in range(cy0, cy1):
                for x in range(cx0, cx1):
                    i = (y * W + x) * 3
                    buf[i] = color[0]
                    buf[i + 1] = color[1]
                    buf[i + 2] = color[2]
    return bytes(buf)


def mix_rgb(a: bytes, b: bytes, t: float) -> bytearray:
    t = clamp(t)
    if t <= 0:
        return bytearray(a)
    if t >= 1:
        return bytearray(b)
    out = bytearray(len(a))
    ia = 1 - t
    for i, (av, bv) in enumerate(zip(a, b)):
        out[i] = int(av * ia + bv * t)
    return out


def blit(
    dst: bytearray,
    src: bytearray,
    sw: int,
    sh: int,
    x: int,
    y: int,
    alpha: float,
) -> None:
    if alpha <= 0.001:
        return
    for sy in range(sh):
        dy = y + sy
        if dy < 0 or dy >= H:
            continue
        for sx in range(sw):
            dx = x + sx
            if dx < 0 or dx >= W:
                continue
            si = (sy * sw + sx) * 4
            sa = (src[si + 3] / 255.0) * alpha
            if sa <= 0.001:
                continue
            di = (dy * W + dx) * 3
            inv = 1 - sa
            dst[di] = int(dst[di] * inv + src[si] * sa)
            dst[di + 1] = int(dst[di + 1] * inv + src[si + 1] * sa)
            dst[di + 2] = int(dst[di + 2] * inv + src[si + 2] * sa)


def close_eyes(src: bytearray, sw: int, sh: int, lids: list[tuple[float, float, float, float]]) -> bytearray:
    out = bytearray(src)
    for x0, y0, x1, y1 in lids:
        xa, xb = int(x0 * sw), int(x1 * sw)
        ya, yb = int(y0 * sh), int(y1 * sh)
        for y in range(max(0, ya), min(sh, yb)):
            for x in range(max(0, xa), min(sw, xb)):
                i = (y * sw + x) * 4
                if out[i + 3] < 20:
                    continue
                out[i] = 255
                out[i + 1] = 255
                out[i + 2] = 255
                out[i + 3] = 255
    return out


def scale_stage() -> None:
    return


def prepare_assets() -> dict[str, tuple[int, int, bytearray]]:
    RASTER.mkdir(parents=True, exist_ok=True)
    ghost_svg = ASSETS / "ghost-mark.svg"
    logo_svg = ASSETS / "logo.svg"
    ghost_png = raster_svg(ghost_svg, RASTER / "ghost-mark.png", 280, 330)
    logo_png = raster_svg(logo_svg, RASTER / "logo.png", 240, 240)

    make_text_plates()

    assets = {
        "ghost": png_to_rgba(ghost_png),
        "logo": png_to_rgba(logo_png),
        "remain": png_to_rgba(PLATES / "remain.png"),
        "wordmark": png_to_rgba(PLATES / "wordmark.png"),
        "tagline": png_to_rgba(PLATES / "tagline.png"),
        "tech": png_to_rgba(PLATES / "tech.png"),
        "oss": png_to_rgba(PLATES / "oss.png"),
    }
    gw, gh, gpx = assets["ghost"]
    assets["ghost_blink"] = (gw, gh, close_eyes(gpx, gw, gh, [(0.28, 0.38, 0.44, 0.50), (0.56, 0.38, 0.72, 0.50)]))
    lw, lh, lpx = assets["logo"]
    assets["logo_blink"] = (lw, lh, close_eyes(lpx, lw, lh, [(0.36, 0.40, 0.47, 0.50), (0.53, 0.40, 0.64, 0.50)]))
    return assets


def generate_audio() -> Path:
    AUDIO.mkdir(parents=True, exist_ok=True)
    wav = AUDIO / "outro.wav"
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=68:sample_rate=48000:duration=8",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=102:sample_rate=48000:duration=8",
            "-f",
            "lavfi",
            "-i",
            "anoisesrc=color=pink:sample_rate=48000:duration=8",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=184:sample_rate=48000:duration=8",
            "-filter_complex",
            (
                "[0]volume=0.07,lowpass=f=140[d1];"
                "[1]volume=0.045,lowpass=f=180[d2];"
                "[d1][d2]amix=inputs=2:duration=first,afade=t=in:st=0:d=0.7,afade=t=out:st=6.7:d=1.3[drone];"
                "[2]atrim=0:0.55,asetpts=PTS-STARTPTS,highpass=f=300,lowpass=f=1800,"
                "afade=t=in:st=0:d=0.08,afade=t=out:st=0.18:d=0.35,volume=0.22,adelay=1450|1450[whoosh];"
                "[3]atrim=0:0.7,asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.02,afade=t=out:st=0.08:d=0.55,"
                "volume=0.16,adelay=4000|4000[accent];"
                "[drone][whoosh][accent]amix=inputs=3:duration=first:normalize=0,alimiter=limit=0.35[out]"
            ),
            "-map",
            "[out]",
            "-ac",
            "2",
            str(wav),
        ]
    )
    return wav


def start_encoder(wav: Path) -> tuple[subprocess.Popen, Path]:
    mp4 = ROOT / "the-last-clue-outro.mp4"
    proc = subprocess.Popen(
        [
            "ffmpeg",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{W}x{H}",
            "-r",
            str(FPS),
            "-i",
            "-",
            "-i",
            str(wav),
            "-c:v",
            "libx264",
            "-profile:v",
            "high",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-color_range",
            "tv",
            "-colorspace",
            "bt709",
            "-color_primaries",
            "bt709",
            "-color_trc",
            "bt709",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-movflags",
            "+faststart",
            "-t",
            "8",
            str(mp4),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    return proc, mp4


QC_INDEXES = {12, 24, 72, 156, 201, 237, 240}


def render_frames(assets: dict[str, tuple[int, int, bytearray]], raw_fh) -> None:
    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True)
    print("painting backgrounds…", flush=True)
    fog = make_fog()
    matrix_open = make_matrix_frame(CALM_A)
    matrix_blink = make_matrix_frame(BLINK)

    gw, gh, ghost = assets["ghost"]
    _, _, ghost_blink = assets["ghost_blink"]
    lw, lh, logo = assets["logo"]
    _, _, logo_blink = assets["logo_blink"]
    rw, rh, remain = assets["remain"]
    ww, wh, wordmark = assets["wordmark"]
    tw, th, tagline = assets["tagline"]
    ew, eh, tech = assets["tech"]
    ow, oh, oss = assets["oss"]

    for n in range(FRAME_COUNT):
        t = n / FPS
        fog_in = ease_in_out_cubic(rng(t, 1.20, 2.00))
        use_blink = blink_amount(t, 0.72, 0.96) > 0.55
        mat = matrix_blink if use_blink else matrix_open
        frame = mix_rgb(mat, fog, fog_in)

        remain_in = ease_out_cubic(rng(t, 1.45, 2.20))
        remain_out = ease_in_out_cubic(rng(t, 3.85, 4.55))
        remain_vis = remain_in * (1 - remain_out)
        if remain_vis > 0.01:
            drift = ease_out_cubic(rng(t, 1.50, 3.80))
            gy = int(lerp(18, -4, drift))
            gx = (W - gw) // 2
            gy_pos = 268 + gy
            blit(frame, ghost, gw, gh, gx, gy_pos, remain_vis)
            line_a = ease_out_cubic(rng(t, 1.85, 2.55)) * (1 - remain_out)
            blit(frame, remain, rw, rh, (W - rw) // 2, gy_pos + gh + 18, line_a)

        logo_in = ease_out_cubic(rng(t, 4.05, 4.85))
        if logo_in > 0.01:
            lift = int(lerp(18, 0, logo_in))
            logo_px = logo_blink if blink_amount(t, 6.55, 6.82) > 0.45 else logo
            lx = (W - lw) // 2
            ly = 214 + lift
            blit(frame, logo_px, lw, lh, lx, ly, logo_in)
            blit(
                frame,
                wordmark,
                ww,
                wh,
                (W - ww) // 2,
                ly + lh + 8,
                ease_out_cubic(rng(t, 4.18, 4.85)),
            )
            blit(
                frame,
                tagline,
                tw,
                th,
                (W - tw) // 2,
                ly + lh + 8 + wh - 10,
                ease_out_cubic(rng(t, 4.55, 5.20)),
            )
            blit(
                frame,
                tech,
                ew,
                eh,
                (W - ew) // 2,
                ly + lh + 8 + wh + th + 8,
                ease_out_cubic(rng(t, 5.05, 5.65)),
            )
            blit(
                frame,
                oss,
                ow,
                oh,
                (W - ow) // 2,
                ly + lh + 8 + wh + th + eh + 12,
                ease_out_cubic(rng(t, 5.00, 5.55)),
            )

        fade = ease_in_out_cubic(rng(t, 7.15, 8.00))
        if fade > 0:
            for i in range(len(frame)):
                frame[i] = int(frame[i] * (1 - fade))

        packed = bytes(frame)
        raw_fh.write(packed)
        if n + 1 in QC_INDEXES:
            write_png(FRAMES / f"frame-{n + 1:04d}.png", W, H, packed)
        if n % 30 == 0 or n == FRAME_COUNT - 1:
            print(f"frame {n + 1}/{FRAME_COUNT}", flush=True)


def export_qc_frames() -> None:
    qc = ROOT / "frames" / "qc"
    qc.mkdir(exist_ok=True)
    picks = {
        "00-matrix": 12,
        "01-blink": 24,
        "02-ghost": 72,
        "03-lockup": 156,
        "04-logo-blink": 201,
        "05-fade": 237,
    }
    for name, idx in picks.items():
        src = FRAMES / f"frame-{idx:04d}.png"
        if src.exists():
            shutil.copy(src, qc / f"{name}.png")


def main() -> int:
    print("preparing assets…", flush=True)
    assets = prepare_assets()
    print("mixing audio…", flush=True)
    wav = generate_audio()
    print("rendering and encoding…", flush=True)
    proc, mp4 = start_encoder(wav)
    assert proc.stdin is not None
    try:
        render_frames(assets, proc.stdin)
        proc.stdin.close()
        err = proc.communicate()[1]
    except Exception:
        proc.kill()
        raise
    if proc.returncode:
        sys.stderr.write(err.decode("utf-8", errors="replace"))
        return proc.returncode
    export_qc_frames()
    print(mp4, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
