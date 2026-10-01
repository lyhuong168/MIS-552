"""Thin wrapper around the OpenAI API plus the cached-demo store.

Demo mode never touches the network: every feature looks its result up in
cache/responses.json by a stable key. Live mode calls the API and writes the
result back into the same file, so running build_cache.py (or simply using
the app in live mode) refreshes the cached demo.
"""

import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
CACHE_PATH = ROOT / "cache" / "responses.json"

MODEL = os.environ.get("PAWS_MODEL", "gpt-4o-mini")
IMAGE_MODEL = os.environ.get("PAWS_IMAGE_MODEL", "gpt-image-1")


class NotCached(KeyError):
    """Raised in demo mode when an input has no cached response."""


def fill(template: str, **values) -> str:
    """Fill {placeholders} without tripping over the literal JSON braces in prompts."""
    for key, value in values.items():
        template = template.replace("{" + key + "}", str(value))
    return template


# ---------------------------------------------------------------- cache

def load_cache() -> dict:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {"_meta": {}, "entries": {}}


def get_cached(key: str):
    entries = load_cache()["entries"]
    if key not in entries:
        raise NotCached(key)
    return entries[key]


def save_cached(key: str, value) -> None:
    cache = load_cache()
    cache["entries"][key] = value
    cache["_meta"].update({
        "source": "live",
        "model": MODEL,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    CACHE_PATH.parent.mkdir(exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")


def cache_meta() -> dict:
    return load_cache().get("_meta", {})


# ---------------------------------------------------------------- live calls

def has_key() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


def _client():
    from openai import OpenAI  # imported lazily so demo mode works without the package configured
    return OpenAI()  # reads OPENAI_API_KEY from the environment; never hardcode a key


def chat_json(system: str, messages: list[dict], temperature: float = 0.2, n: int = 1):
    """Call the chat model in JSON mode. Returns a dict, or a list of n dicts when n > 1."""
    resp = _client().chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system}, *messages],
        temperature=temperature,
        n=n,
        response_format={"type": "json_object"},
    )
    parsed = [json.loads(choice.message.content) for choice in resp.choices]
    return parsed if n > 1 else parsed[0]


def chat_text(system: str, messages: list[dict], temperature: float = 0.6) -> str:
    resp = _client().chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system}, *messages],
        temperature=temperature,
    )
    return resp.choices[0].message.content.strip()


def image_part(image_bytes: bytes, mime: str = "image/jpeg") -> dict:
    b64 = base64.b64encode(image_bytes).decode()
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "low"}}


def generate_image(prompt: str) -> bytes:
    resp = _client().images.generate(model=IMAGE_MODEL, prompt=prompt, size="1536x1024", n=1)
    return base64.b64decode(resp.data[0].b64_json)
