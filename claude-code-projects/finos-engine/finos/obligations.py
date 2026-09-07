"""obligations: Profile -> ObligationsResult.

Per obligation: required, funded, gap, years to target. The **near-term gap
(target <= 5 years out)** is aggregated separately, because that is the
capital that comes out of surplus before any optimization question is even
askable (State.md decision hierarchy).

Also flags any obligation with near-zero risk capacity regardless of horizon
— a `flexibility: fixed` obligation is "money that must be there" even if it
is years away (State.md §1.7's college-in-six-years example).

**Phase 3B-4a, C5:** `as_of_year` is a required keyword argument — the
`datetime.date.today()` default was removed so any result (and any packet
built from it) is reproducible rather than silently depending on when the
code happened to run.
"""

from dataclasses import dataclass

from .profile_load import Obligation, Profile

NEAR_TERM_YEARS = 5


@dataclass(frozen=True)
class ObligationDetail:
    label: str
    required: float
    funded: float
    gap: float
    is_funded: bool
    years_to_target: int
    is_near_term: bool
    low_risk_capacity: bool


@dataclass(frozen=True)
class ObligationsResult:
    per_obligation: "list[ObligationDetail]"
    near_term_gap: float
    long_term_gap: float
    flagged_low_risk_capacity: "list[str]"
    as_of_year: int


def compute_obligations(profile: Profile, *, as_of_year: int) -> ObligationsResult:
    details = []
    flagged: list[str] = []
    near_term_gap = 0.0
    long_term_gap = 0.0

    for o in profile.obligations:
        gap = o.estimated_total_cost - o.already_funded
        is_funded = gap <= 0
        years_to_target = o.target_year - as_of_year
        is_near_term = years_to_target <= NEAR_TERM_YEARS
        # "Money that must be there" — inflexible regardless of how far out it is.
        low_risk_capacity = o.flexibility == "fixed"

        if low_risk_capacity:
            flagged.append(o.label)

        if gap > 0:
            if is_near_term:
                near_term_gap += gap
            else:
                long_term_gap += gap

        details.append(ObligationDetail(
            label=o.label, required=o.estimated_total_cost, funded=o.already_funded,
            gap=gap, is_funded=is_funded, years_to_target=years_to_target,
            is_near_term=is_near_term, low_risk_capacity=low_risk_capacity,
        ))

    return ObligationsResult(
        per_obligation=details,
        near_term_gap=near_term_gap,
        long_term_gap=long_term_gap,
        flagged_low_risk_capacity=flagged,
        as_of_year=as_of_year,
    )
