"""Download + clean the NHSEDataScience/synthetic_clinical_notes dataset and build the EVAL-ONLY
note<->patient ground-truth oracle.

The notes are unannotated, but each note links (person_id / admission_id) to a patient + admission
record that holds the real (synthetic) identifiers. Joining them gives free ground truth: we know
exactly which name / NHS number / DOB / ward should be scrubbed from each note.

IMPORTANT: `load_notes_with_known_pii()` is for evaluation only. The detection/anonymisation path must
never see the `known` field — that would be data leakage and invalidate the metric.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import ftfy
import pandas as pd
from huggingface_hub import HfApi, hf_hub_download

REPO_ID = "NHSEDataScience/synthetic_clinical_notes"
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
NOTE_TEXT_COL = "clean_note_text"


@dataclass
class Note:
    clinical_note_id: str
    person_id: str
    admission_id: str
    text: str
    known: dict[str, list[str]] = field(default_factory=dict)


def clean_text(value: str) -> str:
    """Repair the documented mojibake ('special characters incorrectly decoded') and tidy whitespace."""
    if not value:
        return ""
    return ftfy.fix_text(str(value)).replace("\r\n", "\n").strip()


def download_dataset(force: bool = False) -> list[Path]:
    """Fetch every CSV in the dataset repo into data/raw/. Fails loudly (no silent fallback)."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    csv_files = [f for f in HfApi().list_repo_files(REPO_ID, repo_type="dataset") if f.endswith(".csv")]
    if not csv_files:
        raise RuntimeError(f"No CSV files found in dataset repo {REPO_ID}")
    paths = []
    for name in csv_files:
        local = hf_hub_download(REPO_ID, name, repo_type="dataset", local_dir=str(RAW_DIR))
        paths.append(Path(local))
    return paths


def _read(name: str) -> pd.DataFrame:
    # The repo nests CSVs under a subfolder (e.g. silver/), so locate by basename.
    path = RAW_DIR / name
    if not path.exists():
        matches = list(RAW_DIR.rglob(name))
        if not matches:
            raise FileNotFoundError(f"{name} not found under {RAW_DIR} — run `python -m src.load_data` first.")
        path = matches[0]
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def load_tables() -> dict[str, pd.DataFrame]:
    """Load patients / admissions / notes; clean the note text column."""
    patients = _read("patients.csv")
    admissions = _read("admissions.csv")
    notes = _read("synthetic_clinical_notes.csv")
    if NOTE_TEXT_COL in notes.columns:
        notes[NOTE_TEXT_COL] = notes[NOTE_TEXT_COL].map(clean_text)
    return {"patients": patients, "admissions": admissions, "notes": notes}


def _nonempty(*values: str) -> list[str]:
    seen, out = set(), []
    for v in values:
        v = (v or "").strip()
        if v and v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)
    return out


def load_notes_with_known_pii(limit: int | None = None) -> list[Note]:
    """Join each note to its patient + admission record and attach the known identifiers (oracle)."""
    tables = load_tables()
    patients = {r["person_id"]: r for _, r in tables["patients"].iterrows() if r.get("person_id")}
    admissions = {r["admission_id"]: r for _, r in tables["admissions"].iterrows() if r.get("admission_id")}

    notes: list[Note] = []
    df = tables["notes"]
    if limit:
        df = df.head(limit)
    for _, row in df.iterrows():
        person = patients.get(row.get("person_id"), {})
        admission = admissions.get(row.get("admission_id"), {})

        names = _nonempty(
            person.get("full_name", ""), admission.get("patient_name", ""),
            admission.get("full_name", ""), admission.get("first_name", ""), admission.get("surname", ""),
        )
        nhs_numbers = _nonempty(person.get("nhs_number", ""), admission.get("nhs_number", ""))
        dobs = _nonempty(person.get("date_of_birth", ""), admission.get("date_of_birth", ""))
        places = _nonempty(
            admission.get("ward", ""), admission.get("site_name", ""), admission.get("bed_location", ""),
        )
        ids = _nonempty(row.get("person_id", ""), admission.get("patient_id", ""))

        notes.append(Note(
            clinical_note_id=row.get("clinical_note_id", ""),
            person_id=row.get("person_id", ""),
            admission_id=row.get("admission_id", ""),
            text=clean_text(row.get(NOTE_TEXT_COL, "")),
            known={"names": names, "nhs_numbers": nhs_numbers, "dobs": dobs, "places": places, "ids": ids},
        ))
    return notes


def main() -> int:
    paths = download_dataset()
    print(f"Downloaded {len(paths)} CSV(s) to {RAW_DIR}:")
    for p in paths:
        print(f"  - {p.name}")
    tables = load_tables()
    for name, df in tables.items():
        print(f"  {name}: {len(df)} rows, columns: {list(df.columns)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
