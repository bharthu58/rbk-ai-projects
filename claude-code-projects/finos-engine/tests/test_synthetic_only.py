"""SPEC rule 5: 'The test suite asserts it only ever loads synthetic: true.'
This is the machine-checkable line between test and real data — a meta-test
over the fixtures themselves, not over the engine."""

import os
from pathlib import Path

import pytest
import yaml

FIXTURES = Path(__file__).parent / "fixtures"

_DEFAULT_WORKSPACE_ROOT = "/mnt/e/RBK_AUR_DSKTP_AI/Workspace/financial-os"


def test_every_loadable_fixture_declares_synthetic_true():
    """Fixtures deliberately malformed to test failure paths are exempt only
    when the malformation IS the missing/invalid synthetic flag itself —
    every other fixture, including the malformed ones testing unrelated
    failure modes, must still declare synthetic: true."""
    exempt = {"malformed-missing-synthetic-flag.yaml", "malformed-yaml-syntax.yaml"}

    # F2 added tests/fixtures/v3/ for the v3 loader. Its profile-shaped
    # fixtures (profile-v3-*.yaml) carry the same `synthetic:` flag as every
    # v2 profile fixture and are checked here too. The registry and scenario
    # library fixtures in that directory are NOT profile-shaped — their
    # schemas (assumption-registry.schema.yaml, scenario-library.schema.yaml)
    # define no `synthetic` field at all — so they are out of scope for this
    # specific check, same as the Decision Register / Open Issues schemas.
    profile_shaped = list(FIXTURES.glob("*.yaml")) + list((FIXTURES / "v3").glob("profile-v3-*.yaml"))

    for fixture_path in profile_shaped:
        if fixture_path.name in exempt:
            continue
        raw = yaml.safe_load(fixture_path.read_text())
        assert raw.get("synthetic") is True, f"{fixture_path.name} must declare synthetic: true"


def test_this_repository_holds_no_real_profile():
    """No file named profile.yaml (the real profile's filename) exists
    anywhere under this repo — the boundary the repo itself is responsible
    for, now that engine code lives here rather than in the Workspace."""
    repo_root = Path(__file__).parent.parent
    real_named_files = list(repo_root.rglob("profile.yaml"))
    assert real_named_files == [], f"found file(s) named exactly 'profile.yaml': {real_named_files}"


def test_the_finos_workspace_holds_no_real_profile():
    """The real profile lives outside the Workspace entirely (State.md §2).
    This asserts the negative against the FinOS Workspace specifically —
    a separate boundary from the repo, resolved explicitly rather than
    inferred from this file's own location, so a future move of either
    side can't quietly stop this control from protecting anything.

    A Workspace root that cannot be resolved fails the test rather than
    skipping it: a skipped privacy control reports success while checking
    nothing. FINOS_ALLOW_NO_WORKSPACE_CHECK=1 is a deliberate escape hatch
    for environments with no Workspace mount, and must never be set in a
    normal run."""
    workspace_root = Path(os.environ.get("FINOS_WORKSPACE_ROOT", _DEFAULT_WORKSPACE_ROOT))

    if not workspace_root.is_dir():
        if os.environ.get("FINOS_ALLOW_NO_WORKSPACE_CHECK") == "1":
            pytest.skip(f"FINOS_WORKSPACE_ROOT not resolvable ({workspace_root}); check explicitly disabled")
        pytest.fail(
            f"FINOS_WORKSPACE_ROOT does not resolve to a directory: {workspace_root}. "
            "This privacy control cannot verify the Workspace is clean. Set FINOS_WORKSPACE_ROOT "
            "to the correct path, or set FINOS_ALLOW_NO_WORKSPACE_CHECK=1 to explicitly skip "
            "(never in a normal run)."
        )

    real_named_files = list(workspace_root.rglob("profile.yaml"))
    assert real_named_files == [], f"found file(s) named exactly 'profile.yaml': {real_named_files}"
