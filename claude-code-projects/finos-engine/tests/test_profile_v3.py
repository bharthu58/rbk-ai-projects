"""F2 criterion 3 (Field[T] short/long equality) plus one rejection test per
criterion 4, 5, 6, 7, 8, 9, 13 — proving the v3 loader refuses bad input, not
merely that it accepts good input."""

import copy
import dataclasses
from pathlib import Path

import pytest
import yaml

from finos.field_meta import FieldValidationError
from finos.profile_load import load_profile
from finos.profile_v3 import ProfileV3ReferenceError, ProfileV3ValidationError
from finos.registry_load import load_registry

FIXTURES = Path(__file__).parent / "fixtures" / "v3"
V2_FIXTURES = Path(__file__).parent / "fixtures"


def _registry():
    return load_registry(FIXTURES / "registry-minimal.yaml")


def _minimal_short() -> dict:
    return copy.deepcopy(yaml.safe_load((FIXTURES / "profile-v3-minimal-short.yaml").read_text()))


def _write(tmp_path, data: dict) -> Path:
    path = tmp_path / "profile.yaml"
    path.write_text(yaml.dump(data))
    return path


# --------------------------------------------------------------------------
# Valid loads + criterion 3
# --------------------------------------------------------------------------


def test_v2_profile_still_loads_via_the_same_entry_point():
    """schema_version 2 is entirely unaffected by F2 — no registry needed."""
    profile = load_profile(V2_FIXTURES / "synthetic-profile.yaml")
    assert profile.schema_version == 2


def test_minimal_valid_v3_profile_loads_short_form():
    profile = load_profile(FIXTURES / "profile-v3-minimal-short.yaml", registry=_registry())
    assert profile.schema_version == 3
    assert len(profile.household) == 3
    assert profile.spending.essential == 60000


def test_minimal_valid_v3_profile_loads_long_form():
    profile = load_profile(FIXTURES / "profile-v3-minimal-long.yaml", registry=_registry())
    assert profile.spending.essential == 60000
    assert profile.field_meta["spending.essential"].status == "ESTIMATE"


def test_v3_without_registry_fails_closed():
    from finos.profile_load import RegistryRequiredError
    with pytest.raises(RegistryRequiredError):
        load_profile(FIXTURES / "profile-v3-minimal-short.yaml")


def test_criterion_3_short_and_long_form_are_equal_on_every_non_metadata_field():
    registry = _registry()
    short_profile = load_profile(FIXTURES / "profile-v3-minimal-short.yaml", registry=registry)
    long_profile = load_profile(FIXTURES / "profile-v3-minimal-long.yaml", registry=registry)

    short_no_meta = dataclasses.replace(short_profile, field_meta={})
    long_no_meta = dataclasses.replace(long_profile, field_meta={})
    assert short_no_meta == long_no_meta

    # And the long form actually carries metadata the short form does not.
    assert short_profile.field_meta == {}
    assert long_profile.field_meta != {}
    assert long_profile.field_meta["spending.essential"].value == 60000


# --------------------------------------------------------------------------
# Criterion 4 — dollar-class validation
# --------------------------------------------------------------------------


def test_criterion_4_wrong_dollar_class_on_a_field_fails_closed(tmp_path):
    data = _minimal_short()
    data["income"]["sources"][0]["gross_annual"] = {
        "value": 150000, "status": "ESTIMATE", "dollar_class": "point_in_time_nominal",
    }
    with pytest.raises(FieldValidationError):
        load_profile(_write(tmp_path, data), registry=_registry())


def test_criterion_4_projected_nominal_rejected_in_profile_context(tmp_path):
    data = _minimal_short()
    data["investments"][0]["approx_value"] = {
        "value": 200000, "status": "ESTIMATE", "dollar_class": "projected_nominal",
    }
    with pytest.raises(FieldValidationError):
        load_profile(_write(tmp_path, data), registry=_registry())


# --------------------------------------------------------------------------
# Criterion 5 — typed reference resolution (lifecycle events, parameter
# roles, statutory facts)
# --------------------------------------------------------------------------


def test_criterion_5_dangling_lifecycle_event_member_ref_fails_closed(tmp_path):
    data = _minimal_short()
    data["income"]["sources"][0]["ends_at"] = "retirement:does_not_exist"
    with pytest.raises(ProfileV3ReferenceError):
        load_profile(_write(tmp_path, data), registry=_registry())


def test_criterion_5_dangling_parameter_role_fails_closed(tmp_path):
    data = _minimal_short()
    data["income"]["sources"][0]["growth_parameter_role"] = "made_up_role"
    with pytest.raises(ProfileV3ReferenceError):
        load_profile(_write(tmp_path, data), registry=_registry())


def test_criterion_5_dangling_statutory_fact_ref_fails_closed(tmp_path):
    data = _minimal_short()
    data["contributions"][0]["limit_policy"]["statutory_fact_ref"] = "made-up-fact"
    with pytest.raises(ProfileV3ReferenceError):
        load_profile(_write(tmp_path, data), registry=_registry())


