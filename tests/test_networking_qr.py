"""Tests for LAN networking helpers and stdlib QR generation."""

from __future__ import annotations

from last_clue.networking import generate_qr_svg, primary_join_url
from last_clue.qr_svg import encode_qr_matrix, generate_qr_svg as stdlib_qr_svg


def test_primary_join_url_includes_room_code() -> None:
    url = primary_join_url(8765, "haunt6")
    assert url.endswith("/?room=HAUNT6")
    assert ":8765" in url


def test_stdlib_qr_svg_contains_modules_for_join_url() -> None:
    url = "http://192.168.1.42:8765/?room=CRYPT1"
    matrix = encode_qr_matrix(url)
    assert len(matrix) >= 21
    assert len(matrix) == len(matrix[0])
    assert any(any(cell for cell in row) for row in matrix)

    svg = stdlib_qr_svg(url)
    assert svg.startswith("<svg")
    assert 'fill="#000000"' in svg
    assert "</svg>" in svg


def test_networking_generate_qr_svg_never_raises() -> None:
    svg = generate_qr_svg("http://10.0.0.8:8765/?room=SPOOKY")
    assert "<svg" in svg
    assert "</svg>" in svg
