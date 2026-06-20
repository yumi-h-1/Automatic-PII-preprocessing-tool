"""NHS number Modulus-11 checksum + recognizer validation."""
from src.recognizers.nhs_number import NhsNumberRecognizer, is_valid_nhs_number, nhs_check_digit

VALID = "9434765919"  # 943 476 591 -> check digit 9


def test_check_digit_known_value():
    assert nhs_check_digit("943476591") == 9


def test_valid_number():
    assert is_valid_nhs_number(VALID)


def test_separated_forms_are_valid():
    assert is_valid_nhs_number("943 476 5919")
    assert is_valid_nhs_number("943,476,5919")


def test_invalid_checksum_rejected():
    # 1234567890 has a check digit of 10 by construction -> invalid.
    assert not is_valid_nhs_number("1234567890")
    assert nhs_check_digit("123456789") is None


def test_wrong_length_rejected():
    assert not is_valid_nhs_number("12345")
    assert not is_valid_nhs_number("94347659190")


def test_recognizer_validate_result():
    rec = NhsNumberRecognizer()
    assert rec.validate_result(VALID) is True
    assert rec.validate_result("943 476 5919") is True
    assert rec.validate_result("1234567890") is False
