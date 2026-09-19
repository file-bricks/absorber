"""File naming: deterministic fallback names, collision handling, optional local model."""

from __future__ import annotations

import json
import re
import unicodedata
import urllib.request
from datetime import datetime
from pathlib import Path

MAX_SLUG_WORDS = 5
MODEL_SAMPLE_CHARS = 800
PROBE_TIMEOUT = 1.0
NAME_TIMEOUT = 3.0

_UMLAUTS = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}


def slugify(text: str, max_words: int = MAX_SLUG_WORDS) -> str:
    """Lowercase ASCII slug from the first few words. Empty input yields ''."""
    text = text.lower()
    for src, dst in _UMLAUTS.items():
        text = text.replace(src, dst)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    words = re.findall(r"[a-z0-9]+", text)[:max_words]
    return "-".join(words)


def fallback_name(kind: str, sample: str = "") -> str:
    """Always-available name: YYYY-MM-DD_HHMMSS_<slug>."""
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    slug = slugify(sample) if kind == "text" else ""
    return f"{stamp}_{slug}" if slug else f"{stamp}_{kind}"


def unique_path(directory: Path, stem: str, extension: str) -> Path:
    """First free path for <stem>.<ext>, appending _2, _3, ... on collision."""
    extension = extension.lstrip(".")
    candidate = directory / f"{stem}.{extension}"
    counter = 2
    while candidate.exists():
        candidate = directory / f"{stem}_{counter}.{extension}"
        counter += 1
    return candidate


def _http_json(url: str, payload: dict | None, timeout: float) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class OllamaNamer:
    """Names files via a local Ollama instance. Every failure falls back silently.

    ``http`` is injectable so tests never touch the network: it is called as
    ``http(url, payload_or_None, timeout)`` and returns the decoded JSON body.
    """

    def __init__(self, url: str, model: str = "auto", http=None):
        self.url = url.rstrip("/")
        self.model = model
        self._http = http or _http_json

    def available_model(self) -> str | None:
        """Resolve the model to use, or None when Ollama is unreachable."""
        try:
            body = self._http(f"{self.url}/api/tags", None, PROBE_TIMEOUT)
            models = [m.get("name") for m in body.get("models", []) if m.get("name")]
        except Exception:
            return None
        if not models:
            return None
        if self.model and self.model != "auto":
            return self.model if self.model in models else None
        return models[0]

    def suggest(self, text: str) -> str | None:
        """A 3-5 word slug for the text, or None if the model cannot be used."""
        model = self.available_model()
        if not model:
            return None
        prompt = (
            "Give a short file name of 3 to 5 words describing this text. "
            "Answer with the words only, no punctuation, no file extension.\n\n"
            + text[:MODEL_SAMPLE_CHARS]
        )
        try:
            body = self._http(
                f"{self.url}/api/generate",
                {"model": model, "prompt": prompt, "stream": False},
                NAME_TIMEOUT,
            )
        except Exception:
            return None
        slug = slugify(str(body.get("response", "")), max_words=5)
        return slug or None


def build_stem(kind: str, sample: str, namer: OllamaNamer | None = None) -> str:
    """The file stem to use: model suggestion when it works, fallback otherwise."""
    if namer is not None and kind == "text" and sample.strip():
        suggestion = namer.suggest(sample)
        if suggestion:
            return f"{datetime.now().strftime('%Y-%m-%d')}_{suggestion}"
    return fallback_name(kind, sample)
