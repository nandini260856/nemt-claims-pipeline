"""
Python validation rules that are awkward to write in SQL.

The NPI (National Provider Identifier) has a built-in check digit. A claim with an
invalid NPI is rejected by the payer, so we catch it before we send anything.
"""
import re

X12_UNSAFE = re.compile(r"[~*:^]")  # characters that would break an EDI file


def npi_check_digit(first_nine: str) -> int:
    """Luhn check digit for an NPI. The '80840' prefix adds a constant 24."""
    total = 24
    for i, ch in enumerate(reversed(first_nine)):
        d = int(ch)
        if i % 2 == 0:  # double every other digit, starting from the right
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return (10 - total % 10) % 10


def is_valid_npi(npi: str) -> bool:
    if not npi or len(npi) != 10 or not npi.isdigit() or npi[0] not in "12":
        return False
    return npi_check_digit(npi[:9]) == int(npi[9])


def has_x12_unsafe_chars(value: str) -> bool:
    return bool(X12_UNSAFE.search(value or ""))
