"""UK entity recognizers that the docs list as built-in but the released presidio-analyzer
(2.2.362) does NOT ship — only UK_NHS is built in. We provide them here, emitting the same entity
names the docs use, so the policy map and anonymiser work unchanged.

Covered: UK_POSTCODE, UK_NINO, UK_PASSPORT, UK_VEHICLE_REGISTRATION.
"""
from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer


def uk_postcode_recognizer() -> PatternRecognizer:
    # Outward (area+district) + optional space + inward (sector+unit), e.g. SW1A 1AA, M1 1AE, EC1A 1BB.
    pattern = Pattern("UK postcode", r"\b[A-Za-z]{1,2}\d[A-Za-z\d]?\s*\d[A-Za-z]{2}\b", 0.5)
    return PatternRecognizer(
        supported_entity="UK_POSTCODE",
        patterns=[pattern],
        context=["postcode", "address", "lives at", "resides"],
        name="UkPostcodeRecognizer",
    )


def uk_nino_recognizer() -> PatternRecognizer:
    # National Insurance Number: 2 letters, 6 digits, 1 suffix letter (A-D), optional spaces.
    pattern = Pattern("UK NINO", r"\b[A-Za-z]{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-Da-d]\b", 0.5)
    return PatternRecognizer(
        supported_entity="UK_NINO",
        patterns=[pattern],
        context=["national insurance", "ni number", "nino"],
        name="UkNinoRecognizer",
    )


def uk_passport_recognizer() -> PatternRecognizer:
    # UK passport numbers are 9 digits; bare 9-digit runs are ambiguous, so require context.
    pattern = Pattern("UK passport", r"\b\d{9}\b", 0.05)
    return PatternRecognizer(
        supported_entity="UK_PASSPORT",
        patterns=[pattern],
        context=["passport"],
        name="UkPassportRecognizer",
    )


def uk_vehicle_recognizer() -> PatternRecognizer:
    # Current-format UK plate: 2 letters, 2 digits, space, 3 letters (e.g. AB12 CDE).
    pattern = Pattern("UK vehicle registration", r"\b[A-Za-z]{2}\d{2}\s?[A-Za-z]{3}\b", 0.4)
    return PatternRecognizer(
        supported_entity="UK_VEHICLE_REGISTRATION",
        patterns=[pattern],
        context=["registration", "vehicle", "number plate", "car"],
        name="UkVehicleRecognizer",
    )
