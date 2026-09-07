"""Required test 4 (SPEC): resilience — funded, underfunded, and Unknown
essential-spend."""

from pathlib import Path

from finos.bands import UNKNOWN
from finos.lifestyle import compute_lifestyle
from finos.profile_load import load_profile
from finos.resilience import compute_resilience

FIXTURES = Path(__file__).parent / "fixtures"

_HEADER = """
synthetic: true
schema_version: 2
household:
  members: [{role: adult_1, age: 40}]
income:
  sources: [{label: "job", gross_annual: 100000, stability: stable}]
scenarios:
  base: {equity_return_pct: 7, fixed_income_return_pct: 4, inflation_pct: 3, income_continues: true, longevity_age: 90}
  reasonable_downside: {equity_return_pct: 4, fixed_income_return_pct: 3, inflation_pct: 4, income_continues: true, longevity_age: 95}
"""


def test_underfunded_reserve():
    profile = load_profile(FIXTURES / "synthetic-profile.yaml")
    lifestyle = compute_lifestyle(profile)
    result = compute_resilience(profile, lifestyle)

    assert result.held == 22000
    assert result.required.midpoint() == 30000
    assert result.funded is False
    assert result.months_covered < profile.safety_reserve.target_months_of_essential


def test_funded_reserve(tmp_path):
    yaml_text = _HEADER + """
spending: {annual_total: 60000, essential: 40000, lifestyle: 15000, discretionary: 5000}
liquid:
  - {label: "operating cash", approx_value: 8000, access: immediate}
  - {label: "emergency reserve", approx_value: 15000, access: days}
safety_reserve: {target_months_of_essential: 3}
"""
    path = tmp_path / "profile.yaml"
    path.write_text(yaml_text)
    profile = load_profile(path)
    lifestyle = compute_lifestyle(profile)
    result = compute_resilience(profile, lifestyle)

    # required = 3 * (40000/12) = 10000; held = 23000
    assert result.held == 23000
    assert result.funded is True
    assert result.months_covered > 3


def test_weeks_access_liquid_excluded_from_held(tmp_path):
    yaml_text = _HEADER + """
spending: {annual_total: 60000, essential: 40000, lifestyle: 15000, discretionary: 5000}
liquid:
  - {label: "cd ladder", approx_value: 50000, access: weeks}
safety_reserve: {target_months_of_essential: 3}
"""
    path = tmp_path / "profile.yaml"
    path.write_text(yaml_text)
    profile = load_profile(path)
    lifestyle = compute_lifestyle(profile)
    result = compute_resilience(profile, lifestyle)

    assert result.held == 0  # "weeks" access does not count toward the reserve
    assert result.funded is False


def test_unknown_essential_makes_reserve_unanswerable_not_zero(tmp_path):
    yaml_text = _HEADER + """
spending: {annual_total: 60000, lifestyle: 15000, discretionary: 5000}
liquid:
  - {label: "operating cash", approx_value: 8000, access: immediate}
safety_reserve: {target_months_of_essential: 3}
"""
    path = tmp_path / "profile.yaml"
    path.write_text(yaml_text)
    profile = load_profile(path)
    lifestyle = compute_lifestyle(profile)
    result = compute_resilience(profile, lifestyle)

    assert result.required is UNKNOWN
    assert result.funded is UNKNOWN
    assert result.months_covered is UNKNOWN
    assert "unanswerable" in result.explanation.lower()
    # held is still computable (doesn't depend on essential spend)
    assert result.held == 8000