# --------------------------------------------------------------------------
# Criterion 6 — derived_from / annual_amount exclusivity
# --------------------------------------------------------------------------


def test_criterion_6_derived_from_with_annual_amount_is_rejected(tmp_path):
    data = _minimal_short()
    data["spending"]["categories"][0]["annual_amount"] = 1800  # alongside derived_from
    with pytest.raises(ProfileV3ValidationError):
        load_profile(_write(tmp_path, data), registry=_registry())


def test_criterion_6_neither_derived_from_nor_annual_amount_is_rejected(tmp_path):
    data = _minimal_short()
    del data["spending"]["categories"][0]["derived_from"]
    with pytest.raises(ProfileV3ValidationError):
        load_profile(_write(tmp_path, data), registry=_registry())


# --------------------------------------------------------------------------
# Criterion 7 — cross-section id collisions
# --------------------------------------------------------------------------


def test_criterion_7_id_collision_between_liquid_and_investments_is_rejected(tmp_path):
    data = _minimal_short()
    data["investments"][1]["id"] = "operating_cash"  # collides with liquid[0].id
    with pytest.raises(ProfileV3ValidationError):
        load_profile(_write(tmp_path, data), registry=_registry())


# --------------------------------------------------------------------------
# Criterion 8 — healthcare fail-closed validation
# --------------------------------------------------------------------------


def test_criterion_8_dependent_coverage_available_to_dangling_ref_is_rejected(tmp_path):
    data = _minimal_short()
    data["household"]["members"][0]["healthcare"]["availability"]["dependent_coverage_available_to"] = ["nobody"]
    with pytest.raises(ProfileV3ReferenceError):
        load_profile(_write(tmp_path, data), registry=_registry())


def test_criterion_8_election_dependent_of_dangling_ref_is_rejected(tmp_path):
    data = _minimal_short()
    data["household"]["members"][1]["healthcare"]["elections"][0]["elected"] = "dependent_of:nobody"
    with pytest.raises(ProfileV3ReferenceError):
        load_profile(_write(tmp_path, data), registry=_registry())


# --------------------------------------------------------------------------
# Criterion 9 — contribution reference and exclusivity validation
# --------------------------------------------------------------------------


def test_criterion_9_account_ref_dangling_is_rejected(tmp_path):
    data = _minimal_short()
    data["contributions"][0]["account_ref"] = "no_such_account"
    with pytest.raises(ProfileV3ReferenceError):
        load_profile(_write(tmp_path, data), registry=_registry())


def test_criterion_9_amount_and_formula_both_set_is_rejected(tmp_path):
    data = _minimal_short()
    data["contributions"][0]["formula"] = {"kind": "pct_of_income", "pct": 5, "income_source_ref": "income_adult_1"}
    with pytest.raises(ProfileV3ValidationError):
        load_profile(_write(tmp_path, data), registry=_registry())


def test_criterion_9_neither_amount_nor_formula_is_rejected(tmp_path):
    data = _minimal_short()
    del data["contributions"][0]["amount"]
    with pytest.raises(ProfileV3ValidationError):
        load_profile(_write(tmp_path, data), registry=_registry())


def test_criterion_9_formula_income_source_ref_dangling_is_rejected(tmp_path):
    data = _minimal_short()
    del data["contributions"][0]["amount"]
    data["contributions"][0]["formula"] = {"kind": "pct_of_income", "pct": 5, "income_source_ref": "no_such_income"}
    with pytest.raises(ProfileV3ReferenceError):
        load_profile(_write(tmp_path, data), registry=_registry())


def test_criterion_9_invalid_contribution_status_is_rejected(tmp_path):
    data = _minimal_short()
    data["contributions"][0]["status"] = "MADE_UP"
    with pytest.raises(ProfileV3ValidationError):
        load_profile(_write(tmp_path, data), registry=_registry())


# --------------------------------------------------------------------------
# Criterion 13 — funding_policy.order parses and validates; no algorithm
# --------------------------------------------------------------------------


def test_criterion_13_unknown_funding_policy_order_is_rejected(tmp_path):
    data = _minimal_short()
    data["education"][0]["funding_policy"]["order"] = "aggressive_529_first"
    with pytest.raises(ProfileV3ValidationError):
        load_profile(_write(tmp_path, data), registry=_registry())


def test_criterion_13_smoothed_non_529_parses_with_no_algorithm_available():
    """The order value round-trips; there is no smoothing function anywhere
    in this module to call — asserted by absence, not by behaviour."""
    import finos.profile_v3 as profile_v3
    assert not hasattr(profile_v3, "compute_smoothed_schedule")
    profile = load_profile(FIXTURES / "profile-v3-minimal-short.yaml", registry=_registry())
    assert profile.education[0].funding_policy.order == "smoothed_non_529"
