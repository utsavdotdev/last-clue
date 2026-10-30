"""Local open-weight LLM provider for Arduino UNO Q (llama-server / Qwen3.5-0.8B-Q4_0).

Optimized for fast, low-token generation on the UNO Q's on-board CPU by disabling
chain-of-thought (<think>) blocks via /no_think + chat_template_kwargs and keeping
output budgets compact.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import re
import urllib.error
import urllib.request
from typing import Protocol
from urllib.parse import urlparse

from last_clue.models import WordEntry
from last_clue.word_packs import BUNDLED_WORD_PACKS, normalize_guess_text

logger = logging.getLogger(__name__)

ALLOWED_LOCAL_HOSTS = frozenset({"localhost", "llamacpp-models-runner", "host.docker.internal"})

FORBIDDEN_RULE_PHRASES = (
    "ignore previous",
    "system prompt",
    "you win",
    "score is",
    "change role",
    "admin",
)


class ChatCompletionTransport(Protocol):
    def post_json(self, url: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
        """Send a JSON POST to the local inference server and return parsed JSON."""


class UrllibTransport:
    """Standard-library HTTP client that refuses non-local URLs and sends no API keys."""

    def post_json(self, url: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
        if not is_local_model_url(url):
            raise ValueError("Refusing non-local AI endpoint URL")
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("Model server did not return a JSON object")
        return parsed


def is_local_model_url(url: str) -> bool:
    """Verify the LLM URL points strictly to localhost, LAN/container IP, or UNO Q brick host."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        return False
    host = parsed.hostname
    if not host:
        return False
    lowered = host.lower()
    if lowered in ALLOWED_LOCAL_HOSTS:
        return True
    try:
        addr = ipaddress.ip_address(lowered)
    except ValueError:
        return False
    return bool(addr.is_loopback or addr.is_private or addr.is_link_local)


def normalize_chat_url(url: str) -> str:
    cleaned = url.strip().rstrip("/")
    suffix = "/v1/chat/completions"
    if cleaned.endswith(suffix):
        return cleaned
    return cleaned + suffix


