"""Required test 1 (SPEC): profile loading — valid, and each malformed fixture
raises the right typed error."""

from pathlib import Path

import pytest

from finos.bands import UNKNOWN
from finos.profile_load import (
    ProfileFileError,
    ProfileFormatError,
    ProfileValidationError,
    SchemaVersionError,
    SyntheticFlagError,
    load_profile,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_valid_synthetic_profile_loads():
    profile = load_profile(FIXTURES / "synthetic-profile.yaml")
    assert profile.synthetic is True
    assert profile.schema_version == 2
    assert len(profile.household) == 3
    assert profile.spending.annual_total == 96000


def test_valid_profile_propagates_unknown_for_missing_optional_fields():
    profile = load_profile(FIXTURES / "synthetic-profile.yaml")
    assert profile.income_net_annual_estimate is UNKNOWN
    assert profile.income_sources[1].growth_assumption_pct is UNKNOWN
    # Present fields must NOT be Unknown.
    assert profile.income_sources[0].growth_assumption_pct == 3


def test_missing_file_raises_profile_file_error():
    with pytest.raises(ProfileFileError):
        load_profile(FIXTURES / "does-not-exist.yaml")


def test_malformed_yaml_raises_profile_format_error():
    with pytest.raises(ProfileFormatError):
        load_profile(FIXTURES / "malformed-yaml-syntax.yaml")


def test_missing_synthetic_flag_raises_synthetic_flag_error():
    with pytest.raises(SyntheticFlagError):
        load_profile(FIXTURES / "malformed-missing-synthetic-flag.yaml")


def test_unknown_schema_version_raises_schema_version_error():
    with pytest.raises(SchemaVersionError):
        load_profile(FIXTURES / "malformed-unknown-schema-version.yaml")


def test_negative_age_raises_profile_validation_error():
    with pytest.raises(ProfileValidationError):
        load_profile(FIXTURES / "malformed-negative-values.yaml")


def test_sum_mismatch_profile_loads_successfully():
    """Loading succeeds even though essential+lifestyle+discretionary != total —
    that inconsistency is lifestyle.py's job to report, not profile_load's job
    to reject (see test_lifestyle.py)."""
    profile = load_profile(FIXTURES / "sum-mismatch-profile.yaml")
    assert profile.spending.annual_total == 80000


def test_load_profile_is_read_only(tmp_path):
    """profile_load must never write to the path it's given."""
    src = FIXTURES / "synthetic-profile.yaml"
    target = tmp_path / "profile.yaml"
    target.write_text(src.read_text())
    before = target.read_text()
    before_mtime = target.stat().st_mtime

    load_profile(target)

    assert target.read_text() == before
    assert target.stat().st_mtime == before_mtime
