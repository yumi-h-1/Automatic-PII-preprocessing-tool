"""Derive clinical-domain cohorts from the NHS synthetic notes.

The NHSE ``synthetic_clinical_notes`` set has no condition/diagnosis field, so a
"diabetes" or "cardiovascular" cohort has to be *derived* from the free text. This
is a small, transparent clinical-concept matcher (keyword/stem lists per domain),
done honestly: it is recall-oriented keyword tagging, not a validated phenotype,
and we say so in the UI.

Pure-Python; no spaCy/Presidio needed to tag a cohort.
"""
from __future__ import annotations

import re

from .data import NoteRecord

# Domain -> clinical concept stems. Stems (substring match on a lowercased note)
# keep it simple and high-recall: "diabet" catches diabetes/diabetic, "cardi" catches
# cardiac/cardiovascular/cardiology. Curated, not exhaustive.
DOMAIN_CONCEPTS: dict[str, list[str]] = {
    "diabetes": ["diabet", "hba1c", "insulin", "metformin", "hypoglyc", "hyperglyc",
                 "blood glucose", "gliclazide"],
    "cardiovascular": ["cardi", "hypertens", "myocardial", "angina", "atrial fibrillation",
                       "heart failure", "ischaem", "ischem", "stroke", "statin", "blood pressure"],
    "respiratory": ["asthma", "copd", "pneumon", "respirat", "bronch", "wheeze",
                    "breathless", "dyspnoea", "spirometry", "inhaler"],
    "mental health": ["depress", "anxiety", "psychos", "schizophren", "bipolar", "self-harm",
                      "suicid", "mental health", "ssri", "sertraline"],
    "cancer": ["cancer", "carcinoma", "tumour", "tumor", "oncolog", "metasta",
               "chemotherap", "malignan", "biopsy", "lymphoma"],
    "renal": ["renal", "kidney", "dialysis", "nephro", "ckd", "creatinine", "egfr",
              "urinary tract"],
}

DOMAINS = list(DOMAIN_CONCEPTS)


def _matcher(domain: str) -> re.Pattern[str]:
    stems = DOMAIN_CONCEPTS[domain]
    return re.compile("|".join(re.escape(s) for s in stems), re.IGNORECASE)


def note_matches_domain(text: str, domain: str) -> bool:
    return bool(text) and bool(_matcher(domain).search(text))


def filter_by_domain(
    records: list[NoteRecord], domain: str, limit: int | None = None
) -> list[NoteRecord]:
    """Return notes whose text mentions any concept stem for ``domain``."""
    if domain not in DOMAIN_CONCEPTS:
        raise ValueError(f"Unknown domain {domain!r}. Known: {DOMAINS}")
    pat = _matcher(domain)
    out = [r for r in records if r.text and pat.search(r.text)]
    return out[:limit] if limit else out


def domain_counts(records: list[NoteRecord]) -> dict[str, int]:
    """How many notes match each domain (cohorts can overlap — comorbidity)."""
    return {d: sum(1 for r in records if r.text and _matcher(d).search(r.text)) for d in DOMAINS}
