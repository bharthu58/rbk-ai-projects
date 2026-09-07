"""Required test 5 (SPEC 3B-4) + T11 (SPEC 3B-4a): obligations — funded, gap,
near-term vs long-term separation, and `as_of_year` as a required kwarg."""

from pathlib import Path

import pytest

from finos.obligations import compute_obligations
from finos.profile_load import load_profile

FIXTURES = Path(__file__).parent / "fixtures"


def test_as_of_year_is_required_and_appears_on_the_result():
    """T11: compute_obligations without as_of_year -> TypeError; value appears
    in the result (packet rendering is covered by test_packet.py's hierarchy tests)."""
    profile = load_profile(FIXTURES / "synthetic-profile.yaml")
    with pytest.raises(TypeError):
        compute_obligations(profile)  # missing as_of_year

    result = compute_obligations(profile, as_of_year=2026)
    assert result.as_of_year == 2026


def test_near_term_and_long_term_gaps_separated():
    profile = load_profile(FIXTURES / "synthetic-profile.yaml")
    result = compute_obligations(profile, as_of_year=2026)

    assert result.near_term_gap == 95000   # college, 2030 - 2026 = 4y
    assert result.long_term_gap == 25000   # kitchen renovation, 2033 - 2026 = 7y


def test_per_obligation_detail_matches_declared_figures():
    profile = load_profile(FIXTURES / "synthetic-profile.yaml")
    result = compute_obligations(profile, as_of_year=2026)

    college = next(o for o in result.per_obligation if o.label == "college - child_1")
    assert college.required == 120000
    assert college.funded == 25000
    assert college.gap == 95000
    assert college.is_funded is False
    assert college.years_to_target == 4
    assert college.is_near_term is True


def test_fixed_flexibility_flagged_as_low_risk_capacity_regardless_of_horizon():
    profile = load_profile(FIXTURES / "synthetic-profile.yaml")
    result = compute_obligations(profile, as_of_year=2026)

    assert "college - child_1" in result.flagged_low_risk_capacity
    assert "kitchen renovation" not in result.flagged_low_risk_capacity  # somewhat_flexible


def test_exactly_five_years_out_counts_as_near_term(tmp_path):
    yaml_text = """
synthetic: true
schema_version: 2
household:
  members: [{role: adult_1, age: 40}]
income:
  sources: [{label: "job", gross_annual: 100000, stability: stable}]
spending: {annual_total: 60000, essential: 40000, lifestyle: 15000, discretionary: 5000}
safety_reserve: {target_months_of_essential: 3}
obligations:
  - {label: "boundary case", target_year: 2031, estimated_total_cost: 10000, already_funded: 0,
     funding_source: taxable, flexibility: flexible}
scenarios:
  base: {equity_return_pct: 7, fixed_income_return_pct: 4, inflation_pct: 3, income_continues: true, longevity_age: 90}
  reasonable_downside: {equity_return_pct: 4, fixed_income_return_pct: 3, inflation_pct: 4, income_continues: true, longevity_age: 95}
"""
    path = tmp_path / "profile.yaml"
    path.write_text(yaml_text)
    profile = load_profile(path)
    result = compute_obligations(profile, as_of_year=2026)  # 2031 - 2026 = 5

    assert result.per_obligation[0].is_near_term is True
    assert result.near_term_gap == 10000
    assert result.long_term_gap == 0


def test_overfunded_obligation_reports_no_gap(tmp_path):
    yaml_text = """
synthetic: true
schema_version: 2
household:
  members: [{role: adult_1, age: 40}]
income:
  sources: [{label: "job", gross_annual: 100000, stability: stable}]
spending: {annual_total: 60000, essential: 40000, lifestyle: 15000, discretionary: 5000}
safety_reserve: {target_months_of_essential: 3}
obligations:
  - {label: "already covered", target_year: 2028, estimated_total_cost: 10000, already_funded: 12000,
     funding_source: "529", flexibility: fixed}
scenarios:
  base: {equity_return_pct: 7, fixed_income_return_pct: 4, inflation_pct: 3, income_continues: true, longevity_age: 90}
  reasonable_downside: {equity_return_pct: 4, fixed_income_return_pct: 3, inflation_pct: 4, income_continues: true, longevity_age: 95}
"""
    path = tmp_path / "profile.yaml"
    path.write_text(yaml_text)
    profile = load_profile(path)
    result = compute_obligations(profile, as_of_year=2026)

    detail = result.per_obligation[0]
    assert detail.gap == -2000
    assert detail.is_funded is True
    assert result.near_term_gap == 0  # overfunded obligations never contribute a gap
