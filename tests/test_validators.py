from nemt_claims.validators import has_x12_unsafe_chars, is_valid_npi, npi_check_digit


def test_known_valid_npi():
    # 1234567893 is the example NPI published by CMS
    assert is_valid_npi("1234567893")


def test_wrong_check_digit_fails():
    assert not is_valid_npi("1234567890")


def test_bad_formats_fail():
    for bad in ["", "123", "12345678931", "abcdefghij", "3234567893", None]:
        assert not is_valid_npi(bad)


def test_check_digit_function():
    assert npi_check_digit("123456789") == 3


def test_x12_unsafe_characters():
    assert has_x12_unsafe_chars("SMITH~JONES")
    assert not has_x12_unsafe_chars("SMITH JONES")
