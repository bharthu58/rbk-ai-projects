"""Phase 3B-5: synthetic end-to-end validation. Exercises the complete
nine-stage flow (Profile -> Lifestyle -> Buckets -> Resilience -> Obligations
-> Retirement -> Surplus -> Attestation -> Packet) on six synthetic
households, asserting every stage rather than just the final number.

Scenario F is also the regression test for Phase 3B-4b's C8: written to fail
against pre-C8 code (obligations status blind to long-term gaps) and pass
after. See the completion report in aoe-gateway/State.md for the recorded
fail-then-pass run.
"""

from pathlib import Path

import pytest

from finos.bands import UNKNOWN
from finos.buckets import compute_buckets
from finos.lifestyle import compute_lifestyle
from finos.obligations import compute_obligations
from finos.packet import Finding, PacketInputs, build_packet
from finos.profile_load import load_profile
from finos.resilience import compute_resilience
from finos.retirement import compute_retirement
from finos.surplus import attest_hierarchy, compute_surplus

FIXTURES = Path(__file__).parent / "fixtures"
AS_OF_YEAR = 2026


def _run_pipeline(fixture_name: str, as_of_year: int = AS_OF_YEAR):
    """Runs all nine stages and returns every intermediate result, so a test
    can assert on each stage rather than only the final packet."""
    profile = load_profile(FIXTURES / fixture_name)
    lifestyle = compute_lifestyle(profile)
    buckets = compute_buckets(profile)
    resilience = compute_resilience(profile, lifestyle)
    obligations = compute_obligations(profile, as_of_year=as_of_year)
    retirement = compute_retirement(profile)
    surplus = compute_surplus(resilience, obligations, retirement, profile)
    hierarchy = attest_hierarchy(resilience, obligations, retirement, surplus)
    return {
        "profile": profile, "lifestyle": lifestyle, "buckets": buckets,
        "resilience": resilience, "obligations": obligations, "retirement": retirement,
        "surplus": surplus, "hierarchy": hierarchy,
    }


def _build_packet_for(stages: dict, question_slug: str) -> str:
    findings = (
        Finding(label="Surplus status", value=stages["surplus"].status),
        Finding(label="Retirement (base)", value=stages["hierarchy"].retirement),
    )
    return build_packet(
        PacketInputs(findings=findings), hierarchy=stages["hierarchy"],
        question_slug=question_slug, purpose="end-to-end validation",
        sanitizer_version="test", removed=(), retained=("banded summary",),
        generated_date="2026-01-01",
    )


# ---------------------------------------------------------------------
# Scenario A — Healthy / on-track
# ---------------------------------------------------------------------

def test_scenario_a_healthy_on_track():
    s = _run_pipeline("scenario-a-healthy.yaml")

    assert s["hierarchy"].safety == "funded"
    assert s["hierarchy"].obligations == "funded"
    assert s["hierarchy"].retirement == "on_track"
    assert s["hierarchy"].surplus == "positive"
    assert s["hierarchy"].unrestricted is True
    assert s["surplus"].classification_warnings == ()
    assert s["buckets"].unclassified == ()


# ---------------------------------------------------------------------
# Scenario B — Insufficient retirement trajectory
# ---------------------------------------------------------------------

def test_scenario_b_retirement_shortfall_not_unrestricted_amount_unchanged():
    a = _run_pipeline("scenario-a-healthy.yaml")
    b = _run_pipeline("scenario-b-retirement-shortfall.yaml")

    assert b["hierarchy"].retirement == "shortfall"
    assert b["hierarchy"].surplus == "positive"
    assert b["hierarchy"].unrestricted is False
    assert b["surplus"].restriction_reason is not None
    assert b["surplus"].blocked_by is None
    # T3's invariant, re-proved end to end: amount is byte-identical to A.
    assert b["surplus"].amount == a["surplus"].amount


# ---------------------------------------------------------------------
# Scenario C — Insufficient safety reserve
# ---------------------------------------------------------------------

def test_scenario_c_reserve_underfunded():
    s = _run_pipeline("scenario-c-reserve-underfunded.yaml")

    assert s["hierarchy"].safety == "underfunded"
    assert s["hierarchy"].surplus == "negative"
    assert s["surplus"].blocked_by is not None
    assert "reserve" in s["surplus"].blocked_by.lower()
    assert s["hierarchy"].unrestricted is False
    assert s["surplus"].restriction_reason is None


# ---------------------------------------------------------------------
# Scenario D — Unknown / unclassified
# ---------------------------------------------------------------------

def test_scenario_d_unknown_and_unclassified():
    s = _run_pipeline("scenario-d-unknown-unclassified.yaml")

    assert s["surplus"].status == "unknown"
    assert s["surplus"].blocked_by == "resilience"
    assert s["hierarchy"].safety == "unknown"

    unclassified_labels = {a.item_label for a in s["buckets"].unclassified}
    assert unclassified_labels == {"misc savings", "random account", "mystery fund"}

    warnings_text = " ".join(s["surplus"].classification_warnings)
    for label in ("misc savings", "random account", "mystery fund"):
        assert label in warnings_text

    # Nothing silently defaults to operating cash.
    from finos.buckets import CURRENT_LIFESTYLE
    for item in s["buckets"].unclassified:
        assert item.bucket != CURRENT_LIFESTYLE


