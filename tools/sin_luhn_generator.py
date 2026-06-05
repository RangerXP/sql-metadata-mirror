"""
SIN Luhn Generator — Layer 1 of the SIN classifier backstop strategy.

Generates Luhn-valid 9-digit Canadian Social Insurance Numbers for the
Enercare Purview demo. Used by nb_05a_publish_synthetic_data_to_sql to
populate dbo.employees.sin_full and dbo.customers.sin_last_4 with values
that satisfy the built-in MICROSOFT.CANADIAN.SIN classifier.

These are SYNTHETIC values for a demo. They are never real persons' SINs.

See docs/purview-sin-classifier-backstop.md for the full strategy.
"""

import random


def luhn_check_digit(first_8: str) -> str:
    """Compute the 9th-digit Luhn check digit for the given 8 leading digits.

    The Canadian SIN uses the Luhn algorithm: starting from position 2 (1-indexed)
    every other digit is doubled; if the doubled value is >= 10, sum its digits
    (equivalent to subtracting 9). The 9th digit makes the total sum divisible by 10.
    """
    if len(first_8) != 8 or not first_8.isdigit():
        raise ValueError("first_8 must be exactly 8 numeric digits")

    total = 0
    for i, ch in enumerate(first_8):
        digit = int(ch)
        # 0-indexed positions 1, 3, 5, 7 -> 1-indexed positions 2, 4, 6, 8 are doubled
        if i % 2 == 1:
            doubled = digit * 2
            digit = doubled if doubled < 10 else doubled - 9
        total += digit

    check = (10 - (total % 10)) % 10
    return str(check)


def generate_synthetic_sin(first_digit: str = "9", rng: random.Random | None = None) -> str:
    """Generate a Luhn-valid 9-digit Canadian SIN.

    first_digit conventions:
        1   Atlantic provinces (or Ontario since 2021)
        2-3 Quebec
        4-5 Ontario (historical primary range)
        6   Prairies
        7   British Columbia and Territories
        9   Temporary Resident (default for synthetic data — unambiguous)

    Digits 0 and 8 are not assigned to individual SINs and will raise ValueError.
    """
    if first_digit not in {"1", "2", "3", "4", "5", "6", "7", "9"}:
        raise ValueError(
            f"first_digit must be in 1-7 or 9; got {first_digit!r}. "
            "0 and 8 are not assigned to Canadian individual SINs."
        )

    r = rng if rng is not None else random
    middle = "".join(str(r.randint(0, 9)) for _ in range(7))
    body = first_digit + middle
    check = luhn_check_digit(body)
    return body + check


def hyphenated(sin9: str) -> str:
    """Format a 9-digit SIN as XXX-XXX-XXX."""
    if len(sin9) != 9 or not sin9.isdigit():
        raise ValueError("Input must be 9 numeric digits")
    return f"{sin9[0:3]}-{sin9[3:6]}-{sin9[6:9]}"


def spaced(sin9: str) -> str:
    """Format a 9-digit SIN as XXX XXX XXX."""
    if len(sin9) != 9 or not sin9.isdigit():
        raise ValueError("Input must be 9 numeric digits")
    return f"{sin9[0:3]} {sin9[3:6]} {sin9[6:9]}"


def is_luhn_valid(candidate: str) -> bool:
    """Verify a 9-digit SIN candidate passes the Luhn checksum."""
    candidate = candidate.replace("-", "").replace(" ", "")
    if len(candidate) != 9 or not candidate.isdigit():
        return False
    return luhn_check_digit(candidate[:8]) == candidate[8]


if __name__ == "__main__":
    # Self-test using 130 692 544 — a documented Luhn-valid demo SIN frequently
    # used in Government of Canada examples.
    assert luhn_check_digit("13069254") == "4", "Luhn check digit calculation broken"
    assert is_luhn_valid("130692544"), "Luhn validator broken"
    assert is_luhn_valid("130-692-544"), "Luhn validator should ignore hyphens"
    assert not is_luhn_valid("130692543"), "Luhn validator should reject invalid"

    rng = random.Random(42)  # Reproducible
    samples = [generate_synthetic_sin("9", rng) for _ in range(5)]
    for s in samples:
        assert is_luhn_valid(s), f"Generated SIN {s} failed Luhn check"
        print(f"  {hyphenated(s)}   ({s})")

    print("\nAll self-tests passed.")
