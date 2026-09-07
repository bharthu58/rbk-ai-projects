"""buckets: Profile -> BucketAllocation.

Assigns each liquid and investment item to one of the six planning buckets
(State.md §1.5) by **purpose, horizon and liquidity — never by account type**.
Rules are explicit and readable in one function per item kind, per Phase 3B-4
SPEC rule 7 ("the owner must be able to read a module and check the arithmetic
by hand").

**Phase 3B-4a, C2/C4 — fail-closed classification.** Neither an unrecognized
declared purpose nor an unmatched item silently becomes "operating cash" or
"long-term surplus" any more. Both land in `UNCLASSIFIED`, carry a warning,
and `surplus.py` excludes `UNCLASSIFIED` money from available capital — a
guess about what an asset is for must never inflate what looks spendable.
"""

from dataclasses import dataclass

from .profile_load import Investment, LiquidAsset, Profile

CURRENT_LIFESTYLE = "Current lifestyle / operating needs"
SAFETY_RESERVE = "Safety reserve"
NEAR_TERM_OBLIGATIONS = "Near-term known obligations"
EDUCATION_FAMILY = "Education / family obligations"
RETIREMENT_CAPITAL = "Long-term retirement capital"
LONG_TERM_SURPLUS = "Long-term surplus / optional wealth"
UNCLASSIFIED = "Unclassified"

BUCKETS = (
    CURRENT_LIFESTYLE, SAFETY_RESERVE, NEAR_TERM_OBLIGATIONS,
    EDUCATION_FAMILY, RETIREMENT_CAPITAL, LONG_TERM_SURPLUS, UNCLASSIFIED,
)

_INVESTMENT_PURPOSE_TO_BUCKET = {
    "retirement": RETIREMENT_CAPITAL,
    "education": EDUCATION_FAMILY,
    "long_term_surplus": LONG_TERM_SURPLUS,
    "near_term_need": NEAR_TERM_OBLIGATIONS,
}

_LIQUID_PURPOSE_TO_BUCKET = {
    "operating": CURRENT_LIFESTYLE,
    "safety_reserve": SAFETY_RESERVE,
    "near_term_need": NEAR_TERM_OBLIGATIONS,
    "long_term_surplus": LONG_TERM_SURPLUS,
}

# Fallback only when `purpose` is absent. Kept exactly as it was before 3B-4a —
# not expanded into an inference engine. No entry for CURRENT_LIFESTYLE here:
# an unmatched label no longer defaults to operating cash (C2); it falls
# through to UNCLASSIFIED like anything else the label doesn't clearly name.
_LIQUID_LABEL_KEYWORDS = {
    SAFETY_RESERVE: ("emergency", "reserve", "safety"),
    NEAR_TERM_OBLIGATIONS: ("near-term", "near term", "upcoming"),
}


@dataclass(frozen=True)
class BucketAssignment:
    item_label: str
    item_kind: str  # "liquid" | "investment"
    bucket: str
    value: float
    source: str  # "declared" | "keyword_fallback" | "unclassified"
    reason: str  # audit text; doubles as the warning message when source != "declared"


@dataclass(frozen=True)
class BucketTotal:
    bucket: str
    total_value: float
    item_count: int
    has_any_funding: bool


@dataclass(frozen=True)
class BucketAllocation:
    assignments: "list[BucketAssignment]"
    totals: "list[BucketTotal]"
    flags: "list[str]"
    unclassified: "tuple[BucketAssignment, ...]"
    fallback_classified: "tuple[BucketAssignment, ...]"


def classify_liquid(item: LiquidAsset) -> "tuple[str, str, str | None]":
    """Public so other modules (surplus.py) can classify a liquid item the same
    way without re-implementing the rule — one rule, one place. Returns
    (bucket, source, warning) — warning is None only when source=='declared'."""
    if item.purpose is not None:
        bucket = _LIQUID_PURPOSE_TO_BUCKET.get(item.purpose)
        if bucket is not None:
            return bucket, "declared", None
        return UNCLASSIFIED, "unclassified", (
            f"liquid '{item.label}': declared purpose {item.purpose!r} is not recognized — "
            "treated as UNCLASSIFIED, excluded from available capital"
        )

    label_lower = item.label.lower()
    for bucket, keywords in _LIQUID_LABEL_KEYWORDS.items():
        if any(kw in label_lower for kw in keywords):
            return bucket, "keyword_fallback", (
                f"liquid '{item.label}': no declared purpose; inferred '{bucket}' from label text — "
                "declare `purpose` explicitly to remove this inference"
            )

    return UNCLASSIFIED, "unclassified", (
        f"liquid '{item.label}': no declared purpose and no recognized label keyword — "
        "treated as UNCLASSIFIED, excluded from available capital (no silent default to operating cash)"
    )


def _assign_liquid(item: LiquidAsset) -> BucketAssignment:
    bucket, source, warning = classify_liquid(item)
    reason = warning if warning is not None else f"declared purpose='{item.purpose}'"
    return BucketAssignment(item_label=item.label, item_kind="liquid", bucket=bucket,
                             value=item.approx_value, source=source, reason=reason)


def _assign_investment(item: Investment) -> tuple[BucketAssignment, "str | None"]:
    bucket = _INVESTMENT_PURPOSE_TO_BUCKET.get(item.intended_purpose)
    flag = None
    if bucket is None:
        # C4: fail closed, not open. An unrecognized purpose must not be
        # silently treated as money available for optimization.
        bucket = UNCLASSIFIED
        source = "unclassified"
        reason = (
            f"investment '{item.label}' has unrecognized intended_purpose "
            f"{item.intended_purpose!r} — treated as UNCLASSIFIED, excluded from surplus"
        )
        flag = reason
    else:
        source = "declared"
        reason = f"intended_purpose='{item.intended_purpose}'"
        if bucket == NEAR_TERM_OBLIGATIONS and item.liquidity in ("locked", "penalty_before_age"):
            flag = (
                f"investment '{item.label}' is purposed near_term_need but has liquidity "
                f"'{item.liquidity}' — review whether it can actually be accessed on that horizon"
            )
    assignment = BucketAssignment(item_label=item.label, item_kind="investment", bucket=bucket,
                                   value=item.approx_value, source=source, reason=reason)
    return assignment, flag


def compute_buckets(profile: Profile) -> BucketAllocation:
    assignments: list[BucketAssignment] = []
    flags: list[str] = []

    for item in profile.liquid:
        assignments.append(_assign_liquid(item))

    for item in profile.investments:
        assignment, flag = _assign_investment(item)
        assignments.append(assignment)
        if flag:
            flags.append(flag)

    totals = []
    for bucket in BUCKETS:
        bucket_items = [a for a in assignments if a.bucket == bucket]
        total_value = sum(a.value for a in bucket_items)
        totals.append(BucketTotal(
            bucket=bucket, total_value=total_value,
            item_count=len(bucket_items), has_any_funding=total_value > 0,
        ))

    unclassified = tuple(a for a in assignments if a.bucket == UNCLASSIFIED)
    fallback_classified = tuple(a for a in assignments if a.source == "keyword_fallback")

    return BucketAllocation(assignments=assignments, totals=totals, flags=flags,
                             unclassified=unclassified, fallback_classified=fallback_classified)
