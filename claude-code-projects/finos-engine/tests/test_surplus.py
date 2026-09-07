"""Required test 6 (SPEC 3B-4) + T1-T4 (SPEC 3B-4a): surplus — positive, zero,
negative, refusal when resilience is Unknown, retirement as a hard
prerequisite, and the unrestricted/restriction_reason semantics."""

from pathlib import Path

import pytest

from finos.bands import UNKNOWN
from finos.lifestyle import compute_lifestyle
from finos.obligations import compute_obligations
from finos.profile_load import load_profile
from finos.resilience import compute_resilience
from finos.retirement import compute_retirement
from finos.surplus import compute_surplus

FIXTURES = Path(__file__).parent / "fixtures"

_HEADER = """
synthetic: true
schema_version: 2
"""

_RETIREMENT_GOALS = """
household:
  members: [{role: adult_1, age: 45, target_retirement_age: 65}]
goals:
  retirement:
    target_age_adult_1: 65
    desired_annual_spending: 60000
    social_security_estimate_annual: 30000
    other_retirement_income: 10000
"""

_SCENARIOS = """
scenarios:
  base: {equity_return_pct: 7, fixed_income_return_pct: 4, inflation_pct: 3, income_continues: true, longevity_age: 90}
  reasonable_downside: {equity_return_pct: 4, fixed_income_return_pct: 3, inflation_pct: 4, income_continues: true, longevity_age: 95}
"""


def _load(tmp_path, body):
    path = tmp_path / "profile.yaml"
    path.write_text(_HEADER + body)
    return load_profile(path)


def _run(profile, as_of_year=2026):
    lifestyle = compute_lifestyle(profile)
    resilience = compute_resilience(profile, lifestyle)
    obligations = compute_obligations(profile, as_of_year=as_of_year)
    retirement = compute_retirement(profile)
    return compute_surplus(resilience, obligations, retirement, profile)


def test_negative_surplus_names_the_blocking_requirement():
    """Primary fixture: reserve underfunded AND retirement shortfall — proves
    blocked_by (amount<=0) and restriction_reason (retirement) coexist without
    being confused for each other."""
    profile = load_profile(FIXTURES / "synthetic-profile.yaml")
    result = _run(profile)

    assert result.status == "negative"
    assert result.amount == -73500
    assert result.blocked_by == "safety reserve is not yet fully funded"
    assert result.retirement_status == "shortfall"
    assert result.unrestricted is False
    assert result.restriction_reason is not None


def test_positive_surplus_retirement_on_track_is_unrestricted(tmp_path):
    """T4: retirement on track + positive amount -> unrestricted=True,
    restriction_reason is None."""
    profile = _load(tmp_path, _RETIREMENT_GOALS + """
income:
  sources: [{label: "job", gross_annual: 150000, stability: stable}]
spending: {annual_total: 65000, essential: 40000, lifestyle: 18000, discretionary: 7000}
liquid:
  - {label: "operating cash", approx_value: 5000, access: immediate, purpose: operating}
  - {label: "emergency reserve", approx_value: 12000, access: immediate, purpose: safety_reserve}
investments:
  - {label: "401k", approx_value: 800000, tax_treatment: tax_deferred, liquidity: penalty_before_age,
     intended_purpose: retirement, allocation: {equity_pct: 60, fixed_income_pct: 40}}
  - {label: "brokerage", approx_value: 60000, tax_treatment: taxable, liquidity: immediate,
     intended_purpose: long_term_surplus, allocation: {equity_pct: 60, fixed_income_pct: 40}}
safety_reserve: {target_months_of_essential: 3}
""" + _SCENARIOS)
    result = _run(profile)

    assert result.status == "positive"
    assert result.amount == 61500
    assert result.retirement_status == "on_track"
    assert result.unrestricted is True
    assert result.restriction_reason is None
    assert result.blocked_by is None


