"""Custom recognizers fire on their target identifiers (pattern recognizers need no NLP artifacts)."""
from src.config import GMC, NHS_ODS, NMC
from src.recognizers import build_roster_recognizers, name_terms
from src.recognizers.clinician_ids import gmc_recognizer, nmc_recognizer
from src.recognizers.ods_code import ods_recognizer


def _entities(recognizer, text, entity):
    return recognizer.analyze(text=text, entities=[entity], nlp_artifacts=None)


def test_gmc_labelled():
    results = _entities(gmc_recognizer(), "Reviewed by Dr Patel, GMC 1234567.", GMC)
    assert any(r.score >= 0.5 for r in results)


def test_nmc_pin():
    results = _entities(nmc_recognizer(), "Nurse PIN 99I1234E on shift.", NMC)
    assert results and any(r.entity_type == NMC for r in results)


def test_ods_practice_code():
    results = _entities(ods_recognizer(), "Registered at practice code P81026.", NHS_ODS)
    assert any(r.score >= 0.5 for r in results)


def test_name_terms_explodes_surname_first():
    terms = name_terms("Wells, Judith Ada")
    assert {"Wells", "Judith", "Ada"} <= terms


def test_roster_recognizer_matches_known_name():
    recs = build_roster_recognizers(person_names=["Wells, Judith Ada"], place_names=["Ward 12"])
    person_rec = next(r for r in recs if r.supported_entities == ["PERSON"])
    results = person_rec.analyze(text="Spoke with Judith about discharge.", entities=["PERSON"], nlp_artifacts=None)
    assert results
