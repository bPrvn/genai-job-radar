"""NVIDIA NIM client (OpenAI-compatible chat completions). Optional: everything
falls back to rule-based logic when NVIDIA_API_KEY is not set."""

import itertools
import json
import os
import re
import threading
from pathlib import Path

import httpx

from .config import NIM_BASE_URL, NIM_MODEL

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def _load_env():
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()


def _keys() -> list[str]:
    """NVIDIA_API_KEY may be one key or a JSON list of keys (for round-robin)."""
    raw = os.environ.get("NVIDIA_API_KEY", "").strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            return [k.strip() for k in json.loads(raw) if k and k.strip()]
        except (json.JSONDecodeError, TypeError):
            pass
    return [raw]


_KEYS = _keys()
_key_cycle = itertools.cycle(_KEYS) if _KEYS else None
_key_lock = threading.Lock()


def _next_key() -> str:
    with _key_lock:
        return next(_key_cycle)


def key_count() -> int:
    return len(_KEYS)


def available() -> bool:
    return bool(_KEYS)


def model() -> str:
    return os.environ.get("NIM_MODEL", NIM_MODEL)


def chat(system: str, user: str, max_tokens: int = 1200, temperature: float = 0.2) -> str:
    payload = {"model": model(), "temperature": temperature, "max_tokens": max_tokens,
               "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    # Round-robin a key per call; on a rate-limit/auth error, fall forward to the next key.
    attempts = max(1, min(len(_KEYS), 3))
    last_exc: Exception | None = None
    for _ in range(attempts):
        key = _next_key()
        try:
            r = httpx.post(
                f"{NIM_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
                json=payload, timeout=120,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as ex:
            last_exc = ex
            if ex.response.status_code in (401, 403, 429) and len(_KEYS) > 1:
                continue  # try the next key
            raise
    raise last_exc  # type: ignore[misc]


def chat_json(system: str, user: str, max_tokens: int = 1500):
    """Asks for JSON and parses the first JSON value in the reply (models sometimes wrap it)."""
    text = chat(system + "\nReply with JSON only, no prose, no code fences.", user, max_tokens)
    m = re.search(r"(\[.*\]|\{.*\})", text, re.S)
    if not m:
        raise ValueError(f"model returned no JSON: {text[:200]}")
    return json.loads(m.group(1))
