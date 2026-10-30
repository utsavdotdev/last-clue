"""High-level AI orchestration service with caching, status tracking, and graceful fallback."""

from __future__ import annotations

import logging
import secrets
import threading
from last_clue.ai.fallback_provider import FallbackHorrorProvider
from last_clue.ai.local_provider import (
    LlamaServerClient,
    LocalHorrorProvider,
    is_local_model_url,
    sanitize_dashes,
)
from last_clue.models import AIStatusState, AIStatusView, WordEntry
from last_clue.word_packs import BUNDLED_WORD_PACKS, normalize_guess_text

logger = logging.getLogger(__name__)
_RNG = secrets.SystemRandom()

# Extra thematic horror words used as an instant local fallback pool when the
# on-board model is still warming up or unreachable, so "Generate" always succeeds.
FALLBACK_EXTRA_WORDS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("Bone Key", "Haunted Relics", ("skeleton key", "bone lock")),
    ("Weeping Statue", "Haunted Relics", ("stone angel", "crying statue")),
    ("Iron Coffin", "Haunted Relics", ("casket", "sarcophagus")),
    ("Plague Mask", "Haunted Relics", ("beak mask", "doctor mask")),
    ("Black Candle", "Haunted Relics", ("ritual candle", "wax candle")),
    ("Silver Dagger", "Haunted Relics", ("ritual blade", "silver knife")),
    ("Music Box", "Haunted Relics", ("windup box", "lullaby box")),
    ("Cracked Pendulum", "Haunted Relics", ("clock pendulum", "hypnosis pendulum")),
    ("Mothman", "Horror Creatures", ("winged cryptid", "red eyed moth")),
    ("Wendigo", "Horror Creatures", ("forest spirit", "antlered beast")),
    ("Shadow Person", "Supernatural Events", ("hat man", "corner shadow")),
    ("Bell Tower", "Haunted Locations", ("belfry", "church tower")),
)


