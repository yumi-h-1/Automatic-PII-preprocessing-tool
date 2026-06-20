"""Central configuration: spaCy model, score threshold, entity coverage, and the per-entity
anonymisation policy map.

The policy map is the heart of "de-identify to a standard": every entity Presidio can emit has an
explicit treatment. In `pseudonymise` mode (the default) identifiers are replaced with realistic but
fake values so the data stays useful for AI; in `redact` mode everything becomes `<ENTITY_TYPE>`.
"""
from __future__ import annotations

import os

# spaCy model. Default to the small model for speed/reliability; en_core_web_lg improves name recall.
SPACY_MODEL: str = os.environ.get("PII_SPACY_MODEL", "en_core_web_sm")

# Minimum confidence for an analyzer result to count as PII.
SCORE_THRESHOLD: float = float(os.environ.get("PII_SCORE_THRESHOLD", "0.35"))

LANGUAGE = "en"

# Custom entity identifiers emitted by our Layer-B recognizers (no Presidio built-in equivalent).
GMC = "GMC"              # General Medical Council number (UK doctors)
NMC = "NMC"              # Nursing & Midwifery Council PIN
NHS_ODS = "NHS_ODS"      # NHS Organisation Data Service codes (GP practices, trusts)
RECORD_ID = "RECORD_ID"  # patient/record UUIDs that appear verbatim in the notes

# Presidio Global + UK built-in entities we expect in clinical notes (others still covered by default).
GLOBAL_ENTITIES = [
    "PERSON", "DATE_TIME", "LOCATION", "NRP", "EMAIL_ADDRESS", "PHONE_NUMBER",
    "URL", "IP_ADDRESS", "MAC_ADDRESS", "CREDIT_CARD", "IBAN_CODE", "CRYPTO", "MEDICAL_LICENSE",
]
UK_ENTITIES = ["UK_NHS", "UK_NINO", "UK_PASSPORT", "UK_POSTCODE", "UK_VEHICLE_REGISTRATION"]
CUSTOM_ENTITIES = [GMC, NMC, NHS_ODS, RECORD_ID]

ALL_ENTITIES = GLOBAL_ENTITIES + UK_ENTITIES + CUSTOM_ENTITIES

# Pseudonymisation strategy per entity. Strategy names are handled in src/anonymize.py.
# Anything not listed falls back to "redact". NRP is special-category data -> always redact.
PSEUDONYMISE_STRATEGY: dict[str, str] = {
    "PERSON": "name",
    "LOCATION": "place",
    "ORGANIZATION": "org",   # spaCy tags hospital/trust names as ORG in this Presidio version
    "DATE_TIME": "date",
    "EMAIL_ADDRESS": "email",
    "PHONE_NUMBER": "phone",
    "UK_NHS": "nhs",
    "UK_NINO": "nino",
    "UK_PASSPORT": "passport",
    "UK_VEHICLE_REGISTRATION": "vehicle",
    "UK_POSTCODE": "postcode",
    "NRP": "redact",            # special-category data: never synthesise
    "MEDICAL_LICENSE": "redact",
    GMC: "redact",
    NMC: "redact",
    NHS_ODS: "redact",
    RECORD_ID: "redact",
    "URL": "redact",
    "IP_ADDRESS": "redact",
    "MAC_ADDRESS": "redact",
    "CREDIT_CARD": "redact",
    "IBAN_CODE": "redact",
    "CRYPTO": "redact",
}

# Default number of notes processed by batch entry points (full run via --limit 0 / None).
DEFAULT_SAMPLE_SIZE = 200
