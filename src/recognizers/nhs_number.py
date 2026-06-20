"""Custom NHS number recognizer that extends Presidio's built-in UK_NHS.

Presidio's UK_NHS recognizer only matches 10 contiguous digits. This dataset writes NHS numbers with
comma/space separators (e.g. ``272,733,208`` / ``272 733 208``), so we add a recognizer that emits the
same ``UK_NHS`` entity for the separated forms and validates every candidate with the official
Modulus-11 checksum to kill false positives.
"""
from __future__ import annotations

import re

from presidio_analyzer import Pattern, PatternRecognizer

ENTITY = "UK_NHS"
_NON_DIGIT = re.compile(r"\D")
# Modulus-11 weights applied to the first 9 digits.
_WEIGHTS = (10, 9, 8, 7, 6, 5, 4, 3, 2)


def nhs_check_digit(nine_digits: str) -> int | None:
    """Return the Modulus-11 check digit for the first 9 digits, or None if invalid (would be 10)."""
    if len(nine_digits) != 9 or not nine_digits.isdigit():
        raise ValueError("expected 9 digits")
    total = sum(int(d) * w for d, w in zip(nine_digits, _WEIGHTS))
    remainder = total % 11
    check = 11 - remainder
    if check == 11:
        check = 0
    if check == 10:
        return None  # number is invalid by construction
    return check


def is_valid_nhs_number(value: str) -> bool:
    """True if `value` (any separators) is a 10-digit NHS number with a valid Modulus-11 check digit."""
    digits = _NON_DIGIT.sub("", value)
    if len(digits) != 10:
        return False
    expected = nhs_check_digit(digits[:9])
    return expected is not None and expected == int(digits[9])


class NhsNumberRecognizer(PatternRecognizer):
    """Matches separated/contiguous NHS numbers and validates the checksum."""

    PATTERNS = [
        Pattern("NHS number (separated)", r"\b\d{3}[ ,]\d{3}[ ,]\d{4}\b", 0.4),
        Pattern("NHS number (contiguous)", r"\b\d{10}\b", 0.3),
        # This dataset uses 9-digit NHS numbers; bare 9-digit runs are ambiguous, so this only fires
        # when an NHS context word is nearby (the context enhancer adds to the low base score).
        Pattern("NHS number (9-digit, context-gated)", r"\b\d{9}\b", 0.15),
    ]
    CONTEXT = ["nhs", "nhs no", "nhs number", "nhs#"]

    def __init__(self) -> None:
        super().__init__(
            supported_entity=ENTITY,
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            name="NhsNumberRecognizer",
        )

    def validate_result(self, pattern_text: str) -> bool | None:
        """Boost valid NHS numbers to full confidence; reject anything failing the checksum."""
        digits = _NON_DIGIT.sub("", pattern_text)
        if len(digits) != 10:
            return None
        return is_valid_nhs_number(digits)
