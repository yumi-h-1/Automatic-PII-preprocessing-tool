"""End-to-end leakage test on a crafted note (loads spaCy; this is what the post-edit hook runs).

Known identifiers placed in the text must NOT survive anonymisation. This is the project's core
guarantee, in miniature.
"""
import pytest

from src.analyzer import analyze, build_analyzer
from src.anonymize import MODE_PSEUDONYMISE, MODE_REDACT, Vault, anonymize_text

NOTE = (
    "Patient Judith Wells (NHS number 943 476 5919), DOB 15/05/1984, lives at SW1A 1AA. "
    "Admitted to Ward 12 at St Mary's Hospital. Contact 020 7946 0958."
)
ROSTER_PERSON = ["Wells, Judith Ada"]
ROSTER_PLACE = ["Ward 12", "St Mary's Hospital"]


@pytest.fixture(scope="module")
def analyzer():
    return build_analyzer(roster_person=ROSTER_PERSON, roster_place=ROSTER_PLACE)


@pytest.mark.parametrize("mode", [MODE_PSEUDONYMISE, MODE_REDACT])
def test_no_known_identifier_leaks(analyzer, mode):
    results = analyze(analyzer, NOTE)
    clean = anonymize_text(NOTE, results, mode=mode, vault=Vault(seed=42))
    lower = clean.lower()
    for leaked in ["judith", "wells", "943 476 5919", "9434765919", "sw1a 1aa"]:
        assert leaked not in lower, f"leaked {leaked!r} in {mode} output: {clean}"


def test_nhs_number_detected(analyzer):
    results = analyze(analyzer, NOTE)
    assert any(r.entity_type == "UK_NHS" for r in results)
