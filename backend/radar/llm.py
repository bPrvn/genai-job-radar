"""NVIDIA NIM client (OpenAI-compatible chat completions). Optional: everything
falls back to rule-based logic when NVIDIA_API_KEY is not set."""

import json
import os
import re
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


def available() -> bool:
    return bool(os.environ.get("NVIDIA_API_KEY"))


def model() -> str:
    return os.environ.get("NIM_MODEL", NIM_MODEL)


def chat(system: str, user: str, max_tokens: int = 1200, temperature: float = 0.2) -> str:
    r = httpx.post(
        f"{NIM_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['NVIDIA_API_KEY']}", "Accept": "application/json"},
        json={"model": model(), "temperature": temperature, "max_tokens": max_tokens,
              "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def chat_json(system: str, user: str, max_tokens: int = 1500):
    """Asks for JSON and parses the first JSON value in the reply (models sometimes wrap it)."""
    text = chat(system + "\nReply with JSON only, no prose, no code fences.", user, max_tokens)
    m = re.search(r"(\[.*\]|\{.*\})", text, re.S)
    if not m:
        raise ValueError(f"model returned no JSON: {text[:200]}")
    return json.loads(m.group(1))
