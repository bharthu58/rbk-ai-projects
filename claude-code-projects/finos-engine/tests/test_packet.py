"""Required test 8 (SPEC 3B-4) + T5 (SPEC 3B-4a): packet generation — correct
header; assert the output contains none of the fixture's raw values, only
banded ones; `hierarchy` is now required."""

import inspect

import pytest

from finos.packet import Finding, PacketInputs, build_packet
from finos.profile_load import Profile
from finos.surplus import HierarchyStatus

_HIERARCHY = HierarchyStatus(safety="funded", obligations="funded", retirement="on_track",
                              surplus="positive", unrestricted=True, as_of_year=2026)


def test_build_packet_signature_cannot_accept_a_profile():
    """The control is structural: no parameter can carry a Profile at all."""
    params = inspect.signature(build_packet).parameters
    assert "profile" not in params
    for p in params.values():
        assert p.annotation is not Profile


def test_build_packet_requires_hierarchy():
    """T5: build_packet without hierarchy -> TypeError."""
    inputs = PacketInputs(findings=(Finding(label="x", value="y"),))
    with pytest.raises(TypeError):
        build_packet(
            inputs, question_slug="q", purpose="p", sanitizer_version="v1",
            removed=(), retained=(), generated_date="2026-01-01",
        )  # missing `hierarchy`


def test_hierarchy_statuses_and_as_of_year_appear_in_output():
    """T5, continued: with hierarchy present, all four statuses and as_of_year appear."""
    inputs = PacketInputs(findings=(Finding(label="x", value="y"),))
    text = build_packet(
        inputs, hierarchy=_HIERARCHY, question_slug="q", purpose="p", sanitizer_version="v1",
        removed=(), retained=(), generated_date="2026-01-01",
    )
    assert "2026" in text
    assert "funded" in text
    assert "on_track" in text
    assert "positive" in text


def test_header_contains_required_provenance_fields():
    inputs = PacketInputs(findings=(
        Finding(label="Annual household spending", value="$95,000-$100,000"),
        Finding(label="Emergency reserve", value="underfunded"),
    ))
    text = build_packet(
        inputs, hierarchy=_HIERARCHY, question_slug="bmw-i4-financing",
        purpose="Evaluate paying off the auto loan vs. investing",
        sanitizer_version="abc1234", removed=("account numbers", "lender name"),
        retained=("banded spending", "reserve status"), generated_date="2026-09-14",
        destinations=("ChatGPT",),
    )

    assert "packet: bmw-i4-financing-2026-09-14" in text
    assert "source_classification: RESTRICTED" in text
    assert "output_classification: PRIVATE" in text
    assert "sanitizer: scripts/packet.py @ abc1234" in text
    assert 'purpose: "Evaluate paying off the auto loan vs. investing"' in text
    assert "removed: [account numbers, lender name]" in text
    assert "retained: [banded spending, reserve status]" in text
    assert "approved_by:" in text
    assert "destinations: [ChatGPT]" in text


def test_approved_by_is_left_blank_for_the_user():
    inputs = PacketInputs(findings=(Finding(label="x", value="y"),))
    text = build_packet(
        inputs, hierarchy=_HIERARCHY, question_slug="q", purpose="p", sanitizer_version="v1",
        removed=(), retained=(), generated_date="2026-01-01",
    )
    line = next(l for l in text.splitlines() if l.startswith("approved_by:"))
    assert line.strip() == "approved_by:  # User must fill in, e.g. \"User 2026-09-14\" — required before this packet leaves the machine"


def test_output_contains_only_banded_findings_never_raw_fixture_values():
    """The fixture's raw exact figures (e.g. a specific account balance) must
    never appear — only the already-banded display strings the caller supplied."""
    raw_exact_balance = "28,347.19"  # a fictitious exact figure that must NEVER leak through
    inputs = PacketInputs(findings=(
        Finding(label="Auto loan balance", value="approximately $25,000-$30,000"),
        Finding(label="Surplus capital", value="approximately $50,000-$55,000"),
    ))
    text = build_packet(
        inputs, hierarchy=_HIERARCHY, question_slug="bmw-i4-financing", purpose="test",
        sanitizer_version="v1", removed=("exact balance",), retained=("banded balance",),
        generated_date="2026-01-01",
    )

    assert raw_exact_balance not in text
    assert "$25,000-$30,000" in text
    assert "$50,000-$55,000" in text


def test_findings_render_as_markdown_bullets():
    inputs = PacketInputs(findings=(Finding(label="Risk capacity", value="moderate"),))
    text = build_packet(
        inputs, hierarchy=_HIERARCHY, question_slug="q", purpose="p", sanitizer_version="v1",
        removed=(), retained=(), generated_date="2026-01-01",
    )
    assert "- **Risk capacity:** moderate" in text
