"""resilience: Profile, LifestyleResult -> ResilienceResult.

Required reserve = target_months x (essential / 12). **Essential, not total** —
sizing against total (which includes lifestyle/discretionary) overstates what
an emergency actually needs (State.md §9).

If essential spending is Unknown, the required reserve is Unknown and the
result says so explicitly rather than reporting "$0 required" (Phase 3B-4 SPEC
rule 2 — this is exactly the propagation rule that exists to prevent).
"""

from dataclasses import dataclass

from .bands import UNKNOWN, Range, Unknown, round_spending
from .lifestyle import LifestyleResult
from .profile_load import Profile

# Liquid assets fast enough to actually meet an emergency. "weeks" access is
# too slow to count toward the reserve, even though it's still liquid in the
# ordinary sense.
_ELIGIBLE_ACCESS = ("immediate", "days")


@dataclass(frozen=True)
class ResilienceResult:
    required: "Range | Unknown"
    held: float
    funded: "bool | Unknown"
    months_covered: "float | Unknown"
    explanation: str


def _band_as_range(point: float) -> Range:
    """A point figure rendered as its own rounding band, per §1.9 — displaying
    a bare point estimate would be false precision the profile's inputs never had."""
    banded = round_spending(point)
    return Range(low=banded - 500, high=banded + 500)


def compute_resilience(profile: Profile, lifestyle: LifestyleResult) -> ResilienceResult:
    held = sum(item.approx_value for item in profile.liquid if item.access in _ELIGIBLE_ACCESS)

    if lifestyle.essential is UNKNOWN:
        return ResilienceResult(
            required=UNKNOWN,
            held=held,
            funded=UNKNOWN,
            months_covered=UNKNOWN,
            explanation=(
                "Essential spending is unknown, so the required reserve is unanswerable — "
                "this is not '$0 required', it is 'cannot be computed until essential spending is known'."
            ),
        )

    monthly_essential = lifestyle.essential / 12
    required_point = profile.safety_reserve.target_months_of_essential * monthly_essential
    required = _band_as_range(required_point)

    funded = held >= required.midpoint()
    months_covered = held / monthly_essential if monthly_essential > 0 else UNKNOWN

    explanation = (
        f"Required = {profile.safety_reserve.target_months_of_essential} months x "
        f"(essential {lifestyle.essential} / 12). Held = sum of liquid assets with "
        f"access in {_ELIGIBLE_ACCESS}."
    )

    return ResilienceResult(
        required=required, held=held, funded=funded,
        months_covered=months_covered, explanation=explanation,
    )