# ---------------------------------------------------------------------
# Scenario E — Meaningful ongoing contributions
# ---------------------------------------------------------------------

def test_scenario_e_contribution_flips_verdict():
    without = _run_pipeline("scenario-e-contribution-unknown.yaml")
    with_ = _run_pipeline("scenario-e-contribution-present.yaml")

    assert without["retirement"].base.sustainable is False
    assert without["retirement"].base.contributions_modeled is False

    assert with_["retirement"].base.sustainable is True
    assert with_["retirement"].base.contributions_modeled is True

    assert without["hierarchy"].retirement == "shortfall"
    assert with_["hierarchy"].retirement == "on_track"


# ---------------------------------------------------------------------
# Scenario F — Long-term obligation gap only (C8 regression test)
# ---------------------------------------------------------------------

def test_scenario_f_long_term_gap_only():
    s = _run_pipeline("scenario-f-long-term-gap.yaml")

    assert s["obligations"].near_term_gap == 0
    assert s["obligations"].long_term_gap > 0
    assert s["hierarchy"].obligations == "long_term_gap_only"


# ---------------------------------------------------------------------
# Cross-cutting assertions — all six scenarios
# ---------------------------------------------------------------------

_ALL_SCENARIO_FIXTURES = [
    "scenario-a-healthy.yaml",
    "scenario-b-retirement-shortfall.yaml",
    "scenario-c-reserve-underfunded.yaml",
    "scenario-d-unknown-unclassified.yaml",
    "scenario-e-contribution-present.yaml",
    "scenario-e-contribution-unknown.yaml",
    "scenario-f-long-term-gap.yaml",
]


@pytest.mark.parametrize("fixture_name", _ALL_SCENARIO_FIXTURES)
def test_full_chain_executes_and_attestation_matches_computed_facts(fixture_name):
    """Cross-cutting assertion 1: no drift between the numbers and the attestation."""
    s = _run_pipeline(fixture_name)
    h = s["hierarchy"]

    if s["resilience"].funded is UNKNOWN:
        assert h.safety == "unknown"
    else:
        assert h.safety == ("funded" if s["resilience"].funded else "underfunded")

    assert h.surplus == s["surplus"].status
    assert h.as_of_year == s["obligations"].as_of_year == AS_OF_YEAR
    assert h.unrestricted == s["surplus"].unrestricted


@pytest.mark.parametrize("fixture_name", _ALL_SCENARIO_FIXTURES)
def test_packet_requires_hierarchy_and_contains_no_raw_fixture_values(fixture_name):
    """Cross-cutting assertion 2. build_packet's signature cannot accept a
    Profile at all (proved once, structurally, in test_packet.py), so this
    re-proves it end to end: every raw approx_value/cost/balance figure that
    exists anywhere in this scenario's fixture must be absent from the
    packet, since _build_packet_for only ever passes two status strings."""
    s = _run_pipeline(fixture_name)
    text = _build_packet_for(s, question_slug="e2e-test")

    raw_values = set()
    for item in s["profile"].liquid:
        raw_values.add(item.approx_value)
    for item in s["profile"].investments:
        raw_values.add(item.approx_value)
    for o in s["profile"].obligations:
        raw_values.add(o.estimated_total_cost)
        raw_values.add(o.already_funded)

    for value in raw_values:
        assert str(int(value)) not in text, f"{fixture_name}: raw value {value} leaked into packet"


@pytest.mark.parametrize("fixture_name", _ALL_SCENARIO_FIXTURES)
def test_as_of_year_explicit_present_and_identical_across_repeat_runs(fixture_name):
    """Cross-cutting assertion 3."""
    first = _run_pipeline(fixture_name, as_of_year=2026)
    second = _run_pipeline(fixture_name, as_of_year=2026)
    assert first["hierarchy"].as_of_year == 2026
    assert first["hierarchy"].as_of_year == second["hierarchy"].as_of_year


@pytest.mark.parametrize("fixture_name", _ALL_SCENARIO_FIXTURES)
def test_determinism_repeat_run_produces_byte_identical_packet(fixture_name):
    """Cross-cutting assertion 4."""
    first = _run_pipeline(fixture_name)
    second = _run_pipeline(fixture_name)

    packet_first = _build_packet_for(first, question_slug="determinism-check")
    packet_second = _build_packet_for(second, question_slug="determinism-check")

    assert packet_first == packet_second


def test_no_network_egress_across_all_scenarios(monkeypatch):
    """Cross-cutting assertion 5, part 1."""
    import socket

    def _blocked(*args, **kwargs):
        raise AssertionError("socket.socket() was called during end-to-end validation")

    monkeypatch.setattr(socket, "socket", _blocked)

    for fixture_name in _ALL_SCENARIO_FIXTURES:
        _run_pipeline(fixture_name)


def test_profile_load_read_only_across_all_scenarios():
    """Cross-cutting assertion 5, part 2."""
    for fixture_name in _ALL_SCENARIO_FIXTURES:
        path = FIXTURES / fixture_name
        before = path.read_text()
        load_profile(path)
        assert path.read_text() == before


def test_every_scenario_fixture_declares_synthetic_true():
    """Cross-cutting assertion 5, part 3."""
    import yaml
    for fixture_name in _ALL_SCENARIO_FIXTURES:
        raw = yaml.safe_load((FIXTURES / fixture_name).read_text())
        assert raw.get("synthetic") is True, fixture_name
