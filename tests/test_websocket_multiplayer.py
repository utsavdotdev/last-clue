"""End-to-end multi-client WebSocket and REST tests for The Last Clue."""

from __future__ import annotations

from fastapi.testclient import TestClient
from last_clue.app import create_app
from last_clue.config import Settings


def test_full_multiplayer_round_over_websockets_with_four_clients() -> None:
    settings = Settings(host="127.0.0.1", port=8765, ai_enabled=False)
    app = create_app(settings, room_code="SPOOKY")

    with TestClient(app) as client:
        health = client.get("/api/health").json()
        assert health["room_code"] == "SPOOKY"

        net = client.get("/api/network").json()
        assert net["room_code"] == "SPOOKY"
        assert "<svg" in net["qr_svg"]

        players = []
        for idx, name in enumerate(["Mina", "Jonathan", "VanHelsing", "Renfield"]):
            resp = client.post(
                "/api/join",
                json={"nickname": name, "room_code": "SPOOKY", "as_host": idx == 0},
            )
            assert resp.status_code == 200
            players.append(resp.json())

        assert players[0]["is_host"] is True
        assert all(not p["is_host"] for p in players[1:])

        # Connect 4 WebSocket clients simultaneously
        with (
            client.websocket_connect(
                f"/ws?player_id={players[0]['player_id']}&token={players[0]['reconnect_token']}"
            ) as ws0,
            client.websocket_connect(
                f"/ws?player_id={players[1]['player_id']}&token={players[1]['reconnect_token']}"
            ) as ws1,
            client.websocket_connect(
                f"/ws?player_id={players[2]['player_id']}&token={players[2]['reconnect_token']}"
            ) as ws2,
            client.websocket_connect(
                f"/ws?player_id={players[3]['player_id']}&token={players[3]['reconnect_token']}"
            ) as ws3,
        ):
            sockets = {
                players[0]["player_id"]: ws0,
                players[1]["player_id"]: ws1,
                players[2]["player_id"]: ws2,
                players[3]["player_id"]: ws3,
            }

            # Drain initial sync messages
            for ws in sockets.values():
                init_msg = ws.receive_json()
                assert init_msg["type"] == "state_sync"

            # Non-host cannot start the game
            ws1.send_json({"type": "start_round"})
            err_msg = ws1.receive_json()
            while err_msg["type"] == "state_sync":
                err_msg = ws1.receive_json()
            assert err_msg["type"] == "error"
            assert "Only the host" in err_msg["message"]

            # Host starts the round
            ws0.send_json({"type": "start_round", "use_ai_intro": False})

            latest_sync: dict[str, dict] = {}
            for pid, ws in sockets.items():
                msg = ws.receive_json()
                while msg["type"] != "state_sync" or msg["public"]["phase"] != "ROLE_REVEAL":
                    msg = ws.receive_json()
                latest_sync[pid] = msg

            imposter_id = None
            secret_word = None
            for pid, msg in latest_sync.items():
                priv = msg["private"]
                if priv["role"] == "IMPOSTER":
                    imposter_id = pid
                    assert priv["secret_word"] is None
                else:
                    assert priv["role"] == "SURVIVOR"
                    assert priv["secret_word"] is not None
                    secret_word = priv["secret_word"]

            assert imposter_id is not None
            assert secret_word is not None

            # Host transitions to Clue Round
            ws0.send_json({"type": "begin_clue_round"})
            state = client.get("/api/state").json()["public"]
            assert state["phase"] == "CLUE_ROUND"

            for speaker_id in state["speaking_order"]:
                sockets[speaker_id].send_json(
                    {"type": "submit_clue", "clue": "Eerie moonlight"}
                )

            state = client.get("/api/state").json()["public"]
            assert state["phase"] == "DISCUSSION"
            assert len(state["clues"]) == 4

            # Host advances from Discussion to Voting
            ws0.send_json({"type": "begin_voting"})
            state = client.get("/api/state").json()["public"]
            assert state["phase"] == "VOTING"

            survivor_ids = [p["player_id"] for p in players if p["player_id"] != imposter_id]
            for sid in survivor_ids:
                sockets[sid].send_json({"type": "cast_vote", "target_id": imposter_id})
            sockets[imposter_id].send_json(
                {"type": "cast_vote", "target_id": survivor_ids[0]}
            )

            state = client.get("/api/state").json()["public"]
            assert state["phase"] == "FINAL_GUESS"
            assert state["accused_player_id"] == imposter_id

            # Imposter submits wrong final guess -> Survivors win
            sockets[imposter_id].send_json(
                {"type": "submit_final_guess", "guess": "WrongGuessWord"}
            )
            state = client.get("/api/state").json()["public"]
            assert state["phase"] == "RESULTS"
            assert state["outcome"]["winner"] == "SURVIVORS"
            assert state["outcome"]["secret_word"] == secret_word


def test_serves_compiled_frontend_and_imposter_escape_path() -> None:
    settings = Settings(host="127.0.0.1", port=8765, ai_enabled=False)
    app = create_app(settings, room_code="ESCAPE")

    with TestClient(app) as client:
        index_resp = client.get("/")
        assert index_resp.status_code == 200
        assert "The Last Clue" in index_resp.text

        players = []
        for idx, name in enumerate(["Arthur", "Lucy", "Quincey", "Seward"]):
            resp = client.post(
                "/api/join",
                json={"nickname": name, "room_code": "ESCAPE", "as_host": idx == 0},
            )
            assert resp.status_code == 200
            players.append(resp.json())

        with (
            client.websocket_connect(
                f"/ws?player_id={players[0]['player_id']}&token={players[0]['reconnect_token']}"
            ) as ws0,
            client.websocket_connect(
                f"/ws?player_id={players[1]['player_id']}&token={players[1]['reconnect_token']}"
            ) as ws1,
            client.websocket_connect(
                f"/ws?player_id={players[2]['player_id']}&token={players[2]['reconnect_token']}"
            ) as ws2,
            client.websocket_connect(
                f"/ws?player_id={players[3]['player_id']}&token={players[3]['reconnect_token']}"
            ) as ws3,
        ):
            sockets = {
                players[0]["player_id"]: ws0,
                players[1]["player_id"]: ws1,
                players[2]["player_id"]: ws2,
                players[3]["player_id"]: ws3,
            }

            ws0.send_json({"type": "start_round", "use_ai_intro": False})
            ws0.send_json({"type": "begin_clue_round"})
            state = client.get("/api/state").json()["public"]
            for speaker_id in state["speaking_order"]:
                sockets[speaker_id].send_json({"type": "submit_clue", "clue": "Foggy crypt"})

            ws0.send_json({"type": "begin_voting"})

            # Find a Survivor to wrongly accuse so the Imposter escapes
            imposter_id = app.state.room_manager.engine.imposter_id
            innocent_id = next(p["player_id"] for p in players if p["player_id"] != imposter_id)

            for p in players:
                pid = p["player_id"]
                target = innocent_id if pid != innocent_id else imposter_id
                sockets[pid].send_json({"type": "cast_vote", "target_id": target})

            state = client.get("/api/state").json()["public"]
            assert state["phase"] == "RESULTS"
            assert state["outcome"]["winner"] == "IMPOSTER"
            assert state["outcome"]["reason"] == "IMPOSTER_ESCAPED_VOTE"
            assert state["outcome"]["accused_id"] == innocent_id
