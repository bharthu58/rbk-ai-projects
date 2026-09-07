"""retirement: Profile -> RetirementResult.

Simple deterministic projection, **Base and Reasonable Downside only** — no
Monte Carlo, no tax engine, no probability distributions (State.md §1.8).
Grows currently-held retirement capital forward at the scenario's blended
return, inflates desired spending, subtracts Social Security/other income,
and tests sustainability year-by-year to `longevity_age`.

**"Output ranges" is satisfied here by reporting Base and Downside side by
side** rather than inventing a second uncertainty band inside one already-
deterministic scenario — that is the practical range this module can produce
without turning into the Monte Carlo engine it is explicitly told not to be.
Flagged as an interpretation, same as surplus.py's "available capital" note.

**Phase 3B-4a, C3 — single annual contribution.** The accumulation phase now
runs as an explicit year-by-year loop (`capital = capital*(1+return) +
annual_contribution`) rather than a closed-form compounding formula, so one
flat ongoing contribution can be added without a schedule, escalation, or
per-account modelling — still "plain, readable Python you can check by hand."
If `goals.retirement.annual_contribution` is `Unknown`, the projection uses
zero, sets `contributions_modeled=False`, and attaches a `caveat` stating the
result is a **floor that understates sustainability** — explicit, per the
"Unknown is never zero" rule, never silent.
"""

from dataclasses import dataclass

from .bands import UNKNOWN, Unknown
from .profile_load import Profile, ScenarioAssumptions

_UNKNOWN_CONTRIBUTION_CAVEAT = (
    "annual_contribution is unknown; this projection assumed $0/year ongoing savings. "
    "That makes projected_capital_at_retirement a FLOOR — the true figure is understated, "
    "not overstated, if the household is in fact still contributing."
)


@dataclass(frozen=True)
class ScenarioProjection:
    scenario: str  # "base" | "reasonable_downside"
    years_to_retirement: "int | Unknown"
    years_in_retirement: "int | Unknown"
    projected_capital_at_retirement: "float | Unknown"
    annual_spending_need_at_retirement: "float | Unknown"
    sustainable: "bool | Unknown"
    depleted_at_age: "int | None | Unknown"
    contributions_modeled: bool
    caveat: "str | None"
    assumptions: dict


@dataclass(frozen=True)
class RetirementResult:
    base: ScenarioProjection
    downside: ScenarioProjection
    explanation: str


def _years_to_retirement(profile: Profile) -> "tuple[int, int] | Unknown":
    """Earliest of the two adults' (current_age, target_retirement_age) pairs —
    conservative: tests sustainability from the earliest point either spouse
    might actually retire."""
    goals = profile.retirement_goals
    pairs = []
    for member in profile.household:
        if member.role == "adult_1" and goals.target_age_adult_1 is not UNKNOWN:
            pairs.append((member.age, goals.target_age_adult_1))
        elif member.role == "adult_2" and goals.target_age_adult_2 is not UNKNOWN:
            pairs.append((member.age, goals.target_age_adult_2))

    if not pairs:
        return UNKNOWN
    current_age, target_age = min(pairs, key=lambda p: p[1] - p[0])
    return current_age, target_age


def _blended_return(profile: Profile, scenario: ScenarioAssumptions) -> "tuple[float, float] | Unknown":
    """(retirement_capital, value-weighted blended annual return as a fraction).
    Simplification: each investment's allocation collapses to equity_pct vs.
    everything else (fixed_income return applied to the remainder) — a v1
    approximation, documented rather than silently precise-looking."""
    retirement_investments = [inv for inv in profile.investments if inv.intended_purpose == "retirement"]
    if not retirement_investments:
        return UNKNOWN

    total_capital = sum(inv.approx_value for inv in retirement_investments)
    if total_capital <= 0:
        return UNKNOWN

    weighted_return = 0.0
    weighted_value = 0.0
    for inv in retirement_investments:
        equity_pct = inv.allocation.equity_pct
        if equity_pct is UNKNOWN:
            continue  # excluded from the blend; principal is still counted in total_capital
        equity_frac = equity_pct / 100
        blended = equity_frac * (scenario.equity_return_pct / 100) + (1 - equity_frac) * (scenario.fixed_income_return_pct / 100)
        weighted_return += blended * inv.approx_value
        weighted_value += inv.approx_value

    if weighted_value <= 0:
        # No investment had a known allocation — fall back to a fully fixed-income
        # assumption for the whole pool, which is the conservative direction.
        blended_return = scenario.fixed_income_return_pct / 100
    else:
        blended_return = weighted_return / weighted_value

    return total_capital, blended_return