class HauntedAIService:
    """Manages local open-weight model calls on UNO Q with deterministic fallback."""

    def __init__(
        self,
        *,
        llm_url: str,
        llm_model: str,
        timeout_seconds: float = 90.0,
        enabled: bool = True,
        hardware_connected: bool = False,
        local_provider: LocalHorrorProvider | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self.llm_url = llm_url
        self.llm_model = llm_model
        self.timeout_seconds = timeout_seconds
        self.enabled = enabled
        self.hardware_connected = hardware_connected
        self._fallback = FallbackHorrorProvider()
        self._local = (
            local_provider
            if local_provider is not None
            else LocalHorrorProvider(
                LlamaServerClient(url=llm_url, model=llm_model, timeout=timeout_seconds)
            )
        )
        self._status: AIStatusState = (
            AIStatusState.DISABLED if not enabled else AIStatusState.FALLBACK
        )
        self._detail: str = (
            "AI disabled by host"
            if not enabled
            else "Ready (built-in packs active; local model on standby)"
        )
        self._custom_words: list[WordEntry] = []
        self._intro_cache: dict[str, list[str]] = {}
        self._narration_cache: dict[str, str] = {}

    @property
    def custom_words(self) -> list[WordEntry]:
        with self._lock:
            return list(self._custom_words)

    def prefetch_round_flavor_async(
        self,
        *,
        category: str,
        secret_word: str,
        synonyms: list[str] | None = None,
    ) -> None:
        """Warm the intro and narration cache on a daemon thread without blocking gameplay."""
        if not self.enabled or not is_local_model_url(self.llm_url):
            return

        def _worker() -> None:
            try:
                intro, used_ai = self.get_round_intro(
                    category=category,
                    secret_word=secret_word,
                    synonyms=synonyms,
                    use_ai=True,
                )
                if used_ai:
                    with self._lock:
                        self._intro_cache.setdefault(category, []).append(intro)
            except Exception:
                pass

        threading.Thread(target=_worker, name="last-clue-ai-prefetch", daemon=True).start()

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self.enabled = enabled
            if not enabled:
                self._status = AIStatusState.DISABLED
                self._detail = "AI disabled - using built-in packs"
            elif self._status == AIStatusState.DISABLED:
                self._status = AIStatusState.FALLBACK
                self._detail = "AI enabled - ready for generation"

    def status_view(self) -> AIStatusView:
        with self._lock:
            return AIStatusView(
                status=self._status,
                model=self.llm_model,
                hardware_mode="uno_q_bridge" if self.hardware_connected else "simulated",
                detail=self._detail,
                custom_words_count=len(self._custom_words),
            )

    def get_round_intro(
        self,
        *,
        category: str,
        secret_word: str,
        synonyms: list[str] | None = None,
        use_ai: bool = False,
    ) -> tuple[str, bool]:
        """Return (intro_text, from_ai). Uses cached or live local AI when requested, else fallback."""
        if not self.enabled or not use_ai or not is_local_model_url(self.llm_url):
            return self._fallback.get_round_intro(category), False

        with self._lock:
            cached_list = self._intro_cache.get(category)
            if cached_list:
                from last_clue.ai.local_provider import validate_round_intro

                while cached_list:
                    candidate = cached_list.pop(0)
                    try:
                        valid = validate_round_intro(
                            candidate,
                            secret_word=secret_word,
                            synonyms=synonyms,
                        )
                        self._status = AIStatusState.READY
                        self._detail = f"Local AI active ({self.llm_model})"
                        return valid, True
                    except ValueError:
                        continue

            self._status = AIStatusState.GENERATING
            self._detail = f"Generating with {self.llm_model}..."

        try:
            intro = self._local.generate_round_intro(
                category=category,
                secret_word=secret_word,
                synonyms=synonyms,
            )
            with self._lock:
                self._status = AIStatusState.READY
                self._detail = f"Local AI active ({self.llm_model})"
            return intro, True
        except Exception as exc:
            logger.info("Local AI intro generation fell back to bundled content: %s", exc)
            with self._lock:
                self._status = AIStatusState.FALLBACK
                self._detail = "AI unavailable - using built-in content"
            return self._fallback.get_round_intro(category), False

    def get_narration(self, event_key: str, *, use_ai: bool = False, context: str = "") -> str:
        """Return spooky narration for a phase transition."""
        if not self.enabled or not use_ai or not is_local_model_url(self.llm_url):
            return self._fallback.get_narration(event_key)
        try:
            text = self._local.generate_narration(event_key=event_key, context=context)
            with self._lock:
                self._status = AIStatusState.READY
                self._detail = f"Local AI active ({self.llm_model})"
            return text
        except Exception:
            with self._lock:
                self._status = AIStatusState.FALLBACK
                self._detail = "AI unavailable - using built-in content"
            return self._fallback.get_narration(event_key)

    def _fallback_custom_words(self, category: str, count: int) -> list[WordEntry]:
        clean_cat = sanitize_dashes(category.strip() or "Haunted Relics")[:36]
        with self._lock:
            existing_pool = list(BUNDLED_WORD_PACKS) + list(self._custom_words)
        seen = {normalize_guess_text(item.word) for item in existing_pool}
        available = [
             WordEntry(
                word=w,
                category=clean_cat,
                difficulty="medium",
                synonyms=list(syns),
                source="ai",
            )
            for w, _default_cat, syns in FALLBACK_EXTRA_WORDS
            if normalize_guess_text(w) not in seen
        ]
        if not available:
            return []
        _RNG.shuffle(available)
        return available[: max(1, count)]

    def generate_custom_words(
        self,
        category: str = "Haunted Relics",
        count: int = 3,
        *,
        allow_fallback: bool = True,
    ) -> list[WordEntry]:
        """Request and validate a candidate word pack from the local model (with instant fallback)."""
        if not self.enabled:
            raise RuntimeError("Local AI is disabled in host settings")
        if not is_local_model_url(self.llm_url):
            raise RuntimeError("Refusing non-local model endpoint")

        with self._lock:
            self._status = AIStatusState.GENERATING
            self._detail = f"Generating words with {self.llm_model}..."
            existing = list(self._custom_words)

        try:
            entries = self._local.generate_word_pack(
                category=category,
                count=count,
                existing_entries=existing,
            )
            with self._lock:
                self._custom_words.extend(entries)
                self._status = AIStatusState.READY
                self._detail = f"Local AI active ({len(self._custom_words)} words saved)"
            return entries
        except Exception as exc:
            logger.info("Local AI word pack call fell back (%s)", exc)
            if allow_fallback:
                fallback_entries = self._fallback_custom_words(category, count)
                if fallback_entries:
                    with self._lock:
                        self._custom_words.extend(fallback_entries)
                        self._status = AIStatusState.FALLBACK
                        self._detail = f"Using built-in reserve ({len(self._custom_words)} words saved)"
                    return fallback_entries
            with self._lock:
                self._status = AIStatusState.FALLBACK
                self._detail = "Using built-in content"
            raise RuntimeError(f"AI word generation failed validation or timed out: {exc}") from exc
