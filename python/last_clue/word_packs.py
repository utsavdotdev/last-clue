"""Bundled horror-themed word packs for The Last Clue."""

from __future__ import annotations

import re
from last_clue.models import WordEntry

BUNDLED_WORD_PACKS: tuple[WordEntry, ...] = (
    # Category 1: Horror creatures (10 words)
    WordEntry(
        word="Vampire",
        category="Horror Creatures",
        difficulty="easy",
        synonyms=["dracula", "nosferatu", "vampires"],
    ),
    WordEntry(
        word="Werewolf",
        category="Horror Creatures",
        difficulty="easy",
        synonyms=["lycanthrope", "wolfman", "werewolves"],
    ),
    WordEntry(
        word="Zombie",
        category="Horror Creatures",
        difficulty="easy",
        synonyms=["undead", "walker", "zombies"],
    ),
    WordEntry(
        word="Ghost",
        category="Horror Creatures",
        difficulty="easy",
        synonyms=["spirit", "specter", "spectre", "ghosts"],
    ),
    WordEntry(
        word="Witch",
        category="Horror Creatures",
        difficulty="easy",
        synonyms=["hag", "sorceress", "witches"],
    ),
    WordEntry(
        word="Demon",
        category="Horror Creatures",
        difficulty="medium",
        synonyms=["fiend", "devil", "demons"],
    ),
    WordEntry(
        word="Mummy",
        category="Horror Creatures",
        difficulty="easy",
        synonyms=["mummies", "wrapped pharaoh"],
    ),
    WordEntry(
        word="Phantom",
        category="Horror Creatures",
        difficulty="medium",
        synonyms=["wraith", "phantoms", "shade"],
    ),
    WordEntry(
        word="Banshee",
        category="Horror Creatures",
        difficulty="medium",
        synonyms=["wailing spirit", "banshees"],
    ),
    WordEntry(
        word="Skeleton",
        category="Horror Creatures",
        difficulty="easy",
        synonyms=["bones", "skeletons"],
    ),
    # Category 2: Haunted locations (10 words)
    WordEntry(
        word="Graveyard",
        category="Haunted Locations",
        difficulty="easy",
        synonyms=["cemetery", "churchyard", "burial ground"],
    ),
    WordEntry(
        word="Abandoned hospital",
        category="Haunted Locations",
        difficulty="medium",
        synonyms=["old hospital", "haunted hospital", "hospital ward"],
    ),
    WordEntry(
        word="Haunted mansion",
        category="Haunted Locations",
        difficulty="easy",
        synonyms=["manor", "haunted house", "haunted manor"],
    ),
    WordEntry(
        word="Creepy basement",
        category="Haunted Locations",
        difficulty="easy",
        synonyms=["cellar", "basement", "dark basement"],
    ),
    WordEntry(
        word="Abandoned school",
        category="Haunted Locations",
        difficulty="medium",
        synonyms=["old school", "haunted school"],
    ),
    WordEntry(
        word="Dark forest",
        category="Haunted Locations",
        difficulty="easy",
        synonyms=["haunted woods", "black forest", "cursed woods", "woods"],
    ),
    WordEntry(
        word="Haunted hotel",
        category="Haunted Locations",
        difficulty="medium",
        synonyms=["overlook hotel", "cursed hotel", "old motel"],
    ),
    WordEntry(
        word="Underground tunnel",
        category="Haunted Locations",
        difficulty="medium",
        synonyms=["catacombs", "subway tunnel", "dark tunnel", "tunnel"],
    ),
    WordEntry(
        word="Abandoned asylum",
        category="Haunted Locations",
        difficulty="medium",
        synonyms=["insane asylum", "sanitarium", "asylum"],
    ),
    WordEntry(
        word="Old church",
        category="Haunted Locations",
        difficulty="easy",
        synonyms=["chapel", "abandoned church", "cathedral"],
    ),
    # Category 3: Cursed objects (10 words)
    WordEntry(
        word="Ouija board",
        category="Cursed Objects",
        difficulty="easy",
        synonyms=["spirit board", "talking board", "ouija"],
    ),
    WordEntry(
        word="Cursed doll",
        category="Cursed Objects",
        difficulty="easy",
        synonyms=["haunted doll", "porcelain doll", "possessed doll"],
    ),
    WordEntry(
        word="Haunted mirror",
        category="Cursed Objects",
        difficulty="easy",
        synonyms=["cursed mirror", "antique mirror", "looking glass"],
    ),
    WordEntry(
        word="Bloody knife",
        category="Cursed Objects",
        difficulty="easy",
        synonyms=["ritual dagger", "rusty blade", "dagger"],
    ),
    WordEntry(
        word="Ancient spellbook",
        category="Cursed Objects",
        difficulty="medium",
        synonyms=["grimoire", "book of shadows", "spellbook", "spell book"],
    ),
    WordEntry(
        word="Crystal ball",
        category="Cursed Objects",
        difficulty="easy",
        synonyms=["scrying orb", "fortune orb", "glass orb"],
    ),
    WordEntry(
        word="Haunted portrait",
        category="Cursed Objects",
        difficulty="medium",
        synonyms=["cursed painting", "moving painting", "oil portrait"],
    ),
    WordEntry(
        word="Cursed necklace",
        category="Cursed Objects",
        difficulty="medium",
        synonyms=["amulet", "cursed locket", "haunted locket", "pendant"],
    ),
    WordEntry(
        word="Mysterious key",
        category="Cursed Objects",
        difficulty="easy",
        synonyms=["skeleton key", "iron key", "rusty key"],
    ),
    WordEntry(
        word="Vintage videotape",
        category="Cursed Objects",
        difficulty="medium",
        synonyms=["vhs tape", "vhs", "cassette tape"],
    ),
    # Category 4: Horror films and classic tropes (10 words)
    WordEntry(
        word="Jump scare",
        category="Horror Films and Classic Tropes",
        difficulty="easy",
        synonyms=["jumpscare", "sudden scare", "startle"],
    ),
    WordEntry(
        word="Final survivor",
        category="Horror Films and Classic Tropes",
        difficulty="medium",
        synonyms=["final girl", "sole survivor", "last survivor"],
    ),
    WordEntry(
        word="Haunted recording",
        category="Horror Films and Classic Tropes",
        difficulty="medium",
        synonyms=["evp", "voice recording", "ghostly audio"],
    ),
    WordEntry(
        word="Cursed videotape",
        category="Horror Films and Classic Tropes",
        difficulty="medium",
        synonyms=["cursed vhs", "ring tape", "forbidden tape"],
    ),
    WordEntry(
        word="Masked killer",
        category="Horror Films and Classic Tropes",
        difficulty="easy",
        synonyms=["slasher", "stalker", "masked stalker"],
    ),
    WordEntry(
        word="Forbidden room",
        category="Horror Films and Classic Tropes",
        difficulty="medium",
        synonyms=["locked room", "sealed room", "red room"],
    ),
    WordEntry(
        word="Creepy nursery",
        category="Horror Films and Classic Tropes",
        difficulty="medium",
        synonyms=["baby room", "haunted nursery", "nursery"],
    ),
    WordEntry(
        word="Secret passage",
        category="Horror Films and Classic Tropes",
        difficulty="easy",
        synonyms=["hidden hallway", "hidden door", "secret corridor"],
    ),
    WordEntry(
        word="Strange knocking",
        category="Horror Films and Classic Tropes",
        difficulty="easy",
        synonyms=["midnight knocking", "three knocks", "rapping at door"],
    ),
    WordEntry(
        word="Flickering lights",
        category="Horror Films and Classic Tropes",
        difficulty="easy",
        synonyms=["power outage", "dying bulb", "strobing light"],
    ),
    # Category 5: Supernatural events (10 words)
    WordEntry(
        word="Possession",
        category="Supernatural Events",
        difficulty="easy",
        synonyms=["demonic possession", "possessed"],
    ),
    WordEntry(
        word="Poltergeist",
        category="Supernatural Events",
        difficulty="medium",
        synonyms=["noisy ghost", "flying objects"],
    ),
    WordEntry(
        word="Exorcism",
        category="Supernatural Events",
        difficulty="easy",
        synonyms=["banishing ritual", "rite of exorcism"],
    ),
    WordEntry(
        word="Premonition",
        category="Supernatural Events",
        difficulty="medium",
        synonyms=["dark vision", "omen", "foreboding vision"],
    ),
    WordEntry(
        word="Apparition",
        category="Supernatural Events",
        difficulty="medium",
        synonyms=["manifestation", "spectral figure", "sighting"],
    ),
    WordEntry(
        word="Curse",
        category="Supernatural Events",
        difficulty="easy",
        synonyms=["hex", "jinx", "blood curse"],
    ),
    WordEntry(
        word="Seance",
        category="Supernatural Events",
        difficulty="easy",
        synonyms=["séance", "spirit circle", "summoning circle"],
    ),
    WordEntry(
        word="Telekinesis",
        category="Supernatural Events",
        difficulty="medium",
        synonyms=["psychokinesis", "mind movement"],
    ),
    WordEntry(
        word="Paranormal investigation",
        category="Supernatural Events",
        difficulty="medium",
        synonyms=["ghost hunt", "ghost hunting", "paranormal study"],
    ),
    WordEntry(
        word="Unexplained disappearance",
        category="Supernatural Events",
        difficulty="hard",
        synonyms=["vanishing", "missing person", "sudden disappearance"],
    ),
)


