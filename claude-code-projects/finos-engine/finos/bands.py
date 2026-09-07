"""Shared rounding/banding helper (State/State.md §1.9 precision policy) and the
two cross-cutting value types every other module in this engine depends on:

- `Unknown` / `UNKNOWN` — a first-class "genuinely unknown" value, never zero
  (Phase 3B-4 SPEC rule 2). `bool(UNKNOWN)` deliberately raises rather than
  silently evaluating falsy, since that is the exact bug this type exists to
  prevent — a caller must write `is UNKNOWN`, never rely on truthiness.
- `Range` — a low/high pair for every projection- or assumption-driven result
  (rule 4: ranges, not point estimates).

No network, no file I/O, no dependency on any other module in this package.
"""

from dataclasses import dataclass


class Unknown:
    """Singleton sentinel. A missing field means *unknown*, distinct from zero."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "Unknown"

    def __bool__(self) -> bool:
        raise TypeError(
            "Unknown has no truth value — coercing it to zero/false is exactly the "
            "bug this type exists to prevent. Check `value is UNKNOWN` explicitly."
        )

    def __eq__(self, other) -> bool:
        return other is self

    def __hash__(self) -> int:
        return hash("__FINANCIAL_OS_UNKNOWN__")


UNKNOWN = Unknown()


def is_unknown(value) -> bool:
    return value is UNKNOWN


@dataclass(frozen=True)
class Range:
    """A low/high pair. Never constructed from a single point estimate without
    both ends being deliberate — a projection with no real uncertainty should
    still state low == high rather than skip the type."""

    low: float
    high: float

    def __post_init__(self):
        if self.low > self.high:
            raise ValueError(f"Range low ({self.low}) must not exceed high ({self.high})")

    def midpoint(self) -> float:
        return (self.low + self.high) / 2

    def __contains__(self, value) -> bool:
        return self.low <= value <= self.high


def _band(value, nearest: float):
    if value is UNKNOWN:
        return UNKNOWN
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"cannot band a non-numeric value: {value!r}")
    return round(value / nearest) * nearest


def round_spending(value):
    """Nearest $1K."""
    return _band(value, 1_000)


def round_asset(value):
    """Nearest $5K — assets, investments, income, future obligations all share
    this precision per §1.9."""
    return _band(value, 5_000)


def round_income(value):
    """Nearest $5K."""
    return _band(value, 5_000)


def round_allocation_pct(value):
    """Nearest 5%."""
    return _band(value, 5)


def round_range_spending(range_: Range | Unknown):
    if range_ is UNKNOWN:
        return UNKNOWN
    return Range(round_spending(range_.low), round_spending(range_.high))


def round_range_asset(range_: Range | Unknown):
    if range_ is UNKNOWN:
        return UNKNOWN
    return Range(round_asset(range_.low), round_asset(range_.high))
