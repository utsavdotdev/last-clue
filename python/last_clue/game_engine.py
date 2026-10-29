"""Server-authoritative multiplayer game engine for The Last Clue."""

from __future__ import annotations

from dataclasses import dataclass
import html
import re
import secrets
import time
from typing import Callable

from last_clue.ai.service import HauntedAIService
from last_clue.hardware.matrix_adapter import MatrixAdapter
from last_clue.models import (
    ClueSubmission,
    GamePhase,
    GhostMatrixState,
    PlayerRole,
    PrivatePlayerPayload,
    PublicGameState,
    PublicPlayerView,
    RoundOutcomeView,
    WinReason,
    WinnerSide,
    WordEntry,
)
from last_clue.scoring import compute_round_scores
from last_clue.word_packs import (
    entries_for_category,
    is_matching_guess,
    list_categories,
)

MIN_PLAYERS = 4
MAX_PLAYERS = 10
MAX_NICKNAME_LENGTH = 18
MAX_CLUE_LENGTH = 40
MAX_GUESS_LENGTH = 48


class GameRuleError(ValueError):
    """Raised when a client or host attempts an invalid action or state transition."""


@dataclass
class PlayerSession:
    player_id: str
    nickname: str
    reconnect_token: str
    connected: bool = True
    is_host: bool = False
    score: int = 0
    role: PlayerRole | None = None
    ready_in_reveal: bool = False
    submitted_clue: str | None = None
    voted_for: str | None = None


def normalize_nickname(raw: str) -> str:
    """Normalize and validate a player's nickname."""
    cleaned = re.sub(r"\s+", " ", raw.strip())
    cleaned = "".join(ch for ch in cleaned if ch.isprintable())
    if not cleaned:
        raise GameRuleError("Enter a nickname to join the room.")
    if len(cleaned) < 2:
        raise GameRuleError("Nickname must be at least 2 characters.")
    if len(cleaned) > MAX_NICKNAME_LENGTH:
        cleaned = cleaned[:MAX_NICKNAME_LENGTH].strip()
    return cleaned


def sanitize_clue_text(raw: str) -> str:
    """Normalize and validate a submitted clue."""
    cleaned = re.sub(r"\s+", " ", raw.strip())
    cleaned = "".join(ch for ch in cleaned if ch.isprintable())
    if not cleaned:
        raise GameRuleError("Clue cannot be empty.")
    if len(cleaned) > MAX_CLUE_LENGTH:
        raise GameRuleError(f"Clue must be {MAX_CLUE_LENGTH} characters or fewer.")
    return cleaned


