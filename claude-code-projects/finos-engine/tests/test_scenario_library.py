"""F2 criterion 11 (override tagged-union validation) and criterion 12
(expected_outcome.status: APPROVED_TARGET requires every binding pinned)."""

import copy
from pathlib import Path

import pytest
import yaml

from finos.registry_load import load_registry
from finos.scenario_library import (
    ScenarioLibraryValidationError,
    ScenarioOverrideError,
    load_scenario_library,
)

FIXTURES = Path(__file__).parent / "fixtures" / "v3"


def _registry_path():
    return FIXTURES / "registry-minimal.yaml"


def _registry():
    return load_registry(_registry_path())


def _profile_raw() -> dict:
    return yaml.safe_load((FIXTURES / "profile-v3-minimal-short.yaml").read_text())


def _minimal_library() -> dict:
    return copy.deepcopy(yaml.safe_load((FIXTURES / "scenario-library-minimal.yaml").read_text()))


def _write(tmp_path, name: str, data: dict) -> Path:
    path = tmp_path / name
    path.write_text(yaml.dump(data))
    return path


# --------------------------------------------------------------------------
# Valid load
# --------------------------------------------------------------------------


def test_minimal_valid_scenario_library_loads():
    library = load_scenario_library(FIXTURES / "scenario-library-minimal.yaml", registry=_registry())
    assert "core-baseline" in library.scenarios
    assert library.scenarios["core-baseline"].expected_outcome.status == "APPROVED_TARGET"


def test_profile_path_validation_is_syntax_only_when_no_profile_supplied():
    """A caller must be able to tell 'paths were resolved against a real
    profile' apart from 'paths were only syntax-checked' from the returned
    object alone — not by inferring it from the load having succeeded."""
    library = load_scenario_library(FIXTURES / "scenario-library-minimal.yaml", registry=_registry())
    assert library.profile_path_validation == "syntax_only"


def test_profile_path_validation_is_resolved_when_profile_supplied():
    library = load_scenario_library(
        FIXTURES / "scenario-library-minimal.yaml", registry=_registry(), profile_raw=_profile_raw(),
    )
    assert library.profile_path_validation == "resolved"


def test_override_path_resolves_against_a_supplied_profile():
    library = load_scenario_library(
        FIXTURES / "scenario-library-minimal.yaml", registry=_registry(), profile_raw=_profile_raw(),
    )
    override = library.scenarios["retire-earlier-adult-1"].overrides[0]
    assert override.path == "household.members[id=adult_1].retirement.target_age"


def test_override_path_dangling_against_a_supplied_profile_is_rejected(tmp_path):
    data = _minimal_library()
    data["scenarios"][1]["overrides"][0]["path"] = "household.members[id=nobody].retirement.target_age"
    with pytest.raises(ScenarioOverrideError):
        load_scenario_library(_write(tmp_path, "scenarios.yaml", data), registry=_registry(), profile_raw=_profile_raw())


# --------------------------------------------------------------------------
# Criterion 11 — override tagged union
# --------------------------------------------------------------------------


def test_target_profile_forbids_parameter_binding_fields(tmp_path):
    data = _minimal_library()
    override = data["scenarios"][1]["overrides"][0]
    override["parameter_role"] = "general_inflation"  # forbidden alongside target: profile
    with pytest.raises(ScenarioOverrideError):
        load_scenario_library(_write(tmp_path, "scenarios.yaml", data), registry=_registry())


def test_target_profile_requires_both_path_and_value(tmp_path):
    data = _minimal_library()
    del data["scenarios"][1]["overrides"][0]["value"]
    with pytest.raises(ScenarioOverrideError):
        load_scenario_library(_write(tmp_path, "scenarios.yaml", data), registry=_registry())


def test_target_parameter_binding_forbids_profile_fields(tmp_path):
    data = _minimal_library()
    override = data["scenarios"][1]["overrides"][1]
    override["path"] = "spending.essential"  # forbidden alongside target: parameter_binding
    with pytest.raises(ScenarioOverrideError):
        load_scenario_library(_write(tmp_path, "scenarios.yaml", data), registry=_registry())