def sanitize_dashes(text: str) -> str:
    """Remove em-dashes and en-dashes to enforce clean typography."""
    cleaned = text.replace("\u2014", " - ").replace("\u2013", "-")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _strip_think_blocks(text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    end_idx = cleaned.rfind("</think>")
    if end_idx != -1:
        cleaned = cleaned[end_idx + len("</think>") :]
    start_idx = cleaned.find("<think>")
    if start_idx != -1:
        cleaned = cleaned[:start_idx]
    return cleaned.strip()


def validate_round_intro(
    raw_text: str,
    *,
    secret_word: str,
    synonyms: list[str] | None = None,
) -> str:
    """Validate that a generated round introduction is safe, concise, and never leaks the word."""
    cleaned = _strip_think_blocks(raw_text)
    cleaned = cleaned.strip().strip('"').strip("'")
    cleaned = sanitize_dashes(cleaned)
    if len(cleaned) < 12 or len(cleaned) > 260:
        raise ValueError("Generated round intro length out of bounds")

    norm_intro = normalize_guess_text(cleaned)
    forbidden_terms = {normalize_guess_text(secret_word)}
    for part in normalize_guess_text(secret_word).split():
        if len(part) >= 4:
            forbidden_terms.add(part)
    for syn in synonyms or []:
        norm_syn = normalize_guess_text(syn)
        if norm_syn:
            forbidden_terms.add(norm_syn)

    for term in forbidden_terms:
        if term and re.search(rf"\b{re.escape(term)}\b", norm_intro):
            raise ValueError("Generated intro leaked the secret word or synonym")

    lowered = cleaned.casefold()
    if any(phrase in lowered for phrase in FORBIDDEN_RULE_PHRASES):
        raise ValueError("Generated intro contained forbidden instruction text")

    return cleaned


def _parse_candidate_items(text: str, default_category: str) -> list[dict[str, object]]:
    """Extract candidate word dicts from JSON object, JSON array, or compact list output."""
    if text.startswith("```"):
        first_nl = text.find("\n")
        text = text[first_nl + 1 :] if first_nl != -1 else text
        last_fence = text.rfind("```")
        if last_fence != -1:
            text = text[:last_fence]
    text = text.strip()

    start_brace = text.find("{")
    start_bracket = text.find("[")
    parsed: object = None
    try:
        if start_bracket != -1 and (start_brace == -1 or start_bracket < start_brace):
            end_bracket = text.rfind("]")
            if end_bracket > start_bracket:
                parsed = json.loads(text[start_bracket : end_bracket + 1])
        elif start_brace != -1:
            end_brace = text.rfind("}")
            if end_brace > start_brace:
                parsed_obj = json.loads(text[start_brace : end_brace + 1])
                if isinstance(parsed_obj, dict):
                    parsed = parsed_obj.get("words", [parsed_obj])
                else:
                    parsed = parsed_obj
    except json.JSONDecodeError:
        parsed = None

    items: list[dict[str, object]] = []
    if isinstance(parsed, list):
        for elem in parsed:
            if isinstance(elem, dict):
                items.append(elem)
            elif isinstance(elem, str) and elem.strip():
                items.append(
                    {
                        "word": elem.strip(),
                        "category": default_category,
                        "difficulty": "medium",
                        "synonyms": [],
                    }
                )
        if items:
            return items

    # Compact plain-line / comma fallback if the 0.8B model omitted JSON braces
    for raw_line in re.split(r"[\n,;]+", text):
        cleaned_line = re.sub(r"^[\s\-\*\d\.\)\"']+|[\s\"']+$", "", raw_line)
        if 3 <= len(cleaned_line) <= 28 and not any(
            ch in cleaned_line for ch in ("{", "}", "[", "]", ":")
        ):
            items.append(
                {
                    "word": cleaned_line,
                    "category": default_category,
                    "difficulty": "medium",
                    "synonyms": [],
                }
            )
    return items


def validate_generated_word_pack(
    raw_content: str,
    *,
    default_category: str = "Haunted Relics",
    existing_entries: list[WordEntry] | None = None,
) -> list[WordEntry]:
    """Validate candidate horror words generated by the local model."""
    text = _strip_think_blocks(raw_content)
    if not text:
        raise ValueError("Model response was empty")

    candidate_items = _parse_candidate_items(text, default_category=default_category)
    if not candidate_items:
        raise ValueError("Model response did not contain valid words")

    existing_pool = list(BUNDLED_WORD_PACKS) + (existing_entries or [])
    seen_words = {normalize_guess_text(item.word) for item in existing_pool}
    validated: list[WordEntry] = []

    for item in candidate_items:
        raw_word = str(item.get("word", "")).strip()
        raw_category = str(item.get("category") or default_category).strip()
        raw_difficulty = str(item.get("difficulty", "medium")).strip().lower()
        raw_synonyms = item.get("synonyms", [])

        if not raw_word or not raw_category:
            continue
        word_clean = sanitize_dashes(raw_word)
        cat_clean = sanitize_dashes(raw_category)
        if not (3 <= len(word_clean) <= 32) or not (4 <= len(cat_clean) <= 40):
            continue
        if any(phrase in word_clean.casefold() for phrase in FORBIDDEN_RULE_PHRASES):
            continue

        norm_word = normalize_guess_text(word_clean)
        if not norm_word or norm_word in seen_words:
            continue

        if raw_difficulty not in {"easy", "medium", "hard"}:
            raw_difficulty = "medium"

        synonyms_clean: list[str] = []
        if isinstance(raw_synonyms, list):
            for syn in raw_synonyms[:4]:
                if isinstance(syn, str) and 2 <= len(syn.strip()) <= 30:
                    s_clean = sanitize_dashes(syn.strip())
                    if normalize_guess_text(s_clean) != norm_word:
                        synonyms_clean.append(s_clean)

        seen_words.add(norm_word)
        validated.append(
            WordEntry(
                word=word_clean,
                category=cat_clean,
                difficulty=raw_difficulty,  # type: ignore[arg-type]
                synonyms=synonyms_clean,
                source="ai",
            )
        )

    if not validated:
        raise ValueError("No valid non-duplicate horror words found in model output")
    return validated


class LlamaServerClient:
    """Thin client for OpenAI-compatible local llama.cpp server."""

    def __init__(
        self,
        url: str,
        model: str,
        timeout: float = 90.0,
        transport: ChatCompletionTransport | None = None,
    ) -> None:
        self.url = normalize_chat_url(url)
        self.model = model
        self.timeout = timeout
        self._transport = transport if transport is not None else UrllibTransport()

    def complete(self, system_prompt: str, user_prompt: str, max_tokens: int = 80) -> str:
        if not is_local_model_url(self.url):
            raise ValueError("Refusing non-local model URL")
        # Append /no_think and pass chat_template_kwargs to skip Qwen3.5 thinking tokens
        payload: dict[str, object] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": f"/no_think\n{system_prompt}"},
                {"role": "user", "content": f"/no_think\n{user_prompt}"},
            ],
            "temperature": 0.35,
            "max_tokens": max_tokens,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        response = self._transport.post_json(self.url, payload, self.timeout)
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("Model response missing choices")
        first = choices[0]
        if not isinstance(first, dict):
            raise ValueError("Invalid choice item")
        message = first.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise ValueError("Model response missing message content")
        return message["content"]


class LocalHorrorProvider:
    """Generates validated horror round introductions, narrations, and word packs locally."""

    def __init__(self, client: LlamaServerClient) -> None:
        self.client = client

    def generate_round_intro(
        self,
        *,
        category: str,
        secret_word: str,
        synonyms: list[str] | None = None,
    ) -> str:
        system_prompt = (
            "Write 1 short spooky sentence setting the mood for a horror game. "
            "Never mention the forbidden word. No hyphens or dashes."
        )
        user_prompt = (
            f"Theme: {category}. Forbidden word: {secret_word}. "
            "One spooky sentence under 140 characters:"
        )
        raw = self.client.complete(system_prompt, user_prompt, max_tokens=48)
        return validate_round_intro(raw, secret_word=secret_word, synonyms=synonyms)

    def generate_narration(self, *, event_key: str, context: str = "") -> str:
        system_prompt = "Write 1 short spooky game announcement under 110 characters."
        user_prompt = f"Event: {event_key}. {context}"
        raw = self.client.complete(system_prompt, user_prompt, max_tokens=36)
        cleaned = sanitize_dashes(_strip_think_blocks(raw).strip().strip('"'))
        if not (10 <= len(cleaned) <= 180):
            raise ValueError("Generated narration length out of bounds")
        return cleaned

    def generate_word_pack(
        self,
        *,
        category: str = "Haunted Relics",
        count: int = 3,
        existing_entries: list[WordEntry] | None = None,
    ) -> list[WordEntry]:
        system_prompt = (
            "Return only a JSON array of 3 short horror nouns. "
            'Example: ["Bone Key", "Weeping Statue", "Iron Coffin"]'
        )
        user_prompt = f'Category: "{category}". JSON array of {count} horror nouns:'
        raw = self.client.complete(system_prompt, user_prompt, max_tokens=64)
        return validate_generated_word_pack(
            raw,
            default_category=category,
            existing_entries=existing_entries,
        )
