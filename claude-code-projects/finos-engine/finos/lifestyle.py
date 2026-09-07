"""lifestyle: Profile -> LifestyleResult.

Annual total, essential, lifestyle, discretionary spending. Validates that the
three components sum to the declared total within rounding tolerance and
*reports* any discrepancy rather than silently reconciling it — the profile is
the source of truth, not this module's arithmetic.

Never flags lifestyle spend as a "savings opportunity" (State.md principle 4):
this module has no field or language anywhere that ranks or judges the
lifestyle/discretionary split, only reports it.
"""

from dataclasses import dataclass

from .bands import UNKNOWN, Unknown, round_spending
from .profile_load import Profile

# Three independently-rounded components (each to the nearest $1K per §1.9) can
# each be off by up to $500 from their true value, so their sum can differ from
# a fourth independently-rounded total by up to $1,500 without anything being
# actually wrong. This is a rounding-tolerance constant, not a judgement call
# about what counts as a "real" discrepancy.
SUM_TOLERANCE = 1_500


@dataclass(frozen=True)
class LifestyleResult:
    annual_total: "float | Unknown"
    essential: "float | Unknown"
    lifestyle: "float | Unknown"
    discretionary: "float | Unknown"
    sum_of_parts: "float | Unknown"
    matches_total: "bool | Unknown"
    discrepancy: "float | Unknown"
    notes: str


def compute_lifestyle(profile: Profile) -> LifestyleResult:
    spending = profile.spending
    annual_total = round_spending(spending.annual_total)
    essential = round_spending(spending.essential)
    lifestyle = round_spending(spending.lifestyle)
    discretionary = round_spending(spending.discretionary)

    parts = (essential, lifestyle, discretionary)
    if any(p is UNKNOWN for p in parts):
        sum_of_parts = UNKNOWN
    else:
        sum_of_parts = essential + lifestyle + discretionary

    if sum_of_parts is UNKNOWN or annual_total is UNKNOWN:
        matches_total = UNKNOWN
        discrepancy = UNKNOWN
    else:
        discrepancy = round(sum_of_parts - annual_total, 2)
        matches_total = abs(discrepancy) <= SUM_TOLERANCE

    return LifestyleResult(
        annual_total=annual_total,
        essential=essential,
        lifestyle=lifestyle,
        discretionary=discretionary,
        sum_of_parts=sum_of_parts,
        matches_total=matches_total,
        discrepancy=discrepancy,
        notes=spending.notes,
    )
