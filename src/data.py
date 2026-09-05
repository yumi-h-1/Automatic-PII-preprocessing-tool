"""Load the NHSE synthetic clinical notes dataset.

The dataset ships three CSVs that share keys:
  patients.csv    person_id, full_name, nhs_number, date_of_birth, ...
  admissions.csv  admission_id, patient_name/first_name/surname, site_name, ward, ...
  notes.csv       clinical_note_id, clean_note_text, person_id, admission_id, ...

Only ``notes.csv`` is used: NoteGuard reads the free text and nothing else. The
identifiers held in the patient/admission tables are never loaded — the engine must
find PII in the text on its own, exactly as it would in a Trust.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

import pandas as pd

REPO_ID = "NHSEDataScience/synthetic_clinical_notes"


@dataclass
class NoteRecord:
    note_id: str
    person_id: str
    admission_id: str
    text: str
    note_type: str = ""
    note_subject: str = ""


def _fix_mojibake(s: str) -> str:
    """Repair the known UTF-8-as-latin-1 decoding defect (e.g. 'Â·' -> '·')."""
    if not s or ("Â" not in s and "Ã" not in s):
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return s


def _first_col(df: pd.DataFrame, *candidates: str) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _download_notes_csv(local_dir: str | None = None) -> str:
    """Discover and fetch the notes CSV from the HF dataset repo."""
    from huggingface_hub import hf_hub_download, list_repo_files

    files = [f for f in list_repo_files(REPO_ID, repo_type="dataset") if f.endswith(".csv")]
    picked = next((f for f in files if "note" in f.lower()), None)
    if picked is None:
        raise RuntimeError(f"Could not locate a notes CSV in {REPO_ID}. Found: {files}")
    return hf_hub_download(REPO_ID, picked, repo_type="dataset", local_dir=local_dir)


@lru_cache(maxsize=1)
def load_notes_table(local_dir: str | None = None) -> pd.DataFrame:
    """Return the notes DataFrame.

    Honours NOTEGUARD_DATA_DIR (a folder holding the CSV) so the demo can run fully
    offline once the data is cached.
    """
    data_dir = local_dir or os.environ.get("NOTEGUARD_DATA_DIR")
    if data_dir and os.path.isdir(data_dir):
        for name in ("synthetic_clinical_notes.csv", "notes.csv"):
            path = os.path.join(data_dir, name)
            if os.path.exists(path):
                return pd.read_csv(path, dtype=str, keep_default_na=False)
        raise FileNotFoundError(f"No notes CSV (synthetic_clinical_notes.csv / notes.csv) in {data_dir}")
    return pd.read_csv(_download_notes_csv(local_dir=local_dir), dtype=str, keep_default_na=False)


def load_notes(limit: int | None = None, local_dir: str | None = None) -> list[NoteRecord]:
    """Read the NHSE synthetic notes as NoteRecords (free text only)."""
    notes = load_notes_table(local_dir=local_dir)

    text_col = _first_col(notes, "clean_note_text", "note_text", "text")
    n_pid = _first_col(notes, "person_id", "patient_id")
    n_aid = _first_col(notes, "admission_id")
    nid_col = _first_col(notes, "clinical_note_id", "note_id")
    ntype = _first_col(notes, "note_type")
    nsubj = _first_col(notes, "note_subject")

    rows = notes if limit is None else notes.head(limit)
    return [
        NoteRecord(
            note_id=str(r.get(nid_col, "")) if nid_col else "",
            person_id=str(r.get(n_pid, "")) if n_pid else "",
            admission_id=str(r.get(n_aid, "")) if n_aid else "",
            text=_fix_mojibake(str(r.get(text_col, ""))) if text_col else "",
            note_type=str(r.get(ntype, "")) if ntype else "",
            note_subject=str(r.get(nsubj, "")) if nsubj else "",
        )
        for _, r in rows.iterrows()
    ]


if __name__ == "__main__":
    for rec in load_notes(limit=5):
        print(f"\n=== note {rec.note_id} (person {rec.person_id}) ===")
        print(rec.text[:200].replace("\n", " "), "...")
