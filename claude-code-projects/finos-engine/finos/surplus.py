"""surplus: ResilienceResult, ObligationsResult, RetirementResult, Profile ->
SurplusResult.

**The decision-hierarchy gate.** `compute_surplus` takes `resilience`,
`obligations` **and `retirement`** as *required* positional arguments — there
is no code path that can evaluate surplus without them, so a tactical
optimization can never structurally outrun safety, known obligations, or
retirement sufficiency (Phase 3B-4 SPEC rule 6; Phase 3B-4a C1 added
retirement to the enforced hierarchy after the original SPEC's ordering
contradicted `financial-os/State/State.md` §1.4 and left `RetirementResult`
consumed by nothing).

Corrected engine order (3B-4a): `... -> Obligations -> Retirement -> Surplus
-> Packet`.

Surplus = available capital − reserve requirement − near-term obligation gaps
− operating cash. A result of zero or negative is returned cleanly, naming
*which* higher-level requirement consumed the capital — "not surplus, because
the reserve is short" is a complete and correct answer, not a failure.

**`unrestricted` is a separate axis from `status`/`amount`.** A retirement
shortfall does not change the arithmetic — it changes whether the resulting
capital is classified as unrestricted surplus available for optimization.
See `restriction_reason`'s exact required wording below: shortfall is a
reason to act (very possibly by directing this capital into retirement), not
a reason to do nothing.

**Implementation note on "available capital"/"operating cash" (flagged for
review in 3B-4, ACCEPTED with a fix in 3B-4a per C2):** the *shape* of the
formula is unchanged from 3B-4 — available capital starts as the gross liquid
pool plus `LONG_TERM_SURPLUS`-purposed investments, and reserve/near-term-
obligation/operating-cash requirements are peeled off as explicit deductions,
not by pre-excluding those buckets from the gross sum. **What 3B-4a changes is
narrow: `UNCLASSIFIED` liquid (declared-but-unrecognized purpose, or no
purpose and no label match) is excluded from that gross sum entirely** — it
can never inflate surplus, and it is not swept into operating cash either.
Classification now comes from `buckets.compute_buckets`, not re-derived here,
so the bucket report and the surplus figure can no longer disagree about the
same asset. Every non-`declared` classification carries a warning, and every
warning propagates into `SurplusResult.classification_warnings` — **including
when compute_surplus refuses** (Phase 3B-5, scenario D): classification is
independent of resilience/retirement being known, so it is computed once,
unconditionally, before either refusal check, not only on the success path.

**Phase 3B-4b, C10a — refusal priority is correct as implemented, not a bug.**
When both resilience and retirement are `Unknown`, resilience refuses first
(`blocked_by="resilience"`), matching §1.4's SAFETY-before-RETIREMENT
ordering. Consequence, accepted deliberately: the User fixes resilience,
re-runs, and only *then* discovers retirement is also unknown — sequential
discovery across two round trips, not simultaneous. Reporting both at once
would need a second field; that is machinery this SPEC declines to add for a
sequencing inconvenience, not a correctness gap.

**Phase 3B-4b, C10b — `unrestricted=False` has two distinct, non-exclusive
causes.** It is `False` either because **no surplus exists** (`amount <= 0`)
or because **a retirement shortfall restricts it** (`retirement_status ==
"shortfall"`) — and both can be true at once. `restriction_reason`
disambiguates: `None` when there is no retirement shortfall (even if
`amount <= 0` — in that case `blocked_by` is the explanation), set when there
is one (independent of `amount`). Do not "fix" a case where `amount <= 0`,
`unrestricted=False`, **and** `restriction_reason is None` — that combination
is correct: `blocked_by` is carrying the explanation instead.
"""

from dataclasses import dataclass

from .bands import UNKNOWN, Unknown
from .buckets import CURRENT_LIFESTYLE, LONG_TERM_SURPLUS, UNCLASSIFIED, compute_buckets
from .obligations import ObligationsResult
from .profile_load import Profile
from .resilience import ResilienceResult
from .retirement import RetirementResult

