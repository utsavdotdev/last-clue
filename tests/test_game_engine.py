"""Automated unit tests for The Last Clue game rules, privacy boundaries, and scoring."""

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


class FakeClock:
    def __init__(self, initial: float = 1000.0) -> None:
        self.now = initial

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _make_engine_with_players(count: int = 4) -> tuple[GameEngine, FakeClock, list[str]]:
    clock = FakeClock()
    engine = GameEngine(room_code="CRYPT1", clock=clock)
    pids: list[str] = []
    for idx in range(count):
        session = engine.join_player(f"Player{idx + 1}", as_host=(idx == 0))
        pids.append(session.player_id)
    return engine, clock, pids


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

    # Cannot start with only 3 players
    with pytest.raises(GameRuleError, match="At least 4"):
        engine.start_round()

    engine.join_player("Diana")
    engine.start_round()
    assert engine.phase == GamePhase.ROLE_REVEAL


def test_role_assignment_and_strict_private_payload_isolation() -> None:
    engine, _, pids = _make_engine_with_players(5)
    engine.start_round()

    public_state = engine.build_public_state()
    public_json = public_state.model_dump(mode="json")

    assert engine.active_word_entry is not None
    secret_word = engine.active_word_entry.word

    # Public state must NEVER contain the secret word or imposter_id during active play
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


def test_clue_round_turn_order_and_duplicate_submission_prevention() -> None:
    engine, _, pids = _make_engine_with_players(4)
    engine.start_round()

    # All players acknowledge role reveal -> automatically enters CLUE_ROUND
    for pid in pids:
        engine.mark_role_acknowledged(pid)

    assert engine.phase == GamePhase.CLUE_ROUND
    assert len(engine.speaking_order) == 4

    first_speaker = engine.current_speaker_id
    assert first_speaker is not None
    wrong_speaker = next(pid for pid in pids if pid != first_speaker)

    # Speaking out of turn is rejected
    with pytest.raises(GameRuleError, match="Wait for your turn"):
        engine.submit_clue(wrong_speaker, "Out of turn clue")

    # Overly long clue is rejected
    with pytest.raises(GameRuleError, match="40 characters"):
        engine.submit_clue(first_speaker, "x" * 45)

    # Submit valid clues in speaking order
    for idx, speaker_id in enumerate(list(engine.speaking_order)):
        assert engine.current_speaker_id == speaker_id
        engine.submit_clue(speaker_id, f"Spooky clue {idx + 1}")
        with pytest.raises(GameRuleError):
            engine.submit_clue(speaker_id, "Second clue attempt")

    assert engine.phase == GamePhase.DISCUSSION
    assert len(engine.clues) == 4


def test_voting_imposter_caught_wrong_final_guess_survivors_win() -> None:
    engine, _, pids = _make_engine_with_players(4)
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

    # Self-vote is forbidden
    with pytest.raises(GameRuleError, match="cannot vote for yourself"):
        engine.cast_vote(survivors[0], survivors[0])

    # 3 survivors vote for the Imposter; Imposter votes for survivor[0]
    for s_id in survivors:
        engine.cast_vote(s_id, imposter_id)

    # Duplicate vote is forbidden
    with pytest.raises(GameRuleError, match="already cast"):
        engine.cast_vote(survivors[0], survivors[1])

    engine.cast_vote(imposter_id, survivors[0])

    # All votes cast -> transitions to FINAL_GUESS because Imposter had majority
    assert engine.phase == GamePhase.FINAL_GUESS
    assert engine.accused_player_id == imposter_id
    assert engine.matrix.state == GhostMatrixState.IMPOSTER_DISCOVERED

    # Non-imposter cannot submit final guess
    with pytest.raises(GameRuleError, match="Only the discovered Imposter"):
        engine.submit_final_guess(survivors[0], "Vampire")

    # Imposter guesses wrong -> Survivors win (+1 point each for accurate voters)
    outcome = engine.submit_final_guess(imposter_id, "TotallyWrongWord999")
    assert engine.phase == GamePhase.RESULTS
    assert outcome.winner == WinnerSide.SURVIVORS
    assert outcome.reason == WinReason.IMPOSTER_CAUGHT_WRONG_GUESS
    assert engine.matrix.state == GhostMatrixState.SURVIVORS_WIN

    for s_id in survivors:
        assert engine.players[s_id].score == 1
    assert engine.players[imposter_id].score == 0


def test_voting_imposter_caught_correct_final_guess_or_synonym_imposter_wins() -> None:
    engine, _, pids = _make_engine_with_players(4)
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

    # Guess with different casing and leading article ("the ...")
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
    engine, _, pids = _make_engine_with_players(4)
    engine.start_round()
    engine.begin_clue_round()
    for speaker_id in list(engine.speaking_order):
        engine.submit_clue(speaker_id, "Dark shadow")
    engine.begin_voting()

    p0, p1, p2, p3 = pids
    # 2 votes for p0, 2 votes for p1 -> tie!
    engine.cast_vote(p0, p1)
    engine.cast_vote(p2, p1)
    engine.cast_vote(p1, p0)
    engine.cast_vote(p3, p0)

    assert engine.phase == GamePhase.RUNOFF
    assert set(engine.runoff_candidates) == {p0, p1}
    assert engine.matrix.state == GhostMatrixState.RUNOFF

    # Voting for someone not in runoff is rejected
    with pytest.raises(GameRuleError, match="tied candidates"):
        engine.cast_vote(p0, p2)

    # Tie again in runoff -> Imposter escapes and wins!
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


def test_Disconnect_and_reconnect_and_timer_expiration() -> None:
    engine, clock, pids = _make_engine_with_players(4)
    p0_session = engine.players[pids[0]]
    saved_token = p0_session.reconnect_token

    engine.start_round()
    engine.begin_clue_round()

    current = engine.current_speaker_id
    assert current is not None

    # Advance clock past clue timeout -> automatically skips speaker
    clock.advance(60.0)
    assert engine.check_and_advance_expired_timer() is True
    assert engine.clues[0].clue == "[Silence]"

    # Disconnect and reconnect using token
    engine.disconnect_player(pids[0])
    assert engine.players[pids[0]].connected is False
    rejoined = engine.join_player("IgnoredName", reconnect_token=saved_token)
    assert rejoined.player_id == pids[0]
    assert rejoined.connected is True
