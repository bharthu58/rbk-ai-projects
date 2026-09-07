"""Required test 2 (SPEC): lifestyle / annual spending, including the
sum-mismatch case."""

from pathlib import Path

from finos.bands import UNKNOWN
from finos.lifestyle import compute_lifestyle
from finos.profile_load import load_profile

FIXTURES = Path(__file__).parent / "fixtures"

_MINIMAL_HEADER = """
synthetic: true
schema_version: 2
household:
  members:
    - role: adult_1
      age: 40
income:
  sources:
    - label: "job"
      gross_annual: 100000
      stability: stable
safety_reserve:
  target_months_of_essential: 6
scenarios:
  base: {equity_return_pct: 7, fixed_income_return_pct: 4, inflation_pct: 3, income_continues: true, longevity_age: 90}
  reasonable_downside: {equity_return_pct: 4, fixed_income_return_pct: 3, inflation_pct: 4, income_continues: true, longevity_age: 95}
"""


def test_happy_path_sums_cleanly():
    profile = load_profile(FIXTURES / "synthetic-profile.yaml")
    result = compute_lifestyle(profile)
    assert result.annual_total == 96000
    assert result.essential == 60000
    assert result.sum_of_parts == 96000
    assert result.matches_total is True
    assert result.discrepancy == 0


def test_sum_mismatch_is_reported_not_reconciled():
    profile = load_profile(FIXTURES / "sum-mismatch-profile.yaml")
    result = compute_lifestyle(profile)
    assert result.matches_total is False
    assert result.discrepancy != 0
    # Reported values are exactly what the profile declared — never silently
    # adjusted to make them agree.
    assert result.essential == 50000
    assert result.lifestyle == 20000
    assert result.discretionary == 20000
    assert result.annual_total == 80000


def test_unknown_essential_propagates_and_never_becomes_zero(tmp_path):
    yaml_text = _MINIMAL_HEADER + """
spending:
  annual_total: 80000
  lifestyle: 20000
  discretionary: 10000
"""
    path = tmp_path / "profile.yaml"
    path.write_text(yaml_text)
    profile = load_profile(path)

    result = compute_lifestyle(profile)
    assert result.essential is UNKNOWN
    assert result.sum_of_parts is UNKNOWN
    assert result.matches_total is UNKNOWN
    assert result.discrepancy is UNKNOWN
    # Explicitly not zero — an Unknown essential must never present as $0.
    assert result.essential != 0
