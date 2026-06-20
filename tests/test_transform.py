"""Transforms: redaction tags, patient-consistent pseudonyms, valid fake NHS, date-shift."""
import re
from datetime import datetime

from noteguard.recognizers import find_rule_spans, nhs_number_is_valid
from noteguard.transform import (
    PSEUDONYM, REDACTION, PseudonymVault, _fake_nhs_number, apply_transform,
)


def test_redaction_removes_value_and_tags():
    text = "NHS 943 476 5919"
    out, _ = apply_transform(text, find_rule_spans(text), REDACTION)
    assert "[NHS number]" in out
    assert "943 476 5919" not in out


def test_pseudonym_is_consistent():
    v = PseudonymVault()
    assert v.token_for("PERSON", "Smith, John") == v.token_for("PERSON", "Smith, John")


def test_fake_nhs_number_valid_and_stable():
    n1 = _fake_nhs_number("943 476 5919")
    n2 = _fake_nhs_number("943 476 5919")
    assert n1 == n2
    assert nhs_number_is_valid(n1)


def test_nino_surrogate_format():
    import re
    v = PseudonymVault()
    nino = v.token_for("UK_NINO", "AB 12 34 56 C")
    assert re.fullmatch(r"[A-Z]{2}\d{6}[A-D]", nino)


def test_vehicle_surrogate_format():
    import re
    v = PseudonymVault()
    reg = v.token_for("UK_VEHICLE_REGISTRATION", "AB12 CDE")
    assert re.fullmatch(r"[A-Z]{2}\d{2} [A-Z]{3}", reg)


def test_date_shift_is_consistent_per_patient():
    # Only date-of-birth dates are treated as PII, so both need a DOB context. The
    # per-patient offset is consistent, so the interval between them is preserved.
    text = "DOB 12/03/1981 ... DOB 20/03/1981"
    out, _ = apply_transform(text, find_rule_spans(text), PSEUDONYM, PseudonymVault(), person_id="p1")
    assert "12/03/1981" not in out and "20/03/1981" not in out
    dates = [datetime.strptime(d, "%d/%m/%Y") for d in re.findall(r"\d{2}/\d{2}/\d{4}", out)]
    assert len(dates) == 2
    assert (dates[1] - dates[0]).days == 8  # consistent offset preserves the interval
