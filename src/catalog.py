"""Curated registry of public clinical-text datasets for Tab 2.

The NHS synthetic notes are the primary, NHS-made source (see ``cohorts.py``). This
registry adds *external* public free-text sources so users can pull domain data from
beyond the NHS set. Every loaded row is run through the same de-identification gate
before download, and each entry carries an honest provenance label so it's clear what
is NHS-made vs. external (mostly US case-report derived).

Loaders use the HF ``datasets`` library (optional). Tabular / credential-gated sets
(e.g. Kaggle) are listed as link-only references rather than auto-loaded.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class CatalogEntry:
    key: str
    name: str
    provenance: str          # honest origin label
    license: str
    url: str
    text_field: str | None = None
    hf_repo: str | None = None
    hf_split: str = "train"
    # loader(limit) -> list[(record_id, text)]; None => link-only reference
    loader: Callable[[int], list[tuple[str, str]]] | None = None

    @property
    def loadable(self) -> bool:
        return self.loader is not None


def _hf_loader(repo: str, field: str, split: str = "train"):
    def load(limit: int) -> list[tuple[str, str]]:
        try:
            from datasets import load_dataset
        except ImportError as e:  # pragma: no cover - environment dependent
            raise RuntimeError("External datasets need `datasets` (pip install datasets).") from e
        ds = load_dataset(repo, split=split, streaming=True)
        out: list[tuple[str, str]] = []
        for i, row in enumerate(ds):
            if i >= limit:
                break
            text = str(row.get(field) or "").strip()
            if text:
                out.append((f"{repo.split('/')[-1]}_{i + 1}", text))
        return out

    return load


# Public free-text clinical datasets. None are domain-pre-split, so Tab 2 applies the
# same clinical-concept domain filter (cohorts.note_matches_domain) to their rows too.
_ENTRIES: list[CatalogEntry] = [
    CatalogEntry(
        key="asclepius",
        name="Asclepius — Synthetic Clinical Notes",
        provenance="External · synthesised from PMC-Patients case reports (US-leaning, not NHS)",
        license="CC BY-NC-SA 4.0",
        url="https://huggingface.co/datasets/starmpcc/Asclepius-Synthetic-Clinical-Notes",
        text_field="note",
        hf_repo="starmpcc/Asclepius-Synthetic-Clinical-Notes",
        loader=_hf_loader("starmpcc/Asclepius-Synthetic-Clinical-Notes", "note"),
    ),
    CatalogEntry(
        key="augmented",
        name="Augmented Clinical Notes",
        provenance="External · 167k notes from open-access PubMed Central case studies (not NHS)",
        license="See dataset card",
        url="https://huggingface.co/datasets/AGBonnet/augmented-clinical-notes",
        text_field="full_note",
        hf_repo="AGBonnet/augmented-clinical-notes",
        loader=_hf_loader("AGBonnet/augmented-clinical-notes", "full_note"),
    ),
    CatalogEntry(
        key="cdc_diabetes",
        name="CDC Diabetes Health Indicators (reference)",
        provenance="External · US CDC BRFSS survey — tabular, not free text, needs Kaggle creds",
        license="CC0 (Kaggle)",
        url="https://www.kaggle.com/datasets/alexteboul/diabetes-health-indicators-dataset",
        loader=None,  # link-only: tabular + credential-gated
    ),
]

CATALOG: dict[str, CatalogEntry] = {e.key: e for e in _ENTRIES}


def all_entries() -> list[CatalogEntry]:
    return list(_ENTRIES)
