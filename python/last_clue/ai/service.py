"""High-level AI orchestration service with caching, status tracking, and graceful fallback."""

from __future__ import annotations

import logging
import threading
from last_clue.ai.fallback_provider import FallbackHorrorProvider
from last_clue.ai.local_provider import (
    LlamaServerClient,
    LocalHorrorProvider,
    is_local_model_url,
)
from last_clue.models import AIStatusState, AIStatusView, WordEntry

logger = logging.getLogger(__name__)


class HauntedAIService:
    """Manages local open-weight model calls on UNO Q with deterministic fallback."""

    def __init__(
        self,
        *,
        llm_url: str,
        llm_model: str,
        timeout_seconds: float = 25.0,
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
            AIStatusState.FALLBACK if not enabled else AIStatusState.FALLBACK
        )
        self._detail: str = (
            "AI disabled by host - using built-in content"
            if not enabled
            else "AI standby - using built-in content until local model responds"
        )
        self._custom_words: list[WordEntry] = []

    @property
    def custom_words(self) -> list[WordEntry]:
        with self._lock:
            return list(self._custom_words)

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self.enabled = enabled
            if not enabled:
                self._status = AIStatusState.DISABLED
                self._detail = "AI disabled by host - using built-in content"
            elif self._status == AIStatusState.DISABLED:
                self._status = AIStatusState.FALLBACK
                self._detail = "AI enabled - awaiting next local inference"

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
        """Return (intro_text, from_ai). Uses fast fallback unless use_ai is requested and enabled."""
        if not self.enabled or not use_ai or not is_local_model_url(self.llm_url):
            return self._fallback.get_round_intro(category), False

        with self._lock:
            self._status = AIStatusState.GENERATING
            self._detail = f"Generating intro with local {self.llm_model}..."

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

    def generate_custom_words(self, category: str = "Haunted Relics", count: int = 3) -> list[WordEntry]:
        """Synchronously request and validate a candidate word pack from the local model."""
        if not self.enabled:
            raise RuntimeError("Local AI is disabled in host settings")
        if not is_local_model_url(self.llm_url):
            raise RuntimeError("Refusing non-local model endpoint")

        with self._lock:
            self._status = AIStatusState.GENERATING
            self._detail = f"Summoning candidate words from {self.llm_model}..."
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
                self._detail = f"Local AI active ({self.llm_model}) - {len(self._custom_words)} AI words cached"
            return entries
        except Exception as exc:
            with self._lock:
                self._status = AIStatusState.FALLBACK
                self._detail = "AI unavailable - using built-in content"
            raise RuntimeError(f"AI word generation failed validation or timed out: {exc}") from exc
