"""Anonymisation vault + operator policy."""
from src.anonymize import MODE_PSEUDONYMISE, MODE_REDACT, Vault, build_operators
from src.recognizers.nhs_number import is_valid_nhs_number


def test_pseudonyms_are_consistent():
    vault = Vault(seed=1)
    assert vault.name("Wells, Judith") == vault.name("Wells, Judith")
    assert vault.name("Wells, Judith") != vault.name("Smith, John")


def test_fake_nhs_number_passes_checksum():
    vault = Vault(seed=2)
    fake = vault.nhs("943 476 5919")
    assert is_valid_nhs_number(fake)
    assert fake != "943 476 5919"


def test_postcode_reduced_to_outward_code():
    vault = Vault(seed=3)
    assert vault.postcode("SW1A 1AA") == "SW1A"
    assert vault.postcode("M1 1AE") == "M1"


def test_nino_and_vehicle_formats():
    vault = Vault(seed=4)
    import re
    assert re.fullmatch(r"[A-Z]{2}\d{6}[A-D]", vault.nino("x"))
    assert re.fullmatch(r"[A-Z]{2}\d{2} [A-Z]{3}", vault.vehicle("x"))


def test_date_shift_preserves_intervals():
    vault = Vault(seed=5)
    from dateutil import parser
    a = parser.parse(vault.date("01/01/2000"), dayfirst=True)
    b = parser.parse(vault.date("01/02/2000"), dayfirst=True)
    assert (b - a).days == 31  # one consistent offset -> interval preserved


def test_redact_mode_uses_default_operator():
    assert build_operators(MODE_REDACT, Vault(seed=6)) == {}


def test_pseudonymise_has_person_and_redacts_nrp():
    ops = build_operators(MODE_PSEUDONYMISE, Vault(seed=7))
    assert "PERSON" in ops and ops["PERSON"].operator_name == "custom"
    assert ops["NRP"].operator_name == "replace"  # special-category data is redacted, never synthesised
