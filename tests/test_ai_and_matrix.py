"""Automated tests for local AI validation, anti-leak checks, fallback, and 8x13 LED Matrix."""

from __future__ import annotations

from pathlib import Path
import re
import pytest
from last_clue.ai.local_provider import (
    LlamaServerClient,
    LocalHorrorProvider,
    is_local_model_url,
    validate_generated_word_pack,
    validate_round_intro,
)
from last_clue.ai.service import HauntedAIService
from last_clue.hardware.frames import (
    COLS,
    FRAME_LENGTH,
    GHOST_STATE_CODES,
    ROWS,
    STATE_PRIMARY_SPRITES,
)
from last_clue.hardware.matrix_adapter import MatrixAdapter
from last_clue.hardware.simulator import format_ascii_matrix
from last_clue.hardware.uno_q_matrix import UnoQBridgeClient
from last_clue.models import AIStatusState, GhostMatrixState


class FakeTransport:
    def __init__(self, response_text: str = "", should_fail: bool = False) -> None:
        self.response_text = response_text
        self.should_fail = should_fail
        self.calls: list[tuple[str, dict[str, object]]] = []

    def post_json(self, url: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
        self.calls.append((url, payload))
        if self.should_fail:
            raise TimeoutError("Simulated local model timeout")
        return {
            "choices": [
                {
                    "message": {
                        "content": self.response_text,
                    }
                }
            ]
        }


def test_is_local_model_url_rejects_cloud_and_accepts_uno_q_brick() -> None:
    assert is_local_model_url("http://llamacpp-models-runner:9999/v1/chat/completions") is True
    assert is_local_model_url("http://127.0.0.1:8080/v1/chat/completions") is True
    assert is_local_model_url("http://localhost:11434/v1/chat/completions") is True
    assert is_local_model_url("http://192.168.1.42:9999/v1/chat/completions") is True

    # Cloud / public endpoints must be rejected
    assert is_local_model_url("https://api.openai.com/v1/chat/completions") is False
    assert is_local_model_url("https://openrouter.ai/api/v1/chat/completions") is False
    assert is_local_model_url("http://user:pass@localhost:9999/v1/chat/completions") is False


def test_validate_round_intro_blocks_secret_word_and_synonym_leaks() -> None:
    valid = validate_round_intro(
        "<think>Thinking...</think>The hospital corridor has been silent for thirty years. Tonight a locked door creaked open.",
        secret_word="Vampire",
        synonyms=["Dracula", "Nosferatu"],
    )
    assert "hospital corridor" in valid
    assert "\u2014" not in valid

    with pytest.raises(ValueError, match="leaked the secret word"):
        validate_round_intro(
            "A hungry vampire waits in the belfry above you.",
            secret_word="Vampire",
            synonyms=["Dracula"],
        )

    with pytest.raises(ValueError, match="leaked the secret word"):
        validate_round_intro(
            "Count Dracula's shadow stretches across the dining hall.",
            secret_word="Vampire",
            synonyms=["Dracula"],
        )


def test_validate_generated_word_pack_parses_json_and_filters_duplicates() -> None:
    raw_json = """```json
    {
      "words": [
        {
          "word": "Vampire",
          "category": "Horror Creatures",
          "difficulty": "easy",
          "synonyms": ["Dracula"]
        },
        {
          "word": "Lantern Specter",
          "category": "Haunted Relics",
          "difficulty": "medium",
          "synonyms": ["Will o wisp", "Ghostly lantern"]
        }
      ]
    }
    ```"""
    entries = validate_generated_word_pack(raw_json)
    # "Vampire" is already in BUNDLED_WORD_PACKS so it must be deduplicated
    assert len(entries) == 1
    assert entries[0].word == "Lantern Specter"
    assert entries[0].category == "Haunted Relics"
    assert entries[0].source == "ai"


def test_haunted_ai_service_falls_back_gracefully_on_timeout_or_leak() -> None:
    transport = FakeTransport(should_fail=True)
    client = LlamaServerClient(
        url="http://llamacpp-models-runner:9999/v1/chat/completions",
        model="Qwen3.5-0.8B-Q4_0",
        transport=transport,
    )
    service = HauntedAIService(
        llm_url=client.url,
        llm_model=client.model,
        local_provider=LocalHorrorProvider(client),
    )

    intro, used_ai = service.get_round_intro(
        category="Haunted Locations",
        secret_word="Graveyard",
        use_ai=True,
    )
    assert used_ai is False
    assert len(intro) > 15
    assert service.status_view().status == AIStatusState.FALLBACK
    assert "using built-in content" in service.status_view().detail


def test_haunted_ai_service_generates_custom_words_and_caches_intro() -> None:
    json_payload = '{"words": [{"word": "Bone Lantern", "category": "Cursed Objects", "difficulty": "medium", "synonyms": ["Skull lamp"]}]}'
    transport = FakeTransport(response_text=json_payload, should_fail=False)
    client = LlamaServerClient(
        url="http://llamacpp-models-runner:9999/v1/chat/completions",
        model="Qwen3.5-0.8B-Q4_0",
        transport=transport,
    )
    service = HauntedAIService(
        llm_url=client.url,
        llm_model=client.model,
        local_provider=LocalHorrorProvider(client),
    )

    entries = service.generate_custom_words("Cursed Objects", count=1)
    assert len(entries) == 1
    assert entries[0].word == "Bone Lantern"
    assert service.status_view().status == AIStatusState.READY
    assert service.status_view().custom_words_count == 1


def test_matrix_adapter_renders_all_ten_ghost_states_and_calls_bridge() -> None:
    recorded_calls: list[tuple[str, int, int]] = []

    def fake_bridge_call(method: str, state_code: int, generation: int) -> None:
        recorded_calls.append((method, state_code, generation))

    bridge = UnoQBridgeClient(call_fn=fake_bridge_call)
    adapter = MatrixAdapter(bridge=bridge, sync_mode=True)

    assert adapter.hardware_connected is True
    assert len(recorded_calls) == 1
    assert recorded_calls[0][1] == GHOST_STATE_CODES[GhostMatrixState.BOOT]

    for state in GhostMatrixState:
        snap = adapter.set_state(state, force=True)
        assert snap.state == state
        assert len(snap.pixels) == FRAME_LENGTH
        assert ROWS * COLS == 104
        assert any(px == 1 for px in snap.pixels)
        ascii_art = format_ascii_matrix(state)
        assert len(ascii_art.splitlines()) == ROWS


def test_sketch_ino_sprite_masks_match_python_frames() -> None:
    sketch_path = Path(__file__).resolve().parents[1] / "sketch" / "sketch.ino"
    sketch_text = sketch_path.read_text(encoding="utf-8")
    assert 'Bridge.provide_safe("set_ghost_state", set_ghost_state);' in sketch_text

    for state, masks in STATE_PRIMARY_SPRITES.items():
        mask_str = ", ".join(str(m) for m in masks)
        assert re.search(rf"\{{{re.escape(mask_str)}\}}", sketch_text), (
            f"Missing primary sprite mask for {state} in sketch.ino"
        )
