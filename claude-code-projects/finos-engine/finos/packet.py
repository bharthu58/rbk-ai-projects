"""packet: PacketInputs, question, purpose -> Markdown.

**The signature is the control.** `build_packet()` does not accept `Profile`,
does not accept any monetary result type from the other seven modules, and
does not accept a file path to read from — only a `PacketInputs` of already-
derived, already-banded strings. You cannot leak what the function was never
given.

Emits the provenance header from `Reports/sanitized/README.md`:
`source_classification: RESTRICTED` (permanent — the source never changes),
`output_classification: PRIVATE` (this artifact only), sanitizer name + a
caller-supplied version/commit, purpose, removed/retained, and `approved_by`
left blank for the User to fill in by hand.

**Phase 3B-4a, C1 — `hierarchy: HierarchyStatus` is now required.** Unlike
every other result type, `HierarchyStatus` *is* accepted here deliberately —
it carries only four status strings and a year, no monetary values, so it
cannot leak anything, and its presence is exactly what proves the full
decision hierarchy actually ran before this packet could be built. There is
no way to call `build_packet` without it.
"""

from dataclasses import dataclass

from .surplus import HierarchyStatus

_SANITIZER_MODULE = "scripts/packet.py"


@dataclass(frozen=True)
class Finding:
    """One already-sanitized line. `value` must already be a display string —
    a banded range, a funded/not-funded word, a status — never a raw number
    pulled straight from a Profile field."""

    label: str
    value: str


@dataclass(frozen=True)
class PacketInputs:
    """Everything build_packet is allowed to see. Notably absent: Profile,
    any *Result type, or a path — none of those can appear here by construction."""

    findings: "tuple[Finding, ...]"


def build_packet(
    inputs: PacketInputs,
    *,
    hierarchy: HierarchyStatus,
    question_slug: str,
    purpose: str,
    sanitizer_version: str,
    removed: "tuple[str, ...]",
    retained: "tuple[str, ...]",
    generated_date: str,
    destinations: "tuple[str, ...]" = (),
) -> str:
    """`generated_date` is a caller-supplied 'YYYY-MM-DD' string (not read from
    the wall clock here) so packet generation stays deterministic and testable."""
    packet_id = f"{question_slug}-{generated_date}"
    sanitizer = f"{_SANITIZER_MODULE} @ {sanitizer_version}"

    header_lines = [
        "---",
        f"packet: {packet_id}",
        "source_classification: RESTRICTED",
        "output_classification: PRIVATE",
        f"sanitizer: {sanitizer}",
        f'purpose: "{purpose}"',
        f"removed: [{', '.join(removed)}]",
        f"retained: [{', '.join(retained)}]",
        "approved_by:  # User must fill in, e.g. \"User 2026-09-14\" — required before this packet leaves the machine",
        f"destinations: [{', '.join(destinations)}]",
        "---",
        "",
    ]

    body_lines = [f"# {question_slug.replace('-', ' ').title()}", ""]
    body_lines.append(f"## Decision Hierarchy (as of {hierarchy.as_of_year})")
    body_lines.append(f"- **Safety:** {hierarchy.safety}")
    body_lines.append(f"- **Obligations:** {hierarchy.obligations}")
    body_lines.append(f"- **Retirement:** {hierarchy.retirement}")
    body_lines.append(f"- **Surplus:** {hierarchy.surplus}")
    body_lines.append(f"- **Unrestricted:** {hierarchy.unrestricted}")
    body_lines.append("")
    for finding in inputs.findings:
        body_lines.append(f"- **{finding.label}:** {finding.value}")
    body_lines.append("")

    return "\n".join(header_lines + body_lines)
