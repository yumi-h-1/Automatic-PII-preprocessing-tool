"""Recognizer for NHS ODS (Organisation Data Service) codes — GP practices, trusts, sites.

GP practice codes are a letter followed by 5 digits (e.g. P81026). Bare codes are ambiguous, so we
only score them when an organisational context word is present.
"""
from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

from ..config import NHS_ODS


def ods_recognizer() -> PatternRecognizer:
    patterns = [
        Pattern("ODS code (labelled)", r"(?i)\b(?:ODS|practice code)[:\s]*[A-Z]\d{5}\b", 0.8),
        Pattern("ODS GP practice code", r"\b[A-Z]\d{5}\b", 0.2),
    ]
    return PatternRecognizer(
        supported_entity=NHS_ODS,
        patterns=patterns,
        context=["ods", "practice", "gp", "surgery", "trust", "site code", "organisation"],
        name="OdsRecognizer",
    )