_RESTRICTION_REASON_SHORTFALL = (
    "Retirement sufficiency shows a shortfall in the Base scenario. This capital's first claim "
    "is retirement remediation — which may itself be an investment decision. Not unrestricted "
    "surplus; not immobilised."
)


@dataclass(frozen=True)
class SurplusResult:
    status: str  # "positive" | "zero" | "negative" | "unknown"
    amount: "float | Unknown"
    available_capital: "float | Unknown"
    reserve_deduction: "float | Unknown"
    near_term_obligation_deduction: float
    operating_cash_deduction: "float | Unknown"
    blocked_by: "str | None"  # "this is not surplus at all" — amount <= 0, or refusal
    retirement_status: str  # "on_track" | "shortfall" | "unknown"
    unrestricted: bool
    restriction_reason: "str | None"  # set on retirement shortfall — never confuse with blocked_by
    classification_warnings: "tuple[str, ...]"
    explanation: str


@dataclass(frozen=True)
class HierarchyStatus:
    """Strings + a bool + one int — no monetary values, cannot leak. Attests
    that the full hierarchy actually ran, for packet.py to require.

    Phase 3B-4b, C9: `unrestricted` was added because `surplus` alone
    (positive|zero|negative|unknown) let a retirement-shortfall household
    attest `surplus: positive` with no trace of the restriction in the
    packet — the entire point of C1 never reached the one artifact a cloud
    model actually reads. `unrestricted` carries that distinction explicitly
    rather than requiring a reader to cross-reference `retirement`."""

    safety: str  # "funded" | "underfunded" | "unknown"
    obligations: str  # "funded" | "near_term_gap" | "long_term_gap_only" | "unknown"
    retirement: str  # "on_track" | "shortfall" | "unknown"
    surplus: str  # "positive" | "zero" | "negative" | "unknown"
    unrestricted: bool
    as_of_year: int


def _retirement_status(retirement: RetirementResult) -> str:
    sustainable = retirement.base.sustainable
    if sustainable is UNKNOWN:
        return "unknown"
    return "on_track" if sustainable else "shortfall"


