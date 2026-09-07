"""F2 criterion 10 (required parameter roles must be bound; pinned assumption
versions must exist) plus the reference-resolution checks that back it."""

import copy
from pathlib import Path

import pytest
import yaml

from finos.registry_load import (
    RegistryReferenceError,
    RegistryValidationError,
    load_registry,
)

FIXTURES = Path(__file__).parent / "fixtures" / "v3"


def _minimal_valid_registry() -> dict:
    return copy.deepcopy(yaml.safe_load((FIXTURES / "registry-minimal.yaml").read_text()))


def _write(tmp_path, data: dict) -> Path:
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.dump(data))
    return path


def test_minimal_valid_registry_loads():
    registry = load_registry(FIXTURES / "registry-minimal.yaml")
    assert "general_inflation" in registry.parameters
    assert registry.parameters["general_inflation"].required is True
    assert ("general-inflation-base", 1) in registry.assumptions
    assert "base" in registry.assumption_sets


def test_criterion_10_unbound_required_role_fails_closed(tmp_path):
    data = _minimal_valid_registry()
    # Add a second required role with no binding anywhere.
    data["parameters"].append({"role": "equity_return", "units": "pct_annual", "required": True})
    with pytest.raises(RegistryReferenceError):
        load_registry(_write(tmp_path, data))


def test_criterion_10_pinned_version_must_exist(tmp_path):
    data = _minimal_valid_registry()
    data["assumption_sets"][0]["bindings"][0]["pinned_version"] = 99
    with pytest.raises(RegistryReferenceError):
        load_registry(_write(tmp_path, data))


def test_binding_role_must_resolve_against_parameters(tmp_path):
    data = _minimal_valid_registry()
    data["assumption_sets"][0]["bindings"][0]["role"] = "does_not_exist"
    with pytest.raises(RegistryReferenceError):
        load_registry(_write(tmp_path, data))


def test_binding_assumption_id_must_resolve(tmp_path):
    data = _minimal_valid_registry()
    data["assumption_sets"][0]["bindings"][0]["assumption_id"] = "does-not-exist"
    with pytest.raises(RegistryReferenceError):
        load_registry(_write(tmp_path, data))


def test_assumption_role_must_resolve_against_parameters(tmp_path):
    data = _minimal_valid_registry()
    data["assumptions"][0]["role"] = "does_not_exist"
    with pytest.raises(RegistryReferenceError):
        load_registry(_write(tmp_path, data))


def test_assumption_status_actual_is_rejected(tmp_path):
    """An assumption is a belief, never a measured fact — ACTUAL belongs to
    statutory_facts[] or the Profile, not here."""
    data = _minimal_valid_registry()
    data["assumptions"][0]["status"] = "ACTUAL"
    with pytest.raises(RegistryValidationError):
        load_registry(_write(tmp_path, data))


def test_projected_nominal_rejected_on_an_assumption(tmp_path):
    data = _minimal_valid_registry()
    data["assumptions"][0]["dollar_class"] = "projected_nominal"
    with pytest.raises(RegistryValidationError):
        load_registry(_write(tmp_path, data))


def test_latest_binding_must_not_carry_a_stale_pinned_version(tmp_path):
    data = _minimal_valid_registry()
    data["assumption_sets"][0]["bindings"][0]["version_policy"] = "latest"
    # pinned_version left in place from the fixture — that's the stale pin.
    with pytest.raises(RegistryValidationError):
        load_registry(_write(tmp_path, data))