class GameEngine:
    """Authoritative state machine for one Last Clue game room."""

    def __init__(
        self,
        *,
        room_code: str = "HAUNT6",
        matrix: MatrixAdapter | None = None,
        ai_service: HauntedAIService | None = None,
        discussion_seconds: int = 60,
        voting_seconds: int = 45,
        clue_timeout_seconds: int = 45,
        final_guess_seconds: int = 35,
        clock: Callable[[], float] = time.monotonic,
        rng: secrets.SystemRandom | None = None,
    ) -> None:
        self.room_code = room_code.upper()
        self.matrix = matrix if matrix is not None else MatrixAdapter()
        self.ai_service = ai_service
        self.discussion_seconds = discussion_seconds
        self.voting_seconds = voting_seconds
        self.clue_timeout_seconds = clue_timeout_seconds
        self.final_guess_seconds = final_guess_seconds
        self._clock = clock
        self._rng = rng if rng is not None else secrets.SystemRandom()

        self.host_token: str = secrets.token_urlsafe(18)
        self.phase: GamePhase = GamePhase.LOBBY
        self.round_number: int = 0
        self.players: dict[str, PlayerSession] = {}
        self.player_order: list[str] = []

        self.selected_category: str | None = None
        self.active_word_entry: WordEntry | None = None
        self.imposter_id: str | None = None
        self.round_intro: str = ""
        self.narration: str = "Gather 4 to 10 investigators in the lobby to begin the ritual."

        self.speaking_order: list[str] = []
        self.current_speaker_index: int = 0
        self.clues: list[ClueSubmission] = []

        self.votes: dict[str, str] = {}
        self.runoff_candidates: list[str] = []
        self.accused_player_id: str | None = None
        self.imposter_final_guess: str | None = None
        self.outcome: RoundOutcomeView | None = None

        self.phase_deadline: float | None = None
        self.phase_total_seconds: int | None = None
        self._used_words: set[str] = set()

        self.matrix.set_state(GhostMatrixState.LOBBY)

    # --- Player & Lobby Management ---

    def join_player(
        self,
        nickname: str,
        *,
        reconnect_token: str | None = None,
        as_host: bool = False,
    ) -> PlayerSession:
        """Join a new player or reconnect an existing session by token."""
        if reconnect_token:
            for existing in self.players.values():
                if secrets.compare_digest(existing.reconnect_token, reconnect_token):
                    existing.connected = True
                    return existing

        norm_name = normalize_nickname(nickname)

        # Allow reconnecting by matching nickname if that slot is currently disconnected
        for existing in self.players.values():
            if existing.nickname.casefold() == norm_name.casefold():
                if not existing.connected:
                    existing.connected = True
                    return existing
                raise GameRuleError(f"Nickname '{norm_name}' is already taken in this room.")

        if self.phase != GamePhase.LOBBY:
            raise GameRuleError("Cannot join as a new player while a round is in progress.")
        if len(self.players) >= MAX_PLAYERS:
            raise GameRuleError(f"Room is full (maximum {MAX_PLAYERS} players).")

        player_id = f"p_{secrets.token_hex(4)}"
        token = secrets.token_urlsafe(16)
        has_any_host = any(p.is_host for p in self.players.values())
        is_host = bool(as_host or not has_any_host)

        session = PlayerSession(
            player_id=player_id,
            nickname=norm_name,
            reconnect_token=token,
            connected=True,
            is_host=is_host,
        )
        self.players[player_id] = session
        self.player_order.append(player_id)
        return session

    def authenticate_player(self, player_id: str, token: str) -> PlayerSession:
        player = self.players.get(player_id)
        if player is None or not secrets.compare_digest(player.reconnect_token, token):
            raise GameRuleError("Invalid player credentials.")
        return player

    def is_authorized_host(self, *, player_id: str | None = None, token: str | None = None) -> bool:
        if token and secrets.compare_digest(token, self.host_token):
            return True
        if player_id and token:
            player = self.players.get(player_id)
            if (
                player is not None
                and player.is_host
                and secrets.compare_digest(player.reconnect_token, token)
            ):
                return True
        return False

    def require_host(self, *, player_id: str | None = None, token: str | None = None) -> None:
        if not self.is_authorized_host(player_id=player_id, token=token):
            raise GameRuleError("Only the host can perform this action.")

    def disconnect_player(self, player_id: str) -> None:
        player = self.players.get(player_id)
        if player is None:
            return
        player.connected = False
        if player.is_host:
            # Promote another connected player if host disconnects so the room is never stranded
            for candidate_id in self.player_order:
                cand = self.players[candidate_id]
                if cand.connected and cand.player_id != player_id:
                    cand.is_host = True
                    break

        if self.phase == GamePhase.CLUE_ROUND and self.current_speaker_id == player_id:
            self._advance_speaker_or_discussion()
        elif self.phase in {GamePhase.VOTING, GamePhase.RUNOFF}:
            self._check_all_votes_in()

    def leave_player(self, player_id: str) -> None:
        if player_id not in self.players:
            return
        if self.phase == GamePhase.LOBBY:
            was_host = self.players[player_id].is_host
            del self.players[player_id]
            self.player_order = [pid for pid in self.player_order if pid != player_id]
            if was_host and self.player_order:
                self.players[self.player_order[0]].is_host = True
        else:
            self.disconnect_player(player_id)

    def update_settings(
        self,
        *,
        selected_category: str | None = None,
        discussion_seconds: int | None = None,
        voting_seconds: int | None = None,
        ai_enabled: bool | None = None,
    ) -> None:
        if selected_category is not None:
            cat = selected_category.strip()
            self.selected_category = None if cat.lower() in {"", "any", "random"} else cat
        if discussion_seconds is not None:
            if not 10 <= discussion_seconds <= 300:
                raise GameRuleError("Discussion timer must be between 10 and 300 seconds.")
            self.discussion_seconds = discussion_seconds
        if voting_seconds is not None:
            if not 10 <= voting_seconds <= 300:
                raise GameRuleError("Voting timer must be between 10 and 300 seconds.")
            self.voting_seconds = voting_seconds
        if ai_enabled is not None and self.ai_service is not None:
            self.ai_service.set_enabled(ai_enabled)

    # --- Round Lifecycle & Phases ---

    def connected_player_ids(self) -> list[str]:
        return [pid for pid in self.player_order if self.players[pid].connected]

    def start_round(self, *, use_ai_intro: bool = False) -> None:
        if self.phase not in {GamePhase.LOBBY, GamePhase.RESULTS}:
            raise GameRuleError("A round can only start from the lobby or results screen.")

        active_ids = self.connected_player_ids()
        if len(active_ids) < MIN_PLAYERS:
            raise GameRuleError(f"At least {MIN_PLAYERS} connected players are required to start.")
        if len(active_ids) > MAX_PLAYERS:
            raise GameRuleError(f"Maximum {MAX_PLAYERS} players allowed.")

        self.round_number += 1
        extra_words = self.ai_service.custom_words if self.ai_service is not None else []
        candidates = entries_for_category(self.selected_category, extra_entries=extra_words)
        unused = [w for w in candidates if w.word.casefold() not in self._used_words]
        if not unused:
            self._used_words.clear()
            unused = candidates

        chosen_entry = self._rng.choice(unused)
        self._used_words.add(chosen_entry.word.casefold())
        self.active_word_entry = chosen_entry

        # Select exactly 1 Imposter using cryptographically secure randomness
        self.imposter_id = self._rng.choice(active_ids)

        # Reset per-round player state
        for pid in self.player_order:
            p = self.players[pid]
            p.ready_in_reveal = False
            p.submitted_clue = None
            p.voted_for = None
            if pid in active_ids:
                p.role = (
                    PlayerRole.IMPOSTER if pid == self.imposter_id else PlayerRole.SURVIVOR
                )
            else:
                p.role = None

        # Randomize speaking order
        shuffled_order = list(active_ids)
        self._rng.shuffle(shuffled_order)
        self.speaking_order = shuffled_order
        self.current_speaker_index = 0
        self.clues = []
        self.votes = {}
        self.runoff_candidates = []
        self.accused_player_id = None
        self.imposter_final_guess = None
        self.outcome = None

        if self.ai_service is not None:
            intro, _ = self.ai_service.get_round_intro(
                category=chosen_entry.category,
                secret_word=chosen_entry.word,
                synonyms=chosen_entry.synonyms,
                use_ai=use_ai_intro,
            )
            self.round_intro = intro
            self.narration = self.ai_service.get_narration("ritual_start")
        else:
            self.round_intro = (
                "The circle is sealed and the lantern grows dim. "
                "One among you does not know the secret word."
            )
            self.narration = "Inspect your private dossier in silence."

        self.phase = GamePhase.ROLE_REVEAL
        self._set_timer(None)
        self.matrix.set_state(GhostMatrixState.ROLES_ASSIGNED)

    def mark_role_acknowledged(self, player_id: str) -> None:
        if self.phase != GamePhase.ROLE_REVEAL:
            raise GameRuleError("Role confirmation is only valid during Role Reveal.")
        player = self.players.get(player_id)
        if player is None or player.role is None:
            raise GameRuleError("Player is not active in this round.")
        player.ready_in_reveal = True

        active_participants = [
            self.players[pid]
            for pid in self.speaking_order
            if self.players[pid].connected
        ]
        if active_participants and all(p.ready_in_reveal for p in active_participants):
            self.begin_clue_round()

    def begin_clue_round(self) -> None:
        if self.phase != GamePhase.ROLE_REVEAL:
            raise GameRuleError("Clue round can only start after Role Reveal.")
        self.phase = GamePhase.CLUE_ROUND
        self.current_speaker_index = 0
        self._skip_disconnected_speakers()
        if self.phase == GamePhase.CLUE_ROUND:
            self._set_timer(self.clue_timeout_seconds)
            self.narration = (
                self.ai_service.get_narration("clue_phase")
                if self.ai_service is not None
                else "The spirits are listening. One of you does not know the word."
            )
            self.matrix.set_state(GhostMatrixState.CLUE_PHASE)

    @property
    def current_speaker_id(self) -> str | None:
        if self.phase != GamePhase.CLUE_ROUND:
            return None
        if 0 <= self.current_speaker_index < len(self.speaking_order):
            return self.speaking_order[self.current_speaker_index]
        return None

    def submit_clue(self, player_id: str, raw_clue: str) -> ClueSubmission:
        if self.phase != GamePhase.CLUE_ROUND:
            raise GameRuleError("Clues can only be submitted during the Clue Round.")
        player = self.players.get(player_id)
        if player is None or player.role is None:
            raise GameRuleError("You are not an active participant in this round.")
        if player.submitted_clue is not None:
            raise GameRuleError("You have already submitted a clue this round.")
        if self.current_speaker_id != player_id:
            raise GameRuleError("Wait for your turn to submit a clue.")

        cleaned_clue = sanitize_clue_text(raw_clue)
        player.submitted_clue = cleaned_clue
        submission = ClueSubmission(
            player_id=player_id,
            nickname=player.nickname,
            clue=cleaned_clue,
            turn_index=len(self.clues) + 1,
        )
        self.clues.append(submission)
        self.current_speaker_index += 1
        self._advance_speaker_or_discussion()
        return submission

    def skip_current_speaker(self) -> None:
        """Host or timer skip when the current speaker disconnects or times out."""
        if self.phase != GamePhase.CLUE_ROUND:
            raise GameRuleError("Not in Clue Round.")
        speaker_id = self.current_speaker_id
        if speaker_id is None:
            self._begin_discussion()
            return
        speaker = self.players[speaker_id]
        if speaker.submitted_clue is None:
            speaker.submitted_clue = "[Silence]"
            self.clues.append(
                ClueSubmission(
                    player_id=speaker_id,
                    nickname=speaker.nickname,
                    clue="[Silence]",
                    turn_index=len(self.clues) + 1,
                )
            )
        self.current_speaker_index += 1
        self._advance_speaker_or_discussion()

    def _skip_disconnected_speakers(self) -> None:
        while self.current_speaker_index < len(self.speaking_order):
            speaker_id = self.speaking_order[self.current_speaker_index]
            speaker = self.players[speaker_id]
            if speaker.connected and speaker.submitted_clue is None:
                return
            if speaker.submitted_clue is None:
                speaker.submitted_clue = "[Disconnected]"
                self.clues.append(
                    ClueSubmission(
                        player_id=speaker_id,
                        nickname=speaker.nickname,
                        clue="[Disconnected]",
                        turn_index=len(self.clues) + 1,
                    )
                )
            self.current_speaker_index += 1

    def _advance_speaker_or_discussion(self) -> None:
        self._skip_disconnected_speakers()
        if self.current_speaker_index >= len(self.speaking_order):
            self._begin_discussion()
        else:
            self._set_timer(self.clue_timeout_seconds)

    def _begin_discussion(self) -> None:
        self.phase = GamePhase.DISCUSSION
        self._set_timer(self.discussion_seconds)
        self.narration = (
            self.ai_service.get_narration("clues_finished")
            if self.ai_service is not None
            else "All clues have been spoken. Question every alibi before voting begins."
        )
        self.matrix.set_state(GhostMatrixState.CLUE_PHASE)

    def begin_voting(self) -> None:
        if self.phase != GamePhase.DISCUSSION:
            raise GameRuleError("Voting can only begin from the Discussion phase.")
        self.phase = GamePhase.VOTING
        self.votes = {}
        for p in self.players.values():
            p.voted_for = None
        self._set_timer(self.voting_seconds)
        self.narration = (
            self.ai_service.get_narration("voting_start")
            if self.ai_service is not None
            else "Cast your secret vote now. You cannot vote for yourself."
        )
        self.matrix.set_state(GhostMatrixState.VOTING_PHASE)

    def eligible_voter_ids(self) -> list[str]:
        return [
            pid
            for pid in self.speaking_order
            if self.players[pid].connected and self.players[pid].role is not None
        ]

    def cast_vote(self, voter_id: str, target_id: str) -> None:
        if self.phase not in {GamePhase.VOTING, GamePhase.RUNOFF}:
            raise GameRuleError("Voting is not currently open.")
        voter = self.players.get(voter_id)
        if voter is None or voter.role is None:
            raise GameRuleError("You are not eligible to vote in this round.")
        if voter_id in self.votes:
            raise GameRuleError("You have already cast your vote.")
        if voter_id == target_id:
            raise GameRuleError("You cannot vote for yourself.")
        if target_id not in self.speaking_order:
            raise GameRuleError("Selected player is not in this round.")
        if self.phase == GamePhase.RUNOFF and target_id not in self.runoff_candidates:
            raise GameRuleError("In a runoff vote, you must choose one of the tied candidates.")

        self.votes[voter_id] = target_id
        voter.voted_for = target_id
        self._check_all_votes_in()

    def _check_all_votes_in(self) -> None:
        eligible = set(self.eligible_voter_ids())
        if eligible and eligible.issubset(self.votes.keys()):
            self.finalize_voting()

    def finalize_voting(self) -> None:
        """Tally votes on the server and transition to Runoff, Final Guess, or Results."""
        if self.phase not in {GamePhase.VOTING, GamePhase.RUNOFF}:
            raise GameRuleError("Cannot tally votes outside Voting or Runoff phase.")

        # Only count votes from connected players or already-submitted valid ballots
        tallies: dict[str, int] = {pid: 0 for pid in self.speaking_order}
        if self.phase == GamePhase.RUNOFF:
            tallies = {pid: 0 for pid in self.runoff_candidates}

        for voter_id, target_id in self.votes.items():
            if target_id in tallies:
                tallies[target_id] += 1

        max_votes = max(tallies.values()) if tallies else 0
        if max_votes == 0:
            # No votes cast at all -> Imposter escapes
            self._complete_round(
                winner=WinnerSide.IMPOSTER,
                reason=(
                    WinReason.IMPOSTER_ESCAPED_RUNOFF_TIE
                    if self.phase == GamePhase.RUNOFF
                    else WinReason.IMPOSTER_ESCAPED_VOTE
                ),
                accused_id=None,
                vote_counts=tallies,
            )
            return

        top_candidates = [pid for pid, count in tallies.items() if count == max_votes]

        if len(top_candidates) == 1:
            accused_id = top_candidates[0]
            self.accused_player_id = accused_id
            if accused_id == self.imposter_id:
                self.phase = GamePhase.FINAL_GUESS
                self._set_timer(self.final_guess_seconds)
                self.narration = (
                    self.ai_service.get_narration("imposter_discovered")
                    if self.ai_service is not None
                    else "The Imposter has been caught. They get one final guess at the secret word."
                )
                self.matrix.set_state(GhostMatrixState.IMPOSTER_DISCOVERED)
            else:
                self._complete_round(
                    winner=WinnerSide.IMPOSTER,
                    reason=WinReason.IMPOSTER_ESCAPED_VOTE,
                    accused_id=accused_id,
                    vote_counts=tallies,
                )
            return

        # Multiple candidates tied for highest votes
        if self.phase == GamePhase.VOTING:
            self.phase = GamePhase.RUNOFF
            self.runoff_candidates = top_candidates
            self.votes = {}
            for p in self.players.values():
                p.voted_for = None
            self._set_timer(self.voting_seconds)
            self.narration = (
                self.ai_service.get_narration("runoff_start")
                if self.ai_service is not None
                else "Tie vote detected. Cast one runoff ballot between the tied suspects."
            )
            self.matrix.set_state(GhostMatrixState.RUNOFF)
        else:
            # Runoff is still tied -> no one is caught and Imposter escapes
            self._complete_round(
                winner=WinnerSide.IMPOSTER,
                reason=WinReason.IMPOSTER_ESCAPED_RUNOFF_TIE,
                accused_id=None,
                vote_counts=tallies,
            )

    def submit_final_guess(self, player_id: str, raw_guess: str) -> RoundOutcomeView:
        if self.phase != GamePhase.FINAL_GUESS:
            raise GameRuleError("Final guess is only allowed when the Imposter is accused.")
        if player_id != self.imposter_id:
            raise GameRuleError("Only the discovered Imposter may submit the final word guess.")
        if self.imposter_final_guess is not None:
            raise GameRuleError("Final guess has already been submitted.")

        cleaned_guess = re.sub(r"\s+", " ", raw_guess.strip())[:MAX_GUESS_LENGTH]
        if not cleaned_guess:
            raise GameRuleError("Enter a word for your final guess.")

        self.imposter_final_guess = cleaned_guess
        assert self.active_word_entry is not None
        guessed_right = is_matching_guess(cleaned_guess, self.active_word_entry)

        tallies: dict[str, int] = {pid: 0 for pid in self.speaking_order}
        for target_id in self.votes.values():
            if target_id in tallies:
                tallies[target_id] += 1

        if guessed_right:
            self._complete_round(
                winner=WinnerSide.IMPOSTER,
                reason=WinReason.IMPOSTER_CAUGHT_GUESSED_WORD,
                accused_id=self.accused_player_id,
                vote_counts=tallies,
                imposter_guess=cleaned_guess,
                guessed_correctly=True,
            )
        else:
            self._complete_round(
                winner=WinnerSide.SURVIVORS,
                reason=WinReason.IMPOSTER_CAUGHT_WRONG_GUESS,
                accused_id=self.accused_player_id,
                vote_counts=tallies,
                imposter_guess=cleaned_guess,
                guessed_correctly=False,
            )
        assert self.outcome is not None
        return self.outcome

    def _complete_round(
        self,
        *,
        winner: WinnerSide,
        reason: WinReason,
        accused_id: str | None,
        vote_counts: dict[str, int],
        imposter_guess: str | None = None,
        guessed_correctly: bool = False,
    ) -> None:
        assert self.active_word_entry is not None
        assert self.imposter_id is not None

        deltas = compute_round_scores(
            winner=winner,
            imposter_id=self.imposter_id,
            player_ids=self.speaking_order,
            final_votes=self.votes,
        )
        for pid, delta in deltas.items():
            if pid in self.players:
                self.players[pid].score += delta

        imposter_name = self.players[self.imposter_id].nickname
        accused_name = self.players[accused_id].nickname if accused_id in self.players else None

        if reason == WinReason.IMPOSTER_CAUGHT_WRONG_GUESS:
            summary = (
                f"Survivors caught {imposter_name}, whose final guess "
                f"('{imposter_guess or 'none'}') missed '{self.active_word_entry.word}'."
            )
        elif reason == WinReason.IMPOSTER_CAUGHT_GUESSED_WORD:
            summary = (
                f"{imposter_name} was caught by the vote, but stole victory by guessing "
                f"'{self.active_word_entry.word}'."
            )
        elif reason == WinReason.IMPOSTER_ESCAPED_RUNOFF_TIE:
            summary = (
                f"The runoff vote ended in a deadlock. {imposter_name} slipped into the dark "
                f"while the secret word was '{self.active_word_entry.word}'."
            )
        else:
            if accused_name:
                summary = (
                    f"The circle wrongly accused {accused_name}. "
                    f"The true Imposter was {imposter_name}."
                )
            else:
                summary = f"No suspect was convicted. The Imposter {imposter_name} escaped."

        self.outcome = RoundOutcomeView(
            winner=winner,
            reason=reason,
            secret_word=self.active_word_entry.word,
            category=self.active_word_entry.category,
            imposter_id=self.imposter_id,
            imposter_nickname=imposter_name,
            accused_id=accused_id,
            accused_nickname=accused_name,
            imposter_final_guess=imposter_guess,
            imposter_guessed_correctly=guessed_correctly,
            vote_counts=vote_counts,
            voter_breakdown=dict(self.votes),
            score_deltas=deltas,
            summary_text=summary,
        )
        self.phase = GamePhase.RESULTS
        self._set_timer(None)

        if winner == WinnerSide.SURVIVORS:
            self.narration = (
                self.ai_service.get_narration("survivors_win")
                if self.ai_service is not None
                else "The Survivors exposed the deception and endured the night."
            )
            self.matrix.set_state(GhostMatrixState.SURVIVORS_WIN)
        else:
            self.narration = (
                self.ai_service.get_narration("imposter_wins")
                if self.ai_service is not None
                else "Deceit triumphs in the dark. The Imposter wins the round."
            )
            self.matrix.set_state(GhostMatrixState.IMPOSTER_WINS)

    def return_to_lobby(self) -> None:
        self.phase = GamePhase.LOBBY
        self.active_word_entry = None
        self.imposter_id = None
        self.speaking_order = []
        self.current_speaker_index = 0
        self.clues = []
        self.votes = {}
        self.runoff_candidates = []
        self.accused_player_id = None
        self.imposter_final_guess = None
        self.outcome = None
        self._set_timer(None)
        for p in self.players.values():
            p.role = None
            p.ready_in_reveal = False
            p.submitted_clue = None
            p.voted_for = None
        self.narration = "Back in the lobby. Ready for the next round."
        self.matrix.set_state(GhostMatrixState.LOBBY)

    def reset_scores(self) -> None:
        for p in self.players.values():
            p.score = 0

    # --- Server Timer Management ---

    def _set_timer(self, seconds: int | None) -> None:
        if seconds is None:
            self.phase_deadline = None
            self.phase_total_seconds = None
        else:
            self.phase_total_seconds = seconds
            self.phase_deadline = self._clock() + float(seconds)

    def timer_remaining(self) -> int | None:
        if self.phase_deadline is None:
            return None
        remaining = int(round(self.phase_deadline - self._clock()))
        return max(0, remaining)

    def check_and_advance_expired_timer(self) -> bool:
        """Advance the state machine if the active phase timer has expired. Returns True if changed."""
        if self.phase_deadline is None:
            return False
        if self._clock() < self.phase_deadline:
            return False

        if self.phase == GamePhase.CLUE_ROUND:
            self.skip_current_speaker()
            return True
        if self.phase == GamePhase.DISCUSSION:
            self.begin_voting()
            return True
        if self.phase in {GamePhase.VOTING, GamePhase.RUNOFF}:
            self.finalize_voting()
            return True
        if self.phase == GamePhase.FINAL_GUESS:
            tallies: dict[str, int] = {pid: 0 for pid in self.speaking_order}
            for target_id in self.votes.values():
                if target_id in tallies:
                    tallies[target_id] += 1
            self._complete_round(
                winner=WinnerSide.SURVIVORS,
                reason=WinReason.IMPOSTER_CAUGHT_WRONG_GUESS,
                accused_id=self.accused_player_id,
                vote_counts=tallies,
                imposter_guess="[Timed out]",
                guessed_correctly=False,
            )
            return True
        return False

    # --- Public & Private State Projections (Zero Secret Leakage) ---

    def build_public_state(self) -> PublicGameState:
        """Build the shared public game state. Never includes active secret word or player roles."""
        players_view = [
            PublicPlayerView(
                player_id=p.player_id,
                nickname=html.escape(p.nickname, quote=False),
                connected=p.connected,
                score=p.score,
                ready_in_reveal=p.ready_in_reveal,
                has_submitted_clue=p.submitted_clue is not None,
                has_voted=p.player_id in self.votes,
                is_host=p.is_host,
            )
            for pid in self.player_order
            if (p := self.players[pid])
        ]
        connected_count = sum(1 for p in self.players.values() if p.connected)
        extra_words = self.ai_service.custom_words if self.ai_service is not None else []
        ai_view = (
            self.ai_service.status_view()
            if self.ai_service is not None
            else HauntedAIService(
                llm_url="http://localhost:9999",
                llm_model="Qwen3.5-0.8B-Q4_0",
                enabled=False,
            ).status_view()
        )
        return PublicGameState(
            room_code=self.room_code,
            phase=self.phase,
            round_number=self.round_number,
            min_players=MIN_PLAYERS,
            max_players=MAX_PLAYERS,
            players=players_view,
            host_ready=connected_count >= MIN_PLAYERS,
            selected_category=self.selected_category,
            available_categories=list_categories(extra_entries=extra_words),
            active_category=(
                self.active_word_entry.category if self.active_word_entry is not None else None
            ),
            round_intro=self.round_intro,
            narration=self.narration,
            speaking_order=list(self.speaking_order),
            current_speaker_id=self.current_speaker_id,
            clues=list(self.clues),
            runoff_candidates=list(self.runoff_candidates),
            accused_player_id=self.accused_player_id,
            votes_cast_count=len(self.votes),
            eligible_voters_count=len(self.eligible_voter_ids()),
            timer_seconds_remaining=self.timer_remaining(),
            timer_total_seconds=self.phase_total_seconds,
            discussion_seconds=self.discussion_seconds,
            voting_seconds=self.voting_seconds,
            outcome=self.outcome if self.phase == GamePhase.RESULTS else None,
            ai_status=ai_view,
            matrix=self.matrix.snapshot(),
        )

    def build_private_payload(self, player_id: str) -> PrivatePlayerPayload:
        """Build the confidential per-player state.

        - Survivors receive their role, category, and secret_word.
        - The Imposter receives their role and category ONLY; secret_word is strictly None.
        """
        player = self.players.get(player_id)
        if player is None:
            raise GameRuleError("Unknown player.")

        category = self.active_word_entry.category if self.active_word_entry else None
        secret_word: str | None = None
        briefing: str | None = None

        if player.role == PlayerRole.SURVIVOR and self.active_word_entry is not None:
            secret_word = self.active_word_entry.word
            briefing = f"Your secret word is {secret_word.upper()}."
        elif player.role == PlayerRole.IMPOSTER and category is not None:
            secret_word = None
            briefing = (
                f"You are the IMPOSTER. The category is {category.upper()}. "
                "Blend in, discover the secret word, and avoid detection."
            )

        return PrivatePlayerPayload(
            player_id=player.player_id,
            nickname=player.nickname,
            is_host=player.is_host,
            role=player.role,
            category=category,
            secret_word=secret_word,
            role_briefing=briefing,
            has_voted_for=self.votes.get(player_id),
            can_submit_final_guess=(
                self.phase == GamePhase.FINAL_GUESS and player_id == self.imposter_id
            ),
        )
