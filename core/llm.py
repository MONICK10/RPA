# AI_PROFILES_UI_SPEC.md Part A — the AI layer.
#
# The rule that makes this defensible: every call is grounded in the candidate's
# own JSON. The LLM never computes a number, never invents a requirement, never
# sets a level — it explains, plans, and coaches on top of numbers our code
# already produced. Scoring stays fully deterministic.
#
# ask() is the single entry point for every LLM call. It never raises — every
# caller has a deterministic fallback, so a missing key, a timeout, or a bad
# response degrades silently rather than breaking the page.

import hashlib
import json
import os
import pathlib
import time

from dotenv import load_dotenv

load_dotenv()

# Provider: Groq (api.groq.com), which is OpenAI-compatible. Note that Groq is
# NOT xAI's Grok — different companies, different keys. A gsk_... key is Groq's;
# an xai-... key is xAI's. To change provider, these four lines are the only
# edit needed: everything below speaks plain OpenAI chat-completions.
MODEL = "openai/gpt-oss-120b"   # verify against GET /v1/models for your key
BASE_URL = "https://api.groq.com/openai/v1"
KEY_NAMES = ("GROQ_API_KEY", "XAI_API_KEY")

CACHE_DIR = pathlib.Path("data/cache")
LOG_PATH = pathlib.Path("data/out/llm_log.jsonl")
TIMEOUT_SECONDS = 20
MAX_RETRIES = 1


def _api_key() -> str | None:
    for name in KEY_NAMES:
        key = os.getenv(name)
        if key:
            return key
    try:
        import streamlit as st
        for name in KEY_NAMES:
            key = st.secrets.get(name)
            if key:
                return key
    except Exception:
        pass
    return None


def is_enabled() -> bool:
    """True only if an API key is configured. Callers should also gate on the
    sidebar 'AI features' toggle — this just answers 'could this ever work'."""
    return _api_key() is not None


def _client():
    key = _api_key()
    if not key:
        return None
    from openai import OpenAI  # Groq is OpenAI-compatible
    return OpenAI(api_key=key, base_url=BASE_URL)


def _cache_path(cache_key: str) -> pathlib.Path:
    return CACHE_DIR / f"llm_{cache_key}.json"


def _log(system: str, user: str, response: str | None, cache_key: str, cached: bool) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "cache_key": cache_key, "cached": cached, "model": MODEL,
            "system": system, "user": user, "response": response,
        }
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # logging is diagnostic only, never load-bearing


def ask(system: str, user: str, json_mode: bool = False, max_tokens: int = 1200) -> str | None:
    """Returns the model's text, or None on any failure (missing key, timeout,
    bad response) — never raises. Cached on a hash of the exact input, so the
    same candidate + same company never makes a second network call."""
    cache_key = hashlib.sha256(f"{MODEL}|{json_mode}|{system}|{user}".encode("utf-8")).hexdigest()[:24]
    cache_file = _cache_path(cache_key)

    if cache_file.exists():
        try:
            cached_response = json.loads(cache_file.read_text(encoding="utf-8"))["response"]
            _log(system, user, cached_response, cache_key, cached=True)
            return cached_response
        except (json.JSONDecodeError, OSError, KeyError):
            pass

    client = _client()
    if client is None:
        return None

    kwargs = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    for _ in range(MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(timeout=TIMEOUT_SECONDS, **kwargs)
            text = response.choices[0].message.content
            if not text:
                continue
            try:
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(json.dumps({"response": text}), encoding="utf-8")
            except OSError:
                pass
            _log(system, user, text, cache_key, cached=False)
            return text
        except Exception:
            continue

    _log(system, user, None, cache_key, cached=False)
    return None
