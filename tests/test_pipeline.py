"""End-to-end pipeline: known identifiers must not survive sanitisation.

Uses the pure-Python RuleDetector so the test is fast and needs no spaCy/Presidio.
"""
from src.detect import RuleDetector
from src.pipeline import Pipeline
from src.transform import PSEUDONYM


def test_pipeline_removes_known_pii():
    text = ("Pt seen, NHS no 943 476 5919, dob 12/03/1981, lives SW1A 1AA, "
            "tel 07700 900123, GMC 1234567.")
    result = Pipeline(detector=RuleDetector()).sanitise(text, PSEUDONYM, person_id="p1")
    for leaked in ("943 476 5919", "12/03/1981", "SW1A 1AA", "07700 900123", "1234567"):
        assert leaked not in result.sanitised
    assert result.audit["entities_removed"] >= 5
