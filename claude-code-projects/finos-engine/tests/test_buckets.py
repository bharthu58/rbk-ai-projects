"""Required test 3 (SPEC): bucket determination across purpose/horizon/
liquidity combinations."""

from pathlib import Path

from finos.buckets import (
    CURRENT_LIFESTYLE,
    EDUCATION_FAMILY,
    LONG_TERM_SURPLUS,
    NEAR_TERM_OBLIGATIONS,
    RETIREMENT_CAPITAL,
    SAFETY_RESERVE,
    compute_buckets,
)
from finos.profile_load import load_profile

FIXTURES = Path(__file__).parent / "fixtures"


def _by_label(allocation, label):
    return next(a for a in allocation.assignments if a.item_label == label)


def test_liquid_assets_classified_by_label_purpose():
    profile = load_profile(FIXTURES / "synthetic-profile.yaml")
    allocation = compute_buckets(profile)

    assert _by_label(allocation, "operating cash").bucket == CURRENT_LIFESTYLE
    assert _by_label(allocation, "emergency reserve").bucket == SAFETY_RESERVE


def test_investments_classified_by_intended_purpose():
    profile = load_profile(FIXTURES / "synthetic-profile.yaml")
    allocation = compute_buckets(profile)

    assert _by_label(allocation, "workplace retirement - adult_1").bucket == RETIREMENT_CAPITAL
    assert _by_label(allocation, "workplace retirement - adult_2").bucket == RETIREMENT_CAPITAL
    assert _by_label(allocation, "taxable brokerage").bucket == LONG_TERM_SURPLUS
    assert _by_label(allocation, "529 - child_1").bucket == EDUCATION_FAMILY
    assert _by_label(allocation, "near-term house-repair fund").bucket == NEAR_TERM_OBLIGATIONS


def test_bucket_totals_sum_correctly():
    profile = load_profile(FIXTURES / "synthetic-profile.yaml")
    allocation = compute_buckets(profile)

    retirement_total = next(t for t in allocation.totals if t.bucket == RETIREMENT_CAPITAL)
    assert retirement_total.total_value == 220000 + 150000
    assert retirement_total.item_count == 2
    assert retirement_total.has_any_funding is True


def test_never_classified_by_account_type():
    """Two investments with the same tax_treatment (tax_deferred) must be able
    to land in different buckets purely because their intended_purpose differs
    — proves classification is not keyed on account type."""
    profile = load_profile(FIXTURES / "synthetic-profile.yaml")
    allocation = compute_buckets(profile)
    tax_deferred_labels = {"workplace retirement - adult_1", "workplace retirement - adult_2"}
    buckets_seen = {_by_label(allocation, label).bucket for label in tax_deferred_labels}
    assert buckets_seen == {RETIREMENT_CAPITAL}  # both retirement-purposed -> same bucket despite being two accounts


def test_empty_bucket_has_no_funding(tmp_path):
    minimal = """
synthetic: true
schema_version: 2
household:
  members:
    - role: adult_1
      age: 40
income:
  sources:
    - {label: "job", gross_annual: 100000, stability: stable}
spending: {annual_total: 60000, essential: 40000, lifestyle: 15000, discretionary: 5000}
liquid:
  - {label: "operating cash", approx_value: 5000, access: immediate, purpose: operating}
safety_reserve: {target_months_of_essential: 6}
scenarios:
  base: {equity_return_pct: 7, fixed_income_return_pct: 4, inflation_pct: 3, income_continues: true, longevity_age: 90}
  reasonable_downside: {equity_return_pct: 4, fixed_income_return_pct: 3, inflation_pct: 4, income_continues: true, longevity_age: 95}
"""
    path = tmp_path / "profile.yaml"
    path.write_text(minimal)
    profile = load_profile(path)
    allocation = compute_buckets(profile)

    current_lifestyle_total = next(t for t in allocation.totals if t.bucket == CURRENT_LIFESTYLE)
    assert current_lifestyle_total.has_any_funding is True

    retirement_total = next(t for t in allocation.totals if t.bucket == RETIREMENT_CAPITAL)
    assert retirement_total.total_value == 0
    assert retirement_total.has_any_funding is False
