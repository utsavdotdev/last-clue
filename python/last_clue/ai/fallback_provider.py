"""Deterministic built-in horror flavor provider when local AI is unavailable or disabled.

All strings follow strict anti-slop rules: zero em-dashes or en-dashes.
"""

from __future__ import annotations

import secrets

_RNG = secrets.SystemRandom()

CATEGORY_INTROS: dict[str, tuple[str, ...]] = {
    "Horror Creatures": (
        "Claw marks score the heavy oak door from the inside. Something in this room is only wearing a human face.",
        "The lantern flame bends toward one corner of the cellar. Listen closely to every voice before the candle dies.",
        "Footsteps echo one beat after everyone stops walking. One among you does not belong to the living.",
    ),
    "Haunted Locations": (
        "The floorboards remember every footstep that crossed this threshold. Tonight, one trespasser walks without a shadow.",
        "Cold air seeps from behind the sealed wallpaper. Someone in the circle is hiding why they came here.",
        "Thirty years of dust lie undisturbed on the stairs, except for a single set of tracks leading straight to us.",
    ),
    "Cursed Objects": (
        "The relic on the table hums whenever a lie is spoken. Watch your companions and weigh every clue.",
        "An iron lock snapped open at midnight without a key. One hand in this circle carries the curse.",
        "Whoever touched the artifact last left a cold fingerprint on the glass. Find the impostor before the final chime.",
    ),
    "Horror Films and Classic Tropes": (
        "Static fills the monitor in the corner of the room. Someone in this scene does not know how the reel ends.",
        "The basement fuse just blew, leaving only emergency red light. One voice in the dark is improvising their lines.",
        "A phone with a severed cord just rang once in the hallway. Test everyone in the circle.",
    ),
    "Supernatural Events": (
        "Every clock in the house stopped at the exact same second. One person here cannot read the omen.",
        "Frost forms across the inside of the windowpanes as the ritual begins. The spirits know who is pretending.",
        "A low whisper answers from the empty chair beside you. Speak one true clue and expose the outsider.",
    ),
}

DEFAULT_INTROS: tuple[str, ...] = (
    "The circle is sealed and the lantern grows dim. One among you does not know the secret word.",
    "Shadows gather along the walls of the chamber. Listen carefully to every clue spoken tonight.",
)

PHASE_NARRATIONS: dict[str, tuple[str, ...]] = {
    "ritual_start": (
        "The ritual begins. Guard your secret word and study every hesitation.",
        "Inspect your private dossier in silence. One player walks in the dark.",
    ),
    "clue_phase": (
        "The spirits are listening. Speak a single clue when your turn arrives.",
        "One of you does not know the word. Offer enough truth to prove yourself, and nothing more.",
    ),
    "clues_finished": (
        "All clues have been spoken into the dark. Question every alibi before the bell tolls.",
        "The testimony is complete. Look for the crack in the story.",
    ),
    "voting_start": (
        "Cast your secret ballot now. Point to the one who spoke hollow words.",
        "The hour of judgment has arrived. Mark the suspect in secret.",
    ),
    "runoff_start": (
        "The circle is divided. Vote once more between the tied suspects, or the Imposter slips away.",
    ),
    "imposter_discovered": (
        "The mask slips. The Imposter is cornered and has one final chance to name the secret word.",
    ),
    "survivors_win": (
        "The circle held firm and the deception failed. The Survivors endure the night.",
    ),
    "imposter_wins": (
        "Deceit triumphs in the dark. The Imposter claims the chamber.",
    ),
}


class FallbackHorrorProvider:
    """Provides atmospheric horror introductions and phase narrations without AI latency."""

    def get_round_intro(self, category: str) -> str:
        options = CATEGORY_INTROS.get(category, DEFAULT_INTROS)
        return _RNG.choice(options)

    def get_narration(self, event_key: str) -> str:
        options = PHASE_NARRATIONS.get(event_key, DEFAULT_INTROS)
        return _RNG.choice(options)
