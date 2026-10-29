"""Automated unit tests for The Last Clue untimed game rules, repeatable clue rounds, privacy boundaries, and scoring."""

from __future__ import annotations

import pytest
from last_clue.game_engine import GameEngine, GameRuleError
from last_clue.models import (
    GamePhase,
    GhostMatrixState,
    PlayerRole,
    WinReason,
    WinnerSide,
)
from last_clue.word_packs import BUNDLED_WORD_PACKS, list_categories


def _make_engine_with_players(count: int = 4) -> tuple[GameEngine, list[str]]:
    engine = GameEngine(room_code="CRYPT1")
    pids: list[str] = []
    for idx in range(count):
        session = engine.join_player(f"Player{idx + 1}", as_host=(idx == 0))
        pids.append(session.player_id)
    return engine, pids


def test_word_packs_have_five_categories_and_ten_words_each() -> None:
    categories = list_categories()
    assert len(categories) >= 5
    for category in categories:
        words_in_cat = [w for w in BUNDLED_WORD_PACKS if w.category == category]
        assert len(words_in_cat) >= 10
        seen = set()
        for entry in words_in_cat:
            assert entry.word.lower() not in seen
            seen.add(entry.word.lower())


def test_minimum_and_maximum_player_counts_and_unique_nicknames() -> None:
    engine = GameEngine(room_code="CRYPT1")
    p1 = engine.join_player("Alice", as_host=True)
    engine.join_player("Bob")
    engine.join_player("Charlie")

    assert p1.is_host is True
    with pytest.raises(GameRuleError, match="already taken"):
        engine.join_player("alice")

    with pytest.raises(GameRuleError, match="At least 4"):
        engine.start_round()

    engine.join_player("Diana")
    engine.start_round()
    assert engine.phase == GamePhase.ROLE_REVEAL


def test_role_assignment_and_strict_private_payload_isolation() -> None:
    engine, pids = _make_engine_with_players(5)
    engine.start_round()

    public_state = engine.build_public_state()
    public_json = public_state.model_dump(mode="json")

    assert engine.active_word_entry is not None
    secret_word = engine.active_word_entry.word

    assert secret_word not in str(public_json)
    assert public_state.outcome is None

    imposters = []
    survivors = []
    for pid in pids:
        priv = engine.build_private_payload(pid)
        if priv.role == PlayerRole.IMPOSTER:
            imposters.append(pid)
            assert priv.secret_word is None
            assert priv.category == engine.active_word_entry.category
            assert secret_word.upper() not in (priv.role_briefing or "").upper()
        else:
            survivors.append(pid)
            assert priv.role == PlayerRole.SURVIVOR
            assert priv.secret_word == secret_word
            assert secret_word.upper() in (priv.role_briefing or "")

    assert len(imposters) == 1
    assert len(survivors) == 4


def test_clue_round_and_repeatable_another_clue_round_flow() -> None:
    engine, pids = _make_engine_with_players(4)
    engine.start_round()

    for pid in pids:
        engine.mark_role_acknowledged(pid)

    assert engine.phase == GamePhase.CLUE_ROUND
    assert engine.clue_round_number == 1
    assert len(engine.speaking_order) == 4

    first_speaker = engine.current_speaker_id
    assert first_speaker is not None
    wrong_speaker = next(pid for pid in pids if pid != first_speaker)

    with pytest.raises(GameRuleError, match="Wait for your turn"):
        engine.submit_clue(wrong_speaker, "Out of turn clue")

    with pytest.raises(GameRuleError, match="40 characters"):
        engine.submit_clue(first_speaker, "x" * 45)

    for idx, speaker_id in enumerate(list(engine.speaking_order)):
        assert engine.current_speaker_id == speaker_id
        engine.submit_clue(speaker_id, f"First pass clue {idx + 1}")
        with pytest.raises(GameRuleError):
            engine.submit_clue(speaker_id, "Duplicate clue attempt")

    # After everyone submits a clue, phase enters DISCUSSION (decision point) with no timer
    assert engine.phase == GamePhase.DISCUSSION
    assert len(engine.clues) == 4
    assert all(c.round_pass == 1 for c in engine.clues)

    # Choose "Another Clue Round" -> starts Clue Round 2 and keeps earlier clues
    engine.start_another_clue_round()
    assert engine.phase == GamePhase.CLUE_ROUND
    assert engine.clue_round_number == 2

    for idx, speaker_id in enumerate(list(engine.speaking_order)):
        engine.submit_clue(speaker_id, f"Second pass clue {idx + 1}")

    assert engine.phase == GamePhase.DISCUSSION
    assert len(engine.clues) == 8
    assert [c.round_pass for c in engine.clues[:4]] == [1, 1, 1, 1]
    assert [c.round_pass for c in engine.clues[4:]] == [2, 2, 2, 2]


