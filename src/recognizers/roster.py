"""Roster (deny-list) recognizers seeded from a Trust's own patient/site records.

Real hospitals hold a patient roster, so this is a legitimate — and very high-recall — backstop:
spaCy NER generalises to unseen names, while the roster guarantees that the known identifiers for the
people actually in this Trust's notes get scrubbed (it catches the "Surname, First" forms NER misses).
Build it from the patient table inside the Trust; it never leaves.
"""
from __future__ import annotations

import re
from typing import Iterable

from presidio_analyzer import PatternRecognizer

_ALPHA_TOKEN = re.compile(r"[A-Za-z][A-Za-z'\-]+")


def name_terms(full_name: str) -> set[str]:
    """Explode a full name into searchable terms: each token (len >= 3) plus the whole string."""
    terms: set[str] = set()
    name = (full_name or "").strip()
    if not name:
        return terms
    for tok in _ALPHA_TOKEN.findall(name):
        if len(tok) >= 3:
            terms.add(tok)
    cleaned = name.replace(",", " ").strip()
    if len(cleaned) >= 3:
        terms.add(cleaned)
    return terms


def _build(terms: Iterable[str], entity: str, name: str) -> PatternRecognizer | None:
    deny = sorted({t for t in terms if t and len(t) >= 3})
    if not deny:
        return None
    return PatternRecognizer(supported_entity=entity, deny_list=deny, name=name)


def build_roster_recognizers(
    person_names: Iterable[str] = (),
    place_names: Iterable[str] = (),
    nhs_numbers: Iterable[str] = (),
    record_ids: Iterable[str] = (),
) -> list[PatternRecognizer]:
    """Return deny-list recognizers for the supplied roster (skips empty categories).

    Names/places generalise via NER; NHS numbers and UUIDs in this dataset don't fit a clean pattern,
    so the roster (which a Trust legitimately holds) guarantees the known ones are scrubbed.
    """
    from ..config import RECORD_ID

    person_terms: set[str] = set()
    for full_name in person_names:
        person_terms |= name_terms(full_name)
    place_terms = {p.strip() for p in place_names if p and p.strip()}
    nhs_terms = {n.strip() for n in nhs_numbers if n and n.strip()}
    id_terms = {i.strip() for i in record_ids if i and i.strip()}

    specs = [
        (person_terms, "PERSON", "RosterPersonRecognizer"),
        (place_terms, "LOCATION", "RosterPlaceRecognizer"),
        (nhs_terms, "UK_NHS", "RosterNhsRecognizer"),
        (id_terms, RECORD_ID, "RosterRecordIdRecognizer"),
    ]
    recognizers = []
    for terms, entity, name in specs:
        rec = _build(terms, entity, name)
        if rec:
            recognizers.append(rec)
    return recognizers
