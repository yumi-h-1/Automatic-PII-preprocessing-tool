"""NHS number Modulus-11 checksum and all surface forms the dataset uses."""
from noteguard.recognizers import UK_NHS, find_rule_spans, nhs_number_is_valid


def _has_nhs(text: str) -> bool:
    return any(s.entity_type == UK_NHS for s in find_rule_spans(text))


def test_valid_10_digit_passes():
    assert nhs_number_is_valid("9434765919")


def test_separated_space_valid():
    assert nhs_number_is_valid("943 476 5919")


def test_separated_comma_valid():
    assert nhs_number_is_valid("943,476,5919")


def test_bad_checksum_rejected():
    assert not nhs_number_is_valid("943 476 5918")


def test_wrong_length_rejected():
    assert not nhs_number_is_valid("12345")
    assert not nhs_number_is_valid("94347659190")


def test_rule_detects_spaced_form():
    assert _has_nhs("NHS no: 943 476 5919")


def test_rule_detects_comma_form():
    assert _has_nhs("NHS: 943,476,5919")


def test_rule_detects_9_digit_context():
    assert _has_nhs("Patient NHS Number: 272 733 208 admitted")
