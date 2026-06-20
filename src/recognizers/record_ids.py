"""Recognizer for record/patient UUIDs that appear verbatim in the notes (e.g. 'Patient ID: 2857...').

These are direct identifiers (person_id) and must be scrubbed. UUIDs are unambiguous, so a plain
pattern is safe and high-confidence.
"""
from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

from ..config import RECORD_ID

_UUID = r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"


def record_id_recognizer() -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity=RECORD_ID,
        patterns=[Pattern("UUID", _UUID, 0.85)],
        context=["patient id", "record", "id"],
        name="RecordIdRecognizer",
    )