def test_positive_surplus_retirement_shortfall_is_not_unrestricted_but_not_blocked(tmp_path):
    """T3: retirement shortfall + positive amount -> unrestricted=False, the
    arithmetic (amount) is UNCHANGED from the on-track case, restriction_reason
    is set (not blocked_by), and its wording conveys 'not unrestricted, not
    immobilised' rather than 'do nothing'."""
    shortfall_goals = _RETIREMENT_GOALS.replace("desired_annual_spending: 60000", "desired_annual_spending: 180000")
    profile = _load(tmp_path, shortfall_goals + """
income:
  sources: [{label: "job", gross_annual: 150000, stability: stable}]
spending: {annual_total: 65000, essential: 40000, lifestyle: 18000, discretionary: 7000}
liquid:
  - {label: "operating cash", approx_value: 5000, access: immediate, purpose: operating}
  - {label: "emergency reserve", approx_value: 12000, access: immediate, purpose: safety_reserve}
investments:
  - {label: "small ira", approx_value: 40000, tax_treatment: tax_deferred, liquidity: penalty_before_age,
     intended_purpose: retirement, allocation: {equity_pct: 60, fixed_income_pct: 40}}
  - {label: "brokerage", approx_value: 60000, tax_treatment: taxable, liquidity: immediate,
     intended_purpose: long_term_surplus, allocation: {equity_pct: 60, fixed_income_pct: 40}}
safety_reserve: {target_months_of_essential: 3}
""" + _SCENARIOS)
    result = _run(profile)

    assert result.status == "positive"
    assert result.amount == 61500  # identical to the on-track case above — arithmetic unchanged
    assert result.retirement_status == "shortfall"
    assert result.unrestricted is False
    assert result.blocked_by is None  # this IS surplus-shaped; it is just not unrestricted
    assert result.restriction_reason is not None
    assert "not unrestricted" in result.restriction_reason.lower()
    assert "not immobilised" in result.restriction_reason.lower() or "not immobilized" in result.restriction_reason.lower()
    # The naive "shortfall therefore do nothing" reading must be impossible to reach from this text.
    assert "do nothing" not in result.restriction_reason.lower()


def test_zero_surplus(tmp_path):
    profile = _load(tmp_path, _RETIREMENT_GOALS + """
income:
  sources: [{label: "job", gross_annual: 100000, stability: stable}]
spending: {annual_total: 40000, essential: 24000, lifestyle: 10000, discretionary: 6000}
liquid:
  - {label: "operating cash", approx_value: 2500, access: immediate, purpose: operating}
  - {label: "emergency reserve", approx_value: 12500, access: immediate, purpose: safety_reserve}
investments:
  - {label: "401k", approx_value: 800000, tax_treatment: tax_deferred, liquidity: penalty_before_age,
     intended_purpose: retirement, allocation: {equity_pct: 60, fixed_income_pct: 40}}
safety_reserve: {target_months_of_essential: 6}
""" + _SCENARIOS)
    result = _run(profile)

    assert result.status == "zero"
    assert result.amount == 0


def test_refuses_to_compute_when_resilience_is_unknown(tmp_path):
    profile = _load(tmp_path, """
household:
  members: [{role: adult_1, age: 40}]
income:
  sources: [{label: "job", gross_annual: 100000, stability: stable}]
spending: {annual_total: 60000, lifestyle: 15000, discretionary: 5000}
liquid:
  - {label: "operating cash", approx_value: 5000, access: immediate, purpose: operating}
safety_reserve: {target_months_of_essential: 3}
""" + _SCENARIOS)
    result = _run(profile)

    assert result.status == "unknown"
    assert result.amount is UNKNOWN
    assert result.blocked_by == "resilience"


def test_refuses_to_compute_when_retirement_is_unknown(tmp_path):
    """T2: no household/goals retirement-age info at all -> retirement unknown
    -> surplus refuses, blocked_by='retirement', mirroring the resilience case."""
    profile = _load(tmp_path, """
household:
  members: [{role: adult_1, age: 40}]
income:
  sources: [{label: "job", gross_annual: 100000, stability: stable}]
spending: {annual_total: 60000, essential: 40000, lifestyle: 15000, discretionary: 5000}
liquid:
  - {label: "operating cash", approx_value: 20000, access: immediate, purpose: operating}
safety_reserve: {target_months_of_essential: 3}
""" + _SCENARIOS)
    result = _run(profile)

    assert result.status == "unknown"
    assert result.amount is UNKNOWN
    assert result.blocked_by == "retirement"
    assert result.retirement_status == "unknown"


def test_compute_surplus_cannot_be_called_without_retirement_result():
    """T1: compute_surplus cannot be called without a RetirementResult."""
    from finos.resilience import ResilienceResult
    from finos.obligations import ObligationsResult
    from finos.bands import Range

    resilience = ResilienceResult(required=Range(1000, 2000), held=5000, funded=True,
                                   months_covered=6, explanation="")
    obligations = ObligationsResult(per_obligation=[], near_term_gap=0, long_term_gap=0,
                                     flagged_low_risk_capacity=[], as_of_year=2026)
    profile = load_profile(FIXTURES / "synthetic-profile.yaml")

    with pytest.raises(TypeError):
        compute_surplus(resilience, obligations, profile)  # missing `retirement`
