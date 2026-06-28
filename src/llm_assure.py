"""Optional LLM assurance pass — a recall-oriented safety net over the engine.

The deterministic detector (rules + Presidio NER) is the workhorse. This adds an
*assurance* layer: a free, OpenAI-compatible LLM is asked to spot any identifiers
that survived, and its hits are returned as ``needs_review=True`` spans so a human
confirms them — we never blindly trust the model.

Config is by environment, so the public demo stays key-free and light by default:

    LLM_ASSURE_API_KEY    free key (e.g. Groq, Google Gemini, HF Inference)
    LLM_ASSURE_BASE_URL   OpenAI-compatible base (default: Groq)
    LLM_ASSURE_MODEL      model id (default: a free Llama-3.x on Groq)

No key -> ``is_configured()`` is False and ``detect()`` is a no-op, so the pipeline
behaves exactly as before. Uses ``requests`` only (no heavy local model -> no OOM).
"""
from __future__ import annotations

import json
import os
import re

from .recognisers import Span

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "llama-3.3-70b-versatile"

# normalise the model's free-form labels onto our entity vocabulary
_LABEL_MAP = {
    "person": "PERSON", "name": "PERSON", "patient": "PERSON", "clinician": "PERSON",
    "doctor": "PERSON", "date": "DATE_TIME", "dob": "DATE_TIME", "date_of_birth": "DATE_TIME",
    "nhs": "UK_NHS", "nhs_number": "UK_NHS", "postcode": "UK_POSTCODE", "address": "LOCATION",
    "location": "LOCATION", "phone": "PHONE_NUMBER", "telephone": "PHONE_NUMBER",
    "email": "EMAIL_ADDRESS", "nino": "UK_NINO", "national_insurance": "UK_NINO",
}

_PROMPT = (
    "You are a clinical data-governance assistant. Find every piece of personally "
    "identifiable information (PII/PHI) in the clinical note below: patient or clinician "
    "names, dates of birth, NHS numbers, addresses, postcodes, phone numbers, emails, and "
    "any other direct identifier. Return ONLY a JSON array of objects with keys "
    '"text" (the exact substring as it appears) and "type" (one of person, date_of_birth, '
    "nhs_number, postcode, address, phone, email, other). No prose, no code fences.\n\n"
    "NOTE:\n"
)


def _normalise_type(raw: str) -> str:
    return _LABEL_MAP.get((raw or "").strip().lower().replace(" ", "_"), "LLM_PII")


def _find_all(haystack: str, needle: str) -> list[tuple[int, int]]:
    spots, start = [], 0
    hl, nl = haystack.lower(), needle.lower()
    if not nl:
        return spots
    while (i := hl.find(nl, start)) != -1:
        spots.append((i, i + len(nl)))
        start = i + len(nl)
    return spots


def _parse_json_array(content: str) -> list[dict]:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", content).strip()
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", content, re.DOTALL)
        if not m:
            return []
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return []
    return data if isinstance(data, list) else []


class LLMAssurance:
    """OpenAI-compatible LLM assurance detector (Detector protocol)."""

    name = "llm-assurance"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int = 30,
    ):
        self.api_key = api_key or os.environ.get("LLM_ASSURE_API_KEY", "")
        self.base_url = (base_url or os.environ.get("LLM_ASSURE_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        self.model = model or os.environ.get("LLM_ASSURE_MODEL", DEFAULT_MODEL)
        self.timeout = timeout
        self.last_error: str | None = None

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _call(self, text: str) -> str:
        import requests

        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "temperature": 0,
                "messages": [{"role": "user", "content": _PROMPT + text}],
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def detect(self, text: str) -> list[Span]:
        """Return LLM-flagged PII spans (all needs_review=True). No-op if unconfigured."""
        self.last_error = None
        if not self.is_configured() or not text.strip():
            return []
        try:
            content = self._call(text)
        except Exception as e:  # pragma: no cover - network dependent
            self.last_error = str(e)
            return []
        spans: list[Span] = []
        for item in _parse_json_array(content):
            if not isinstance(item, dict):
                continue
            value = str(item.get("text") or "").strip()
            if len(value) < 2:
                continue
            etype = _normalise_type(str(item.get("type", "")))
            for s, e in _find_all(text, value):
                spans.append(Span(s, e, etype, text[s:e], 0.5, needs_review=True))
        return spans
