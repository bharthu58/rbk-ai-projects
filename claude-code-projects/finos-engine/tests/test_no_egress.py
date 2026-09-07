"""Required test 10 (SPEC): no network / external egress. This is the only
mechanical proof that the engine is what it claims to be.

Two layers: a static import check (nothing in scripts/ even imports a
networking module), and a runtime test that makes networking impossible
(monkeypatches socket.socket to raise) and then runs the full pipeline
end-to-end on the synthetic fixture, proving it never needed the network.
"""

import ast
import socket
from pathlib import Path

import pytest

from finos.lifestyle import compute_lifestyle
from finos.buckets import compute_buckets
from finos.obligations import compute_obligations
from finos.packet import Finding, PacketInputs, build_packet
from finos.profile_load import load_profile
from finos.resilience import compute_resilience
from finos.retirement import compute_retirement
from finos.surplus import attest_hierarchy, compute_surplus

SCRIPTS_DIR = Path(__file__).parent.parent / "finos"
FIXTURES = Path(__file__).parent / "fixtures"

_FORBIDDEN_MODULES = {"socket", "requests", "urllib", "http", "smtplib", "ftplib", "telnetlib"}
_EXPECTED_MODULE_COUNT = 9  # the nine calculation modules; excludes __init__.py


def _imported_top_level_modules(py_file: Path) -> set:
    tree = ast.parse(py_file.read_text(), filename=str(py_file))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    return modules


def test_no_script_imports_a_networking_module():
    module_files = [p for p in SCRIPTS_DIR.glob("*.py") if p.stem != "__init__"]
    assert len(module_files) == _EXPECTED_MODULE_COUNT, (
        f"expected {_EXPECTED_MODULE_COUNT} modules under {SCRIPTS_DIR}, "
        f"found {len(module_files)}: {[p.name for p in module_files]} — "
        "a glob matching the wrong count means this test would pass vacuously"
    )
    offenders = []
    for py_file in module_files:
        found = _imported_top_level_modules(py_file) & _FORBIDDEN_MODULES
        if found:
            offenders.append(f"{py_file.name}: {found}")
    assert offenders == [], f"networking imports found: {offenders}"


def test_full_pipeline_runs_with_sockets_forcibly_broken(monkeypatch):
    def _blocked(*args, **kwargs):
        raise AssertionError("socket.socket() was called — the engine is not supposed to touch the network")

    monkeypatch.setattr(socket, "socket", _blocked)

    profile = load_profile(FIXTURES / "synthetic-profile.yaml")
    lifestyle = compute_lifestyle(profile)
    buckets = compute_buckets(profile)
    resilience = compute_resilience(profile, lifestyle)
    obligations = compute_obligations(profile, as_of_year=2026)
    retirement = compute_retirement(profile)
    surplus = compute_surplus(resilience, obligations, retirement, profile)
    hierarchy = attest_hierarchy(resilience, obligations, retirement, surplus)

    inputs = PacketInputs(findings=(
        Finding(label="Annual essential spending", value=f"${lifestyle.essential:,.0f}"),
        Finding(label="Reserve funded", value=str(resilience.funded)),
        Finding(label="Surplus status", value=surplus.status),
        Finding(label="Retirement (base) sustainable", value=str(retirement.base.sustainable)),
    ))
    packet_text = build_packet(
        inputs, hierarchy=hierarchy, question_slug="pipeline-smoke-test",
        purpose="prove the pipeline runs with no network access",
        sanitizer_version="test", removed=(), retained=("banded summary",), generated_date="2026-01-01",
    )

    assert buckets.totals  # pipeline genuinely executed, not skipped
    assert "pipeline-smoke-test" in packet_text