def compute_surplus(
    resilience: ResilienceResult,
    obligations: ObligationsResult,
    retirement: RetirementResult,
    profile: Profile,
) -> SurplusResult:
    retirement_status = _retirement_status(retirement)

    # Classification is independent of resilience/retirement being known —
    # computed once, unconditionally, so it is visible even on a refusal
    # (Phase 3B-5 scenario D: a household can have both an unknown essential
    # spend AND unclassified assets, and a human fixing the first should not
    # have to re-run just to discover the second).
    allocation = compute_buckets(profile)
    classification_warnings = tuple(
        a.reason for a in allocation.assignments if a.source != "declared"
    )

    if resilience.required is UNKNOWN:
        return SurplusResult(
            status="unknown", amount=UNKNOWN, available_capital=UNKNOWN,
            reserve_deduction=UNKNOWN, near_term_obligation_deduction=obligations.near_term_gap,
            operating_cash_deduction=UNKNOWN, blocked_by="resilience",
            retirement_status=retirement_status, unrestricted=False, restriction_reason=None,
            classification_warnings=classification_warnings,
            explanation=(
                "Resilience (safety reserve) requirement is unknown because essential spending "
                "is unknown. Surplus cannot be evaluated before safety is established — refusing "
                "to compute rather than guessing."
            ),
        )

    if retirement_status == "unknown":
        return SurplusResult(
            status="unknown", amount=UNKNOWN, available_capital=UNKNOWN,
            reserve_deduction=resilience.required.high, near_term_obligation_deduction=obligations.near_term_gap,
            operating_cash_deduction=UNKNOWN, blocked_by="retirement",
            retirement_status="unknown", unrestricted=False, restriction_reason=None,
            classification_warnings=classification_warnings,
            explanation=(
                "Retirement sustainability is unknown (insufficient age/capital/spending data). "
                "Surplus cannot be evaluated before retirement sufficiency is established — "
                "refusing to compute rather than guessing."
            ),
        )

    operating_cash = sum(
        a.value for a in allocation.assignments
        if a.item_kind == "liquid" and a.bucket == CURRENT_LIFESTYLE
    )
    # Gross pool (all liquid except UNCLASSIFIED, plus long_term_surplus
    # investments) minus reserve/near-term/operating-cash deductions below —
    # same shape as 3B-4; UNCLASSIFIED exclusion is the only change (C2).
    available_capital = sum(
        a.value for a in allocation.assignments
        if (a.item_kind == "liquid" and a.bucket != UNCLASSIFIED)
        or (a.item_kind == "investment" and a.bucket == LONG_TERM_SURPLUS)
    )

    reserve_deduction = resilience.required.high  # conservative: the upper end of the required range
    near_term_deduction = obligations.near_term_gap

    amount = available_capital - reserve_deduction - near_term_deduction - operating_cash

    if amount > 0:
        status = "positive"
    elif amount == 0:
        status = "zero"
    else:
        status = "negative"

    blocked_by = None
    if amount <= 0:
        # Priority order mirrors the decision hierarchy itself: SAFETY, then
        # OBLIGATIONS, then everyday operating needs.
        if not resilience.funded:
            blocked_by = "safety reserve is not yet fully funded"
        elif near_term_deduction > 0:
            blocked_by = "near-term known obligations are not yet fully funded"
        else:
            blocked_by = "available capital net of reserve and near-term obligations does not exceed operating cash needs"

    restriction_reason = _RESTRICTION_REASON_SHORTFALL if retirement_status == "shortfall" else None
    unrestricted = (amount > 0) and (retirement_status == "on_track")

    explanation = (
        f"available_capital({available_capital}) - reserve({reserve_deduction}) - "
        f"near_term_obligation_gap({near_term_deduction}) - operating_cash({operating_cash}) = {amount}. "
        f"retirement_status={retirement_status}."
    )

    return SurplusResult(
        status=status, amount=amount, available_capital=available_capital,
        reserve_deduction=reserve_deduction, near_term_obligation_deduction=near_term_deduction,
        operating_cash_deduction=operating_cash, blocked_by=blocked_by,
        retirement_status=retirement_status, unrestricted=unrestricted,
        restriction_reason=restriction_reason, classification_warnings=classification_warnings,
        explanation=explanation,
    )


def _obligations_status(obligations: ObligationsResult) -> str:
    """Phase 3B-4b, C8. The near-term/long-term split at 5 years is a
    *deduction rule* for surplus arithmetic (accepted in 3B-4, unchanged here)
    — it must not also silently serve as the *attestation* rule. A household
    with a large gap 8 years out is not `funded`, even though nothing is
    deducted from surplus for it today; State.md §1.7 is explicit that a
    known obligation is 'money that must be there' regardless of horizon."""
    near = obligations.near_term_gap
    long = obligations.long_term_gap
    if near is UNKNOWN or long is UNKNOWN:
        return "unknown"
    if near > 0:
        return "near_term_gap"  # takes precedence — the more urgent fact
    if long > 0:
        return "long_term_gap_only"
    return "funded"


def attest_hierarchy(
    resilience: ResilienceResult,
    obligations: ObligationsResult,
    retirement: RetirementResult,
    surplus: SurplusResult,
) -> HierarchyStatus:
    """Called after `compute_surplus` — attests the full hierarchy actually
    ran. `packet.build_packet` requires this; there is no way to produce a
    decision packet while skipping a level."""
    if resilience.funded is UNKNOWN:
        safety = "unknown"
    else:
        safety = "funded" if resilience.funded else "underfunded"

    return HierarchyStatus(
        safety=safety,
        obligations=_obligations_status(obligations),
        retirement=_retirement_status(retirement),
        surplus=surplus.status,
        unrestricted=surplus.unrestricted,
        as_of_year=obligations.as_of_year,
    )