def test_voting_imposter_caught_wrong_final_guess_survivors_win() -> None:
    engine, pids = _make_engine_with_players(4)
    engine.start_round()
    engine.begin_clue_round()
    for speaker_id in list(engine.speaking_order):
        engine.submit_clue(speaker_id, "Candlelight")

    assert engine.phase == GamePhase.DISCUSSION
    engine.begin_voting()
    assert engine.phase == GamePhase.VOTING
    assert engine.matrix.state == GhostMatrixState.VOTING_PHASE

    imposter_id = engine.imposter_id
    assert imposter_id is not None
    survivors = [pid for pid in pids if pid != imposter_id]

    with pytest.raises(GameRuleError, match="cannot vote for yourself"):
        engine.cast_vote(survivors[0], survivors[0])

    for s_id in survivors:
        engine.cast_vote(s_id, imposter_id)

    with pytest.raises(GameRuleError, match="already cast"):
        engine.cast_vote(survivors[0], survivors[1])

    engine.cast_vote(imposter_id, survivors[0])

    assert engine.phase == GamePhase.FINAL_GUESS
    assert engine.accused_player_id == imposter_id
    assert engine.matrix.state == GhostMatrixState.IMPOSTER_DISCOVERED

    with pytest.raises(GameRuleError, match="Only the discovered Imposter"):
        engine.submit_final_guess(survivors[0], "Vampire")

    outcome = engine.submit_final_guess(imposter_id, "TotallyWrongWord999")
    assert engine.phase == GamePhase.RESULTS
    assert outcome.winner == WinnerSide.SURVIVORS
    assert outcome.reason == WinReason.IMPOSTER_CAUGHT_WRONG_GUESS
    assert engine.matrix.state == GhostMatrixState.SURVIVORS_WIN

    for s_id in survivors:
        assert engine.players[s_id].score == 1
    assert engine.players[imposter_id].score == 0


def test_voting_imposter_caught_correct_final_guess_or_synonym_imposter_wins() -> None:
    engine, pids = _make_engine_with_players(4)
    engine.selected_category = "Horror Creatures"
    engine.start_round()
    engine.begin_clue_round()
    for speaker_id in list(engine.speaking_order):
        engine.submit_clue(speaker_id, "Night creature")
    engine.begin_voting()

    imposter_id = engine.imposter_id
    assert imposter_id is not None
    survivors = [pid for pid in pids if pid != imposter_id]

    for s_id in survivors:
        engine.cast_vote(s_id, imposter_id)
    engine.cast_vote(imposter_id, survivors[0])

    assert engine.phase == GamePhase.FINAL_GUESS
    assert engine.active_word_entry is not None

    guess_str = f"  the {engine.active_word_entry.word.lower()}! "
    outcome = engine.submit_final_guess(imposter_id, guess_str)

    assert outcome.winner == WinnerSide.IMPOSTER
    assert outcome.reason == WinReason.IMPOSTER_CAUGHT_GUESSED_WORD
    assert outcome.imposter_guessed_correctly is True
    assert engine.matrix.state == GhostMatrixState.IMPOSTER_WINS
    assert engine.players[imposter_id].score == 2
    for s_id in survivors:
        assert engine.players[s_id].score == 0


def test_voting_tie_triggers_runoff_and_second_tie_lets_imposter_escape() -> None:
    engine, pids = _make_engine_with_players(4)
    engine.start_round()
    engine.begin_clue_round()
    for speaker_id in list(engine.speaking_order):
        engine.submit_clue(speaker_id, "Dark shadow")
    engine.begin_voting()

    p0, p1, p2, p3 = pids
    engine.cast_vote(p0, p1)
    engine.cast_vote(p2, p1)
    engine.cast_vote(p1, p0)
    engine.cast_vote(p3, p0)

    assert engine.phase == GamePhase.RUNOFF
    assert set(engine.runoff_candidates) == {p0, p1}
    assert engine.matrix.state == GhostMatrixState.RUNOFF

    with pytest.raises(GameRuleError, match="tied candidates"):
        engine.cast_vote(p0, p2)

    engine.cast_vote(p0, p1)
    engine.cast_vote(p2, p1)
    engine.cast_vote(p1, p0)
    engine.cast_vote(p3, p0)

    assert engine.phase == GamePhase.RESULTS
    assert engine.outcome is not None
    assert engine.outcome.winner == WinnerSide.IMPOSTER
    assert engine.outcome.reason == WinReason.IMPOSTER_ESCAPED_RUNOFF_TIE
    assert engine.outcome.accused_id is None
    assert engine.players[engine.imposter_id].score == 2  # type: ignore[index]


def test_disconnect_and_reconnect_and_host_skip() -> None:
    engine, pids = _make_engine_with_players(4)
    p0_session = engine.players[pids[0]]
    saved_token = p0_session.reconnect_token

    engine.start_round()
    engine.begin_clue_round()

    current = engine.current_speaker_id
    assert current is not None

    # Host can skip an inactive speaker without relying on a countdown timer
    engine.skip_current_speaker()
    assert engine.clues[0].clue == "[Skipped]"

    # Disconnect and reconnect using token
    engine.disconnect_player(pids[0])
    assert engine.players[pids[0]].connected is False
    rejoined = engine.join_player("IgnoredName", reconnect_token=saved_token)
    assert rejoined.player_id == pids[0]
    assert rejoined.connected is True