def _project_scenario(profile: Profile, scenario: ScenarioAssumptions, *, name: str) -> ScenarioProjection:
    assumptions = {
        "equity_return_pct": scenario.equity_return_pct,
        "fixed_income_return_pct": scenario.fixed_income_return_pct,
        "inflation_pct": scenario.inflation_pct,
        "income_continues": scenario.income_continues,
        "longevity_age": scenario.longevity_age,
    }

    age_pair = _years_to_retirement(profile)
    if age_pair is UNKNOWN:
        return ScenarioProjection(
            scenario=name, years_to_retirement=UNKNOWN, years_in_retirement=UNKNOWN,
            projected_capital_at_retirement=UNKNOWN, annual_spending_need_at_retirement=UNKNOWN,
            sustainable=UNKNOWN, depleted_at_age=UNKNOWN,
            contributions_modeled=False, caveat=None, assumptions=assumptions,
        )
    current_age, retirement_age = age_pair
    years_to_retirement = max(0, retirement_age - current_age)
    years_in_retirement = max(0, scenario.longevity_age - retirement_age)

    capital_info = _blended_return(profile, scenario)
    desired_spending = profile.retirement_goals.desired_annual_spending
    if capital_info is UNKNOWN or desired_spending is UNKNOWN:
        return ScenarioProjection(
            scenario=name, years_to_retirement=years_to_retirement, years_in_retirement=years_in_retirement,
            projected_capital_at_retirement=UNKNOWN, annual_spending_need_at_retirement=UNKNOWN,
            sustainable=UNKNOWN, depleted_at_age=UNKNOWN,
            contributions_modeled=False, caveat=None, assumptions=assumptions,
        )
    retirement_capital, blended_return = capital_info

    declared_contribution = profile.retirement_goals.annual_contribution
    contributions_modeled = declared_contribution is not UNKNOWN
    annual_contribution = declared_contribution if contributions_modeled else 0
    caveat = None if contributions_modeled else _UNKNOWN_CONTRIBUTION_CAVEAT

    inflation = scenario.inflation_pct / 100

    # Year-by-year accumulation so a flat contribution can be added without a
    # closed-form annuity formula — plain and checkable by hand (SPEC rule 7).
    projected_capital = retirement_capital
    for _ in range(years_to_retirement):
        projected_capital = projected_capital * (1 + blended_return) + annual_contribution

    spending_at_retirement = desired_spending * ((1 + inflation) ** years_to_retirement)

    ss = profile.retirement_goals.social_security_estimate_annual
    other = profile.retirement_goals.other_retirement_income
    fixed_income_at_retirement = (ss if ss is not UNKNOWN else 0) + (other if other is not UNKNOWN else 0)
    fixed_income_at_retirement *= (1 + inflation) ** years_to_retirement

    net_need_year_1 = spending_at_retirement - fixed_income_at_retirement

    balance = projected_capital
    net_need = net_need_year_1
    depleted_at_age = None
    for year in range(years_in_retirement):
        balance = balance * (1 + blended_return) - net_need
        net_need *= (1 + inflation)
        if balance < 0:
            depleted_at_age = retirement_age + year + 1
            break

    sustainable = depleted_at_age is None

    return ScenarioProjection(
        scenario=name, years_to_retirement=years_to_retirement, years_in_retirement=years_in_retirement,
        projected_capital_at_retirement=projected_capital, annual_spending_need_at_retirement=net_need_year_1,
        sustainable=sustainable, depleted_at_age=depleted_at_age,
        contributions_modeled=contributions_modeled, caveat=caveat, assumptions=assumptions,
    )


def compute_retirement(profile: Profile) -> RetirementResult:
    base = _project_scenario(profile, profile.scenario_base, name="base")
    downside = _project_scenario(profile, profile.scenario_downside, name="reasonable_downside")
    explanation = (
        "Grows currently-held retirement-purposed capital at a value-weighted blended return, "
        "adding one flat annual contribution per year until retirement (C3), inflates desired "
        "spending and known fixed income to the retirement year, then tests year-by-year "
        "sustainability to each scenario's longevity_age."
    )
    return RetirementResult(base=base, downside=downside, explanation=explanation)
