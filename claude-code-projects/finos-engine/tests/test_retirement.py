"""Required test 7 (SPEC 3B-4) + T9/T10 (SPEC 3B-4a): retirement — Base and
Downside, sustainable and shortfall cases, and contribution modeling."""

from pathlib import Path

from finos.bands import UNKNOWN
from finos.profile_load import load_profile
from finos.retirement import compute_retirement

FIXTURES = Path(__file__).parent / "fixtures"

_HEADER = """
synthetic: true
schema_version: 2
income:
  sources: [{label: "job", gross_annual: 100000, stability: stable}]
spending: {annual_total: 60000, essential: 40000, lifestyle: 15000, discretionary: 5000}
safety_reserve: {target_months_of_essential: 3}
scenarios:
  base: {equity_return_pct: 7, fixed_income_return_pct: 4, inflation_pct: 3, income_continues: true, longevity_age: 90}
  reasonable_downside: {equity_return_pct: 4, fixed_income_return_pct: 3, inflation_pct: 4, income_continues: true, longevity_age: 95}
"""


def _load(tmp_path, body):
    path = tmp_path / "profile.yaml"
    path.write_text(_HEADER + body)
    return load_profile(path)


def test_years_to_and_in_retirement_use_earliest_eligible_adult():
    profile = load_profile(FIXTURES / "synthetic-profile.yaml")
    result = compute_retirement(profile)

    # adult_1: 45 -> 65 (20y); adult_2: 44 -> 65 (21y); earliest wins.
    assert result.base.years_to_retirement == 20
    assert result.base.years_in_retirement == 90 - 65
    assert result.downside.years_in_retirement == 95 - 65


def test_sustainable_case_ample_capital(tmp_path):
    profile = _load(tmp_path, """
household:
  members: [{role: adult_1, age: 45, target_retirement_age: 65}]
investments:
  - {label: "401k", approx_value: 1500000, tax_treatment: tax_deferred, liquidity: penalty_before_age,
     intended_purpose: retirement, allocation: {equity_pct: 60, fixed_income_pct: 40}}
goals:
  retirement:
    target_age_adult_1: 65
    desired_annual_spending: 60000
    social_security_estimate_annual: 40000
    other_retirement_income: 10000
""")
    result = compute_retirement(profile)

    assert result.base.sustainable is True
    assert result.base.depleted_at_age is None
    assert result.base.projected_capital_at_retirement > 1500000  # grew, not just carried forward


def test_shortfall_case_thin_capital_high_spending(tmp_path):
    profile = _load(tmp_path, """
household:
  members: [{role: adult_1, age: 45, target_retirement_age: 65}]
investments:
  - {label: "small ira", approx_value: 50000, tax_treatment: tax_deferred, liquidity: penalty_before_age,
     intended_purpose: retirement, allocation: {equity_pct: 60, fixed_income_pct: 40}}
goals:
  retirement:
    target_age_adult_1: 65
    desired_annual_spending: 150000
    social_security_estimate_annual: 20000
    other_retirement_income: 0
""")
    result = compute_retirement(profile)

    assert result.base.sustainable is False
    assert result.base.depleted_at_age is not None
    assert result.base.depleted_at_age > 65  # depletes sometime during retirement, not before it starts


def test_downside_scenario_uses_its_own_assumptions_not_base():
    profile = load_profile(FIXTURES / "synthetic-profile.yaml")
    result = compute_retirement(profile)

    assert result.base.assumptions["equity_return_pct"] == 7
    assert result.downside.assumptions["equity_return_pct"] == 4
    assert result.base.assumptions["longevity_age"] == 90
    assert result.downside.assumptions["longevity_age"] == 95


def test_unknown_retirement_ages_propagate_not_zero(tmp_path):
    profile = _load(tmp_path, """
household:
  members: [{role: adult_1, age: 45}]
investments:
  - {label: "401k", approx_value: 500000, tax_treatment: tax_deferred, liquidity: penalty_before_age,
     intended_purpose: retirement, allocation: {equity_pct: 60, fixed_income_pct: 40}}
""")
    result = compute_retirement(profile)

    assert result.base.years_to_retirement is UNKNOWN
    assert result.base.sustainable is UNKNOWN


_CONTRIBUTION_BASE = """
household:
  members: [{role: adult_1, age: 45, target_retirement_age: 65}]
investments:
  - {label: "401k", approx_value: 300000, tax_treatment: tax_deferred, liquidity: penalty_before_age,
     intended_purpose: retirement, allocation: {equity_pct: 60, fixed_income_pct: 40}}
goals:
  retirement:
    target_age_adult_1: 65
    desired_annual_spending: 60000
    social_security_estimate_annual: 30000
    other_retirement_income: 5000
"""


def test_contribution_present_projects_higher_than_zero_contribution_baseline(tmp_path):
    """T9."""
    baseline_path = tmp_path / "baseline.yaml"
    baseline_path.write_text(_HEADER + _CONTRIBUTION_BASE)
    baseline = compute_retirement(load_profile(baseline_path))
    assert baseline.base.contributions_modeled is False

    contributing_path = tmp_path / "contributing.yaml"
    contributing_path.write_text(_HEADER + _CONTRIBUTION_BASE + "    annual_contribution: 15000\n")
    contributing = compute_retirement(load_profile(contributing_path))

    assert contributing.base.contributions_modeled is True
    assert contributing.base.projected_capital_at_retirement > baseline.base.projected_capital_at_retirement


def test_unknown_contribution_projects_at_zero_with_caveat(tmp_path):
    """T10."""
    profile = _load(tmp_path, _CONTRIBUTION_BASE)
    result = compute_retirement(profile)

    assert result.base.contributions_modeled is False
    assert result.base.caveat is not None
    assert "floor" in result.base.caveat.lower()
    assert "understate" in result.base.caveat.lower()
