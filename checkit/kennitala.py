"""Validation for Icelandic kennitala (national ID) numbers."""

import datetime

WEIGHTS = [3, 2, 7, 6, 5, 4, 3, 2]
CENTURY = {"8": 1800, "9": 1900, "0": 2000}


def normalize(value):
    """Return the digits of a kennitala, dropping dashes and spaces."""
    return "".join(ch for ch in str(value) if ch.isdigit())


def validate(value):
    """Check the checksum and birth date. Return (ok, message)."""
    kt = normalize(value)
    if len(kt) != 10:
        return False, "must be 10 digits"
    digits = [int(c) for c in kt]
    total = sum(w * d for w, d in zip(WEIGHTS, digits))
    check = 11 - (total % 11)
    if check == 11:
        check = 0
    if check == 10:
        return False, "invalid check digit"
    if check != digits[8]:
        return False, f"checksum mismatch (expected {check})"
    if kt[9] not in CENTURY:
        return False, "unknown century marker"
    day, month, year = int(kt[0:2]), int(kt[2:4]), CENTURY[kt[9]] + int(kt[4:6])
    try:
        datetime.date(year, month, day)
    except ValueError:
        return False, "impossible birth date"
    return True, f"valid (born {day:02d}.{month:02d}.{year})"