def normalize_guess_text(text: str) -> str:
    """Normalize text for case-insensitive, accent-tolerant word comparison."""
    cleaned = text.strip().casefold()
    cleaned = cleaned.replace("é", "e").replace("è", "e").replace("ê", "e")
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if cleaned.startswith("the "):
        cleaned = cleaned[4:].strip()
    if cleaned.startswith("a "):
        cleaned = cleaned[2:].strip()
    if cleaned.startswith("an "):
        cleaned = cleaned[3:].strip()
    return cleaned


def is_matching_guess(guess: str, entry: WordEntry) -> bool:
    """Return True if the Imposter's final guess matches the secret word or its synonyms."""
    normalized_guess = normalize_guess_text(guess)
    if not normalized_guess:
        return False
    accepted = {normalize_guess_text(entry.word)}
    for synonym in entry.synonyms:
        norm_syn = normalize_guess_text(synonym)
        if norm_syn:
            accepted.add(norm_syn)
    return normalized_guess in accepted


def list_categories(extra_entries: list[WordEntry] | None = None) -> list[str]:
    """Return all unique horror categories in deterministic order."""
    seen: set[str] = set()
    ordered: list[str] = []
    pool = list(BUNDLED_WORD_PACKS) + (extra_entries or [])
    for entry in pool:
        if entry.category not in seen:
            seen.add(entry.category)
            ordered.append(entry.category)
    return ordered


def entries_for_category(
    category: str | None = None,
    extra_entries: list[WordEntry] | None = None,
) -> list[WordEntry]:
    """Return all candidate WordEntry items matching the category (or all if None)."""
    pool = list(BUNDLED_WORD_PACKS) + (extra_entries or [])
    if not category or category.strip().lower() in {"any", "random", "all"}:
        return pool
    matched = [item for item in pool if item.category.casefold() == category.strip().casefold()]
    return matched if matched else pool
