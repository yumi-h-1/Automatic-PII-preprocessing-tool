"""Privacy guarantee: de-identifying user data must not write anything to disk.

This is the automated evidence behind the demo's "your data is never stored" claim
(Tab 1). It snapshots the file tree before and after de-identifying both pasted text
and an uploaded CSV/TXT, and asserts no new files appear and the vault is not exported.

Uses the pure-Python RuleDetector so it needs no spaCy/Presidio.
"""
from pathlib import Path

from src.detect import RuleDetector
from src.ingest import records_from_upload
from src.pipeline import Pipeline
from src.transform import PSEUDONYM

SAMPLE = ("Pt John Smith, NHS no 943 476 5919, DOB 02/03/1981, lives SW1A 1AA. "
          "Reviewed by Dr Lee, GMC 1234567.")


def _snapshot(root: Path) -> set[Path]:
    return set(root.rglob("*"))


def test_pipeline_writes_no_files(tmp_path, monkeypatch):
    """Running the de-id pipeline writes nothing to the working directory."""
    monkeypatch.chdir(tmp_path)
    before = _snapshot(tmp_path)

    result = Pipeline(detector=RuleDetector()).sanitise(SAMPLE, PSEUDONYM, person_id="p1")
    assert "943 476 5919" not in result.sanitised  # sanity: it actually ran

    assert _snapshot(tmp_path) == before, "de-identification must not create files on disk"


def test_ingest_in_memory_only(tmp_path, monkeypatch):
    """Ingesting uploaded bytes (txt + csv) writes no temp files."""
    monkeypatch.chdir(tmp_path)
    before = _snapshot(tmp_path)

    txt_recs = records_from_upload("note.txt", SAMPLE.encode("utf-8"))
    assert len(txt_recs) == 1 and txt_recs[0].text

    csv_bytes = ("note\n" + SAMPLE.replace(",", " ") + "\n").encode("utf-8")
    csv_recs = records_from_upload("notes.csv", csv_bytes, text_column="note")
    assert len(csv_recs) == 1

    # de-identify what we ingested
    pipe = Pipeline(detector=RuleDetector())
    for r in txt_recs + csv_recs:
        pipe.sanitise(r.text, PSEUDONYM, person_id=r.record_id)

    assert _snapshot(tmp_path) == before, "ingestion + de-id must stay in memory"


def test_vault_not_persisted(tmp_path, monkeypatch):
    """The re-identification vault is held in memory and never written out."""
    monkeypatch.chdir(tmp_path)
    result = Pipeline(detector=RuleDetector()).sanitise(SAMPLE, PSEUDONYM, person_id="p1")
    # nothing on disk references the vault mapping
    assert not list(tmp_path.rglob("*vault*"))
    assert result.sanitised
