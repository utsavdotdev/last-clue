"""Deterministic scoring logic for The Last Clue."""

from __future__ import annotations

from last_clue.models import WinnerSide

SURVIVOR_CORRECT_VOTE_POINTS = 1
IMPOSTER_WIN_POINTS = 2


def compute_round_scores(
    *,
    winner: WinnerSide,
    imposter_id: str,
    player_ids: list[str],
    final_votes: dict[str, str],
) -> dict[str, int]:
    """Compute score deltas for a completed round.

    Rules from docs.md:
    - Each Survivor who votes correctly for the Imposter earns 1 point when Survivors win.
    - The Imposter earns 2 points when the Imposter wins.
    """
    deltas = {pid: 0 for pid in player_ids}
    if winner == WinnerSide.IMPOSTER:
        if imposter_id in deltas:
            deltas[imposter_id] = IMPOSTER_WIN_POINTS
        return deltas

    for voter_id, target_id in final_votes.items():
        if voter_id != imposter_id and target_id == imposter_id and voter_id in deltas:
            deltas[voter_id] = SURVIVOR_CORRECT_VOTE_POINTS
    return deltas
