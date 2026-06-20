"""Recognizers for UK clinician identifiers — GMC (doctors) and NMC PIN (nurses/midwives).

De-identifying *staff* matters too: Caldicott / DPA apply to any identifiable individual, not just
patients. Presidio has no equivalent, so these complement the built-in MEDICAL_LICENSE entity.

Both use a high-confidence explicit form (with the label) plus a lower-confidence bare form that only
fires when a context word is nearby, to avoid flagging every 7-digit number.
"""
from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

from ..config import GMC, NMC


def gmc_recognizer() -> PatternRecognizer:
    """GMC reference number: 7 digits, usually labelled 'GMC'."""
    patterns = [
        Pattern("GMC (labelled)", r"(?i)\bGMC[:\s#]*\d{7}\b", 0.85),
        Pattern("GMC (bare 7-digit)", r"\b\d{7}\b", 0.05),
    ]
    return PatternRecognizer(
        supported_entity=GMC,
        patterns=patterns,
        context=["gmc", "doctor", "consultant", "registrar"],
        name="GmcRecognizer",
    )


def nmc_recognizer() -> PatternRecognizer:
    """NMC PIN: 2 digits, a letter, 4 digits, a letter (e.g. 99I1234E)."""
    patterns = [
        Pattern("NMC PIN", r"\b\d{2}[A-Za-z]\d{4}[A-Za-z]\b", 0.6),
    ]
    return PatternRecognizer(
        supported_entity=NMC,
        patterns=patterns,
        context=["nmc", "nurse", "midwife", "pin"],
        name="NmcRecognizer",
    )
