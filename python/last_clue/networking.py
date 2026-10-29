"""LAN IPv4 discovery and SVG QR code generation for The Last Clue."""

from __future__ import annotations

import logging
import socket

logger = logging.getLogger(__name__)


def detect_lan_ips() -> list[str]:
    """Detect non-loopback IPv4 addresses on the host machine or Arduino UNO Q."""
    ips: list[str] = []

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.2)
            s.connect(("10.255.255.255", 1))
            primary = s.getsockname()[0]
            if primary and not primary.startswith("127."):
                ips.append(primary)
    except OSError:
        pass

    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            addr = str(info[4][0])
            if addr and not addr.startswith("127.") and addr not in ips:
                ips.append(addr)
    except OSError:
        pass

    return ips


def primary_join_url(port: int, room_code: str | None = None) -> str:
    """Return the primary LAN URL for players to scan or open on their phones."""
    ips = detect_lan_ips()
    host = ips[0] if ips else "127.0.0.1"
    base = f"http://{host}:{port}"
    if room_code:
        return f"{base}/?room={room_code.upper()}"
    return base


def generate_qr_svg(url: str) -> str:
    """Generate a self-contained SVG QR code for the join URL.

    Prefer the optional ``qrcode`` package when present, otherwise use the
    stdlib-only encoder in ``last_clue.qr_svg`` so App Lab starts without it.
    """
    try:
        import io

        import qrcode
        import qrcode.image.svg

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(image_factory=qrcode.image.svg.SvgPathImage)
        buffer = io.BytesIO()
        img.save(buffer)
        return buffer.getvalue().decode("utf-8")
    except Exception as exc:
        logger.info("Using stdlib QR encoder (%s)", exc)
        from last_clue.qr_svg import generate_qr_svg as stdlib_qr_svg

        return stdlib_qr_svg(url)
