"""Runtime settings for The Last Clue."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = Path(__file__).resolve().parent / "static"
_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


@dataclass(frozen=True)
class Settings:
    """Process settings resolved from environment variables."""

    host: str = "0.0.0.0"
    port: int = 8765
    log_level: str = "INFO"
    llm_url: str = "http://llamacpp-models-runner:9999/v1/chat/completions"
    llm_model: str = "Qwen3.5-0.8B-Q4_0"
    llm_timeout_seconds: float = 90.0
    ai_enabled: bool = True
    static_dir: Path = STATIC_DIR


def load_settings() -> Settings:
    """Load and validate environment settings with safe defaults."""
    host = os.environ.get("LAST_CLUE_HOST", "0.0.0.0").strip() or "0.0.0.0"
    port = _int_range(os.environ.get("LAST_CLUE_PORT", "8765"), 1, 65535, "LAST_CLUE_PORT")
    log_level = os.environ.get("LAST_CLUE_LOG_LEVEL", "INFO").strip().upper()
    if log_level not in _LOG_LEVELS:
        log_level = "INFO"
    llm_url = os.environ.get(
        "LAST_CLUE_LLM_URL",
        "http://llamacpp-models-runner:9999/v1/chat/completions",
    ).strip()
    llm_model = os.environ.get("LAST_CLUE_LLM_MODEL", "Qwen3.5-0.8B-Q4_0").strip() or "Qwen3.5-0.8B-Q4_0"
    llm_timeout = _float_range(
        os.environ.get("LAST_CLUE_LLM_TIMEOUT", "90"),
        0.5,
        300.0,
        "LAST_CLUE_LLM_TIMEOUT",
    )
    ai_enabled_raw = os.environ.get("LAST_CLUE_AI_ENABLED", "true").strip().lower()
    ai_enabled = ai_enabled_raw not in {"0", "false", "no", "off"}

    return Settings(
        host=host,
        port=port,
        log_level=log_level,
        llm_url=llm_url,
        llm_model=llm_model,
        llm_timeout_seconds=llm_timeout,
        ai_enabled=ai_enabled,
        static_dir=STATIC_DIR,
    )


def _int_range(raw: str, low: int, high: int, name: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return value


def _float_range(raw: str, low: float, high: float, name: str) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return value
