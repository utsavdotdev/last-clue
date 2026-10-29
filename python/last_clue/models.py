"""Pydantic models and domain types for The Last Clue."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from pydantic import BaseModel, Field


class GamePhase(StrEnum):
    LOBBY = "LOBBY"
    ROLE_REVEAL = "ROLE_REVEAL"
    CLUE_ROUND = "CLUE_ROUND"
    DISCUSSION = "DISCUSSION"
    VOTING = "VOTING"
    RUNOFF = "RUNOFF"
    FINAL_GUESS = "FINAL_GUESS"
    RESULTS = "RESULTS"


class PlayerRole(StrEnum):
    SURVIVOR = "SURVIVOR"
    IMPOSTER = "IMPOSTER"


class WinnerSide(StrEnum):
    SURVIVORS = "SURVIVORS"
    IMPOSTER = "IMPOSTER"


class WinReason(StrEnum):
    IMPOSTER_CAUGHT_WRONG_GUESS = "IMPOSTER_CAUGHT_WRONG_GUESS"
    IMPOSTER_CAUGHT_GUESSED_WORD = "IMPOSTER_CAUGHT_GUESSED_WORD"
    IMPOSTER_ESCAPED_VOTE = "IMPOSTER_ESCAPED_VOTE"
    IMPOSTER_ESCAPED_RUNOFF_TIE = "IMPOSTER_ESCAPED_RUNOFF_TIE"


class GhostMatrixState(StrEnum):
    BOOT = "BOOT"
    LOBBY = "LOBBY"
    ROLES_ASSIGNED = "ROLES_ASSIGNED"
    CLUE_PHASE = "CLUE_PHASE"
    VOTING_PHASE = "VOTING_PHASE"
    RUNOFF = "RUNOFF"
    IMPOSTER_DISCOVERED = "IMPOSTER_DISCOVERED"
    SURVIVORS_WIN = "SURVIVORS_WIN"
    IMPOSTER_WINS = "IMPOSTER_WINS"
    IDLE = "IDLE"


class AIStatusState(StrEnum):
    READY = "READY"
    GENERATING = "GENERATING"
    FALLBACK = "FALLBACK"
    DISABLED = "DISABLED"


class WordEntry(BaseModel):
    word: str
    category: str
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    synonyms: list[str] = Field(default_factory=list)
    source: Literal["bundled", "ai"] = "bundled"


class ClueSubmission(BaseModel):
    player_id: str
    nickname: str
    clue: str
    turn_index: int
    round_pass: int = 1


class PublicPlayerView(BaseModel):
    player_id: str
    nickname: str
    connected: bool
    score: int
    ready_in_reveal: bool = False
    has_submitted_clue: bool = False
    has_voted: bool = False
    is_host: bool = False


class RoundOutcomeView(BaseModel):
    winner: WinnerSide
    reason: WinReason
    secret_word: str
    category: str
    imposter_id: str
    imposter_nickname: str
    accused_id: str | None = None
    accused_nickname: str | None = None
    imposter_final_guess: str | None = None
    imposter_guessed_correctly: bool = False
    vote_counts: dict[str, int] = Field(default_factory=dict)
    voter_breakdown: dict[str, str] = Field(default_factory=dict)
    score_deltas: dict[str, int] = Field(default_factory=dict)
    summary_text: str


class AIStatusView(BaseModel):
    status: AIStatusState
    model: str
    hardware_mode: Literal["uno_q_bridge", "simulated"]
    detail: str
    custom_words_count: int = 0


class MatrixPreviewView(BaseModel):
    state: GhostMatrixState
    state_code: int
    generation: int
    hardware_connected: bool
    label: str
    pixels: list[int] = Field(default_factory=list)


class PublicGameState(BaseModel):
    room_code: str
    phase: GamePhase
    round_number: int
    clue_round_number: int = 1
    min_players: int = 4
    max_players: int = 10
    players: list[PublicPlayerView]
    host_ready: bool
    selected_category: str | None = None
    available_categories: list[str] = Field(default_factory=list)
    active_category: str | None = None
    round_intro: str = ""
    narration: str = ""
    speaking_order: list[str] = Field(default_factory=list)
    current_speaker_id: str | None = None
    clues: list[ClueSubmission] = Field(default_factory=list)
    runoff_candidates: list[str] = Field(default_factory=list)
    accused_player_id: str | None = None
    votes_cast_count: int = 0
    eligible_voters_count: int = 0
    outcome: RoundOutcomeView | None = None
    ai_status: AIStatusView
    matrix: MatrixPreviewView


class PrivatePlayerPayload(BaseModel):
    player_id: str
    nickname: str
    is_host: bool = False
    role: PlayerRole | None = None
    category: str | None = None
    secret_word: str | None = None
    role_briefing: str | None = None
    has_voted_for: str | None = None
    can_submit_final_guess: bool = False


class JoinRoomRequest(BaseModel):
    nickname: str
    room_code: str | None = None
    reconnect_token: str | None = None
    as_host: bool = False


class JoinRoomResponse(BaseModel):
    player_id: str
    nickname: str
    room_code: str
    reconnect_token: str
    is_host: bool
    join_url: str


class HostSettingsUpdate(BaseModel):
    selected_category: str | None = None
    ai_enabled: bool | None = None
