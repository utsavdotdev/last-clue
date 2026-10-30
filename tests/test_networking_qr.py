"""Comprehensive tests for LAN URL resolution, PNG/SVG QR generation, and programmatic QR decoding."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse
from fastapi.testclient import TestClient
import qrcode
from qrcode.util import MODE_8BIT_BYTE, QRData

from last_clue.app import create_app
from last_clue.config import Settings
from last_clue.networking import (
    generate_qr_png,
    generate_qr_svg,
    primary_join_url,
    resolve_join_url,
)
from last_clue.qr_svg import (
    decode_qr_matrix,
    decode_qr_png,
    decode_qr_svg,
    encode_qr_matrix,
)


def test_primary_join_url_and_host_resolution() -> None:
    url, reachable, warning = resolve_join_url(
        8765,
        "haunt6",
        request_host="192.168.1.77:8765",
    )
    assert url == "http://192.168.1.77:8765/?room=HAUNT6"
    assert reachable is True
    assert warning is None

    # Preferred host overrides loopback request host
    url_pref, reachable_pref, _ = resolve_join_url(
        8765,
        "crypt2",
        request_host="localhost:8765",
        preferred_host="10.0.0.55",
    )
    assert url_pref == "http://10.0.0.55:8765/?room=CRYPT2"
    assert reachable_pref is True


def test_encode_qr_matrix_matches_reference_qrcode_library_and_decodes() -> None:
    test_urls = [
        "http://192.168.1.42:8765/?room=CRYPT1",
        "http://10.0.0.15:8765/?room=GHOST9",
        "http://172.20.10.2:8765/?room=SPIRIT",
        "http://uno-q.local:8765/?room=SHADOW&mode=party&source=qr",
    ]
    for url in test_urls:
        matrix = encode_qr_matrix(url)
        decoded_from_matrix = decode_qr_matrix(matrix)
        assert decoded_from_matrix == url

        png_bytes = generate_qr_png(url)
        assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
        assert decode_qr_png(png_bytes) == url

        svg_text = generate_qr_svg(url)
        assert svg_text.startswith("<svg")
        assert decode_qr_svg(svg_text) == url

        # Verify our Reed-Solomon codewords match the reference qrcode library
        version = ((len(matrix) - 21) // 4) + 1
        qr = qrcode.QRCode(
            version=version,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=1,
            border=0,
        )
        qr.add_data(QRData(url.encode("utf-8"), MODE_8BIT_BYTE), optimize=0)
        qr.make(fit=False)
        ref_matrix = [[1 if cell else 0 for cell in row] for row in qr.get_matrix()]
        assert decode_qr_matrix(ref_matrix) == url


def test_end_to_end_room_creation_qr_decoding_and_player_join() -> None:
    settings = Settings(host="0.0.0.0", port=8765, ai_enabled=False)
    app = create_app(settings, room_code="ROOM01")

    with TestClient(app, base_url="http://192.168.1.88:8765") as client:
        # 1. Host creates a brand-new room
        new_room_resp = client.post("/api/room/new")
        assert new_room_resp.status_code == 200
        net_data_1 = new_room_resp.json()
        room_1 = net_data_1["room_code"]
        assert room_1 != "ROOM01"
        assert len(room_1) == 6

        # 2. Inspect the exact URL in network info and fetch the QR PNG
        expected_url_1 = f"http://192.168.1.88:8765/?room={room_1}"
        assert net_data_1["join_url"] == expected_url_1
        assert "localhost" not in net_data_1["join_url"]
        assert "127.0.0.1" not in net_data_1["join_url"]

        qr_png_resp = client.get(net_data_1["qr_png_url"])
        assert qr_png_resp.status_code == 200
        assert qr_png_resp.headers["content-type"] == "image/png"

        # 3 & 4. Programmatically decode the PNG & SVG QR codes and confirm exact URL match
        decoded_png_url_1 = decode_qr_png(qr_png_resp.content)
        decoded_svg_url_1 = decode_qr_svg(net_data_1["qr_svg"])
        assert decoded_png_url_1 == expected_url_1
        assert decoded_svg_url_1 == expected_url_1

        # 5 & 6 & 7. Parse the ?room= param from the decoded QR URL and join the room
        parsed = urlparse(decoded_png_url_1)
        room_from_qr = parse_qs(parsed.query)["room"][0]
        assert room_from_qr == room_1

        host_join = client.post(
            "/api/join",
            json={"nickname": "HostClara", "room_code": room_from_qr, "as_host": True},
        )
        assert host_join.status_code == 200

        player_join = client.post(
            "/api/join",
            json={"nickname": "PhonePlayer", "room_code": room_from_qr, "as_host": False},
        )
        assert player_join.status_code == 200

        lobby_state = client.get("/api/state").json()["public"]
        assert lobby_state["room_code"] == room_1
        nicknames = [p["nickname"] for p in lobby_state["players"]]
        assert nicknames == ["HostClara", "PhonePlayer"]

        # 8. Test with another room to ensure the QR code does not reuse the old room URL
        second_room_resp = client.post("/api/room/new")
        assert second_room_resp.status_code == 200
        net_data_2 = second_room_resp.json()
        room_2 = net_data_2["room_code"]
        assert room_2 != room_1

        expected_url_2 = f"http://192.168.1.88:8765/?room={room_2}"
        qr_png_resp_2 = client.get(net_data_2["qr_png_url"])
        assert qr_png_resp_2.status_code == 200
        decoded_png_url_2 = decode_qr_png(qr_png_resp_2.content)
        assert decoded_png_url_2 == expected_url_2
        assert decoded_png_url_2 != decoded_png_url_1


def test_networking_generate_qr_svg_helper() -> None:
    url = primary_join_url(8765, "SPOOKY", preferred_host="192.168.1.50")
    svg = generate_qr_svg(url)
    assert decode_qr_svg(svg) == "http://192.168.1.50:8765/?room=SPOOKY"
