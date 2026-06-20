"""Layer-B custom recognizers, registered on top of Presidio's Global + UK built-ins."""
from __future__ import annotations

from typing import Iterable

from presidio_analyzer import EntityRecognizer

from .clinician_ids import gmc_recognizer, nmc_recognizer
from .nhs_number import NhsNumberRecognizer, is_valid_nhs_number, nhs_check_digit
from .ods_code import ods_recognizer
from .record_ids import record_id_recognizer
from .roster import build_roster_recognizers, name_terms
from .uk_entities import (
    uk_nino_recognizer,
    uk_passport_recognizer,
    uk_postcode_recognizer,
    uk_vehicle_recognizer,
)

__all__ = [
    "custom_recognizers",
    "NhsNumberRecognizer",
    "is_valid_nhs_number",
    "nhs_check_digit",
    "build_roster_recognizers",
    "name_terms",
]


def custom_recognizers(
    roster_person: Iterable[str] = (),
    roster_place: Iterable[str] = (),
    roster_nhs: Iterable[str] = (),
    roster_ids: Iterable[str] = (),
) -> list[EntityRecognizer]:
    """All custom recognizers. Pass a Trust's roster to enable the deny-list backstop."""
    recognizers: list[EntityRecognizer] = [
        NhsNumberRecognizer(),
        uk_postcode_recognizer(),
        uk_nino_recognizer(),
        uk_passport_recognizer(),
        uk_vehicle_recognizer(),
        gmc_recognizer(),
        nmc_recognizer(),
        ods_recognizer(),
        record_id_recognizer(),
    ]
    recognizers.extend(build_roster_recognizers(roster_person, roster_place, roster_nhs, roster_ids))
    return recognizers