def test_target_parameter_binding_requires_both_parameter_role_and_rebind_to(tmp_path):
    data = _minimal_library()
    del data["scenarios"][1]["overrides"][1]["rebind_to"]
    with pytest.raises(ScenarioOverrideError):
        load_scenario_library(_write(tmp_path, "scenarios.yaml", data), registry=_registry())


def test_pinned_requires_pinned_version(tmp_path):
    data = _minimal_library()
    del data["scenarios"][1]["overrides"][1]["rebind_to"]["pinned_version"]
    with pytest.raises(ScenarioOverrideError):
        load_scenario_library(_write(tmp_path, "scenarios.yaml", data), registry=_registry())


def test_pinned_version_must_resolve_to_a_published_version(tmp_path):
    data = _minimal_library()
    data["scenarios"][1]["overrides"][1]["rebind_to"]["pinned_version"] = 99
    with pytest.raises(ScenarioOverrideError):
        load_scenario_library(_write(tmp_path, "scenarios.yaml", data), registry=_registry())


def test_latest_must_not_carry_a_stale_pinned_version(tmp_path):
    data = _minimal_library()
    data["scenarios"][1]["overrides"][1]["rebind_to"]["version_policy"] = "latest"
    # pinned_version left in place — that is the stale pin.
    with pytest.raises(ScenarioOverrideError):
        load_scenario_library(_write(tmp_path, "scenarios.yaml", data), registry=_registry())


def test_parameter_role_must_resolve_against_the_registry(tmp_path):
    data = _minimal_library()
    data["scenarios"][1]["overrides"][1]["parameter_role"] = "made_up_role"
    with pytest.raises(ScenarioOverrideError):
        load_scenario_library(_write(tmp_path, "scenarios.yaml", data), registry=_registry())


def test_assumption_id_must_resolve_against_the_registry(tmp_path):
    data = _minimal_library()
    data["scenarios"][1]["overrides"][1]["rebind_to"]["assumption_id"] = "does-not-exist"
    with pytest.raises(ScenarioOverrideError):
        load_scenario_library(_write(tmp_path, "scenarios.yaml", data), registry=_registry())


def test_reason_is_required(tmp_path):
    data = _minimal_library()
    del data["scenarios"][1]["overrides"][0]["reason"]
    with pytest.raises(ScenarioLibraryValidationError):
        load_scenario_library(_write(tmp_path, "scenarios.yaml", data), registry=_registry())


# --------------------------------------------------------------------------
# Criterion 12 — expected_outcome.status: APPROVED_TARGET requires every
# binding in the scenario's assumption_set to be pinned
# --------------------------------------------------------------------------


def test_criterion_12_approved_target_with_a_latest_binding_is_rejected(tmp_path):
    registry_data = yaml.safe_load(_registry_path().read_text())
    registry_data["assumption_sets"].append({
        "id": "downside_latest",
        "name": "Downside (tracks latest, synthetic)",
        "status": "DRAFT",
        "bindings": [{
            "role": "general_inflation",
            "assumption_id": "general-inflation-base",
            "version_policy": "latest",
        }],
    })
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(yaml.dump(registry_data))
    registry = load_registry(registry_path)

    library_data = _minimal_library()
    library_data["scenarios"][0]["assumption_set"] = "downside_latest"
    # expected_outcome.status is already APPROVED_TARGET on scenarios[0] (core-baseline).
    with pytest.raises(ScenarioLibraryValidationError):
        load_scenario_library(_write(tmp_path, "scenarios.yaml", library_data), registry=registry)


def test_criterion_12_approved_target_with_all_pinned_bindings_succeeds():
    """Positive control for criterion 12 — the fixture's core-baseline
    scenario is APPROVED_TARGET against the fully-pinned 'base' set."""
    library = load_scenario_library(FIXTURES / "scenario-library-minimal.yaml", registry=_registry())
    assert library.scenarios["core-baseline"].expected_outcome.status == "APPROVED_TARGET"
