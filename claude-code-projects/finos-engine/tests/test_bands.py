"""bands.py: Unknown sentinel, Range type, §1.9 rounding helpers."""

import pytest

from finos.bands import UNKNOWN, Range, round_allocation_pct, round_asset, round_income, round_spending


def test_unknown_is_a_singleton():
    from finos.bands import Unknown
    assert Unknown() is UNKNOWN


def test_unknown_bool_raises_instead_of_coercing_to_false():
    """Rule 2: coercing Unknown to zero/false is the exact bug this type exists
    to prevent — accidental `if value:` must not silently treat it as falsy."""
    with pytest.raises(TypeError):
        bool(UNKNOWN)
    with pytest.raises(TypeError):
        if UNKNOWN:
            pass


def test_round_spending_nearest_1k():
    assert round_spending(60499) == 60000
    assert round_spending(60501) == 61000


def test_round_asset_nearest_5k():
    assert round_asset(222000) == 220000
    assert round_asset(223000) == 225000


def test_round_income_nearest_5k():
    assert round_income(97499) == 95000


def test_round_allocation_nearest_5pct():
    assert round_allocation_pct(82) == 80
    assert round_allocation_pct(83) == 85


def test_rounding_propagates_unknown():
    assert round_spending(UNKNOWN) is UNKNOWN
    assert round_asset(UNKNOWN) is UNKNOWN
    assert round_income(UNKNOWN) is UNKNOWN
    assert round_allocation_pct(UNKNOWN) is UNKNOWN


def test_range_rejects_low_greater_than_high():
    with pytest.raises(ValueError):
        Range(low=100, high=50)


def test_range_midpoint_and_contains():
    r = Range(low=100, high=200)
    assert r.midpoint() == 150
    assert 150 in r
    assert 250 not in r
