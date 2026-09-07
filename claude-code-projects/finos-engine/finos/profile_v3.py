"""profile_v3: raw dict -> ProfileV3.

Loads and fail-closed validates a schema_version: 3 Household Financial
Profile (`schemas/profile.v3.schema.yaml`, rev 4.1). Called from
`profile_load.load_profile` when it sees `schema_version: 3` — never called
directly by anything holding only a bare path, because full validation needs
a loaded `Registry` (parameter-role and statutory-fact references).

**Scope note (F2, not F5):** this module is a loader and validator only. It
produces `ProfileV3`, a type distinct from `profile_load.Profile`, and is
never fed to `lifestyle.py / buckets.py / resilience.py / obligations.py /
retirement.py / surplus.py` — those six modules keep consuming exactly the
`Profile` shape they consume today, for both schema versions, because v3
profiles no longer carry the scenario assumptions those modules need (that
moved to the Assumption Registry + Scenario Library). See the F2 completion
report for the full rationale.

No projection, no smoothing algorithm, no timeline engine — parse and
validate shape only, per §6b's explicit scope boundary.
"""

import re
from dataclasses import dataclass, field

from .bands import UNKNOWN, Unknown
from .field_meta import FieldMeta, unwrap_field
from .registry_load import Registry

_VALID_ROLE = {"adult", "child"}
_VALID_RETIREMENT_STATUS = {"PLANNED", "CONFIRMED"}
_VALID_ELECTION_STATUS = {"ACTUAL", "PLANNED", "PROVISIONAL"}
_VALID_STABILITY = {"stable", "variable", "at_risk"}
_VALID_INCOME_KIND = {"employment", "rental", "business", "pension", "annuity", "social_security", "other"}
_VALID_TOTALS_AUTHORITY = {"derived", "declared"}
_VALID_CLASSIFICATION = {"essential", "lifestyle", "discretionary"}
_VALID_CASH_FLOW_PATTERN = {"recurring", "irregular_predictable"}
_VALID_ACCESS = {"immediate", "days", "weeks"}
_VALID_LIQUID_PURPOSE = {"operating", "safety_reserve", "near_term_need", "long_term_surplus"}
_VALID_LIQUID_POOL = {"safety_reserve", "general_taxable", "operating"}
_VALID_CONTAINER = {"taxable_brokerage", "traditional_401k", "roth_401k", "after_tax_401k",
                     "traditional_ira", "roth_ira", "rollover_ira", "hsa", "education_529", "cash", "other"}
_VALID_TAX_CHARACTER = {"taxable", "tax_deferred", "tax_free", "mixed"}
_VALID_INVESTMENT_POOL = {"general_retirement", "general_taxable", "education", "safety_reserve", "hsa", "other"}
_VALID_LIQUIDITY = {"immediate", "days", "penalty_before_age", "locked"}
_VALID_DEBT_TYPE = {"mortgage", "auto", "student", "other"}
_VALID_FIXED_VARIABLE = {"fixed", "variable"}
_VALID_CONTRIBUTOR = {"employee", "employer", "household"}
_VALID_DESTINATION = {"pre_tax", "roth", "after_tax_non_roth", "hsa", "education_529", "other"}
_VALID_MECHANISM = {"regular_deferral", "catch_up", "match", "nonelective", "profit_sharing",
                     "ordinary_after_tax", "education_contribution", "other"}
_VALID_LIMIT_GROUP = {"elective_deferral", "section_415c", "catch_up", "hsa", "none"}
_VALID_CONTRIBUTION_STATUS = {"VERIFIED_PLAN_RULE", "ESTIMATE", "PLANNED", "REALIZED"}
_VALID_CONTRIBUTION_CLASS = {"core", "discretionary"}
_VALID_FUNDING_ORDER = {"smoothed_non_529", "proportional", "dedicated_529_first", "taxable_first", "manual_schedule"}
_VALID_SHORTFALL_SOURCE = {"taxable", "future_income", "loans", "education_funding_capacity", "other"}
_VALID_FLEXIBILITY = {"fixed", "somewhat_flexible", "flexible"}
_VALID_AID_KIND = {"need_based_aid", "merit_scholarship", "employer_benefit", "family_contribution", "other"}
_VALID_AID_STATUS = {"PLANNED", "PROVISIONAL", "CONFIRMED"}
_VALID_TAX_SCOPE = {"federal_income", "state_income", "combined_income", "payroll_fica", "total_all_taxes"}

_LIFECYCLE_EVENT_RE = re.compile(
    r"^(retirement|medicare|debt_payoff|education_start|education_end|child_independent|year):(.+)$"
)


class ProfileV3Error(Exception):
    """Base for every typed error this module raises."""


class ProfileV3ValidationError(ProfileV3Error):
    """A required field is missing or has an invalid value."""


class ProfileV3ReferenceError(ProfileV3Error):
    """A typed reference (lifecycle event, member/account/debt/education id,
    parameter role, statutory fact) does not resolve. Fail closed — never
    silently treated as `never` or skipped."""


@dataclass(frozen=True)
class HealthcareAvailability:
    employer_coverage_while_working: bool = False
    dependent_coverage_available_to: "tuple[str, ...]" = ()
    retiree_coverage_available: bool = False


@dataclass(frozen=True)
class HealthcareElection:
    starts_at: str
    ends_at: str
    elected: str
    status: str


@dataclass(frozen=True)
class HouseholdMemberV3:
    id: str
    role: str
    birth_year: int
    retirement_target_date: "str | None" = None
    retirement_target_age: "int | Unknown" = UNKNOWN
    retirement_status: "str | None" = None
    medicare_eligible_age: int = 65
    independent_year: "int | None" = None
    healthcare_availability: HealthcareAvailability = field(default_factory=HealthcareAvailability)
    healthcare_elections: "tuple[HealthcareElection, ...]" = ()


@dataclass(frozen=True)
class IncomeSourceV3:
    id: str
    owner: str
    kind: str
    label: str
    gross_annual: "float | Unknown"
    stability: str
    growth_parameter_role: "str | None"
    starts_at: str
    ends_at: "str | None" = None


@dataclass(frozen=True)
class SpendingCategoryV3:
    id: str
    label: "str | None"
    annual_amount: "float | Unknown"
    classification: str
    cash_flow_pattern: str
    recurrence: "str | None"
    derived_from: "str | None"
    member_ref: "str | None"
    starts_at: "str | None"
    ends_at: "str | None"
    multiplier_by_state: "dict"
    constant: bool
    inflation_parameter_role: "str | None"
    notes: "str | None" = None


@dataclass(frozen=True)
class SpendingV3:
    totals_authority: str
    totals_tolerance_pct: float
    annual_total: "float | Unknown"
    essential: "float | Unknown"
    lifestyle: "float | Unknown"
    discretionary: "float | Unknown"
    categories: "tuple[SpendingCategoryV3, ...]" = ()


@dataclass(frozen=True)
class LiquidAssetV3:
    id: str
    label: str
    approx_value: "float | Unknown"
    access: str
    purpose: "str | None"
    pool: "str | None"


@dataclass(frozen=True)
class InvestmentAllocationV3:
    equity_pct: "float | Unknown" = UNKNOWN
    fixed_income_pct: "float | Unknown" = UNKNOWN
    cash_pct: "float | Unknown" = UNKNOWN
    other_pct: "float | Unknown" = UNKNOWN


@dataclass(frozen=True)
class InvestmentV3:
    id: str
    label: str
    owner: str
    approx_value: "float | Unknown"
    container: str
    tax_character: str
    basis_value: "float | Unknown"
    earnings_value: "float | Unknown"
    pool: str
    liquidity: str
    intended_purpose: str
    beneficiary: "str | None"
    return_parameter_role: "str | None"
    in_college_return_parameter_role: "str | None"
    allocation: InvestmentAllocationV3


@dataclass(frozen=True)
class DebtV3:
    id: str
    label: str
    balance: "float | Unknown"
    apr_pct: float
    term_months: int
    months_remaining: int
    monthly_payment: "float | Unknown"
    payoff_date: "str | None"
    type: str
    fixed_or_variable: str
    prepayment_penalty: str = "none"


@dataclass(frozen=True)
class MatchTier:
    employee_contributes_up_to_pct: float
    employer_matches_pct: float


@dataclass(frozen=True)
class ContributionFormula:
    kind: "str | None" = None
    pct: "float | None" = None
    income_source_ref: "str | None" = None
    match_rules: "tuple[MatchTier, ...]" = ()
    match_schedule_text: "str | None" = None


@dataclass(frozen=True)
class LimitPolicy:
    statutory_fact_ref: "str | None" = None
    limit_growth_parameter_role: "str | None" = None
    contribute_to_limit: "bool | None" = None


@dataclass(frozen=True)
class ContributionV3:
    id: str
    owner: str
    account_ref: str
    contributor: str
    destination: str
    mechanism: str
    plan_ref: "str | None"
    limit_group_ref: "str | None"
    amount: "float | Unknown"
    formula: "ContributionFormula | None"
    starts_at: "str | None"
    ends_at: "str | None"
    classification: str
    limit_policy: LimitPolicy
    status: str
    notes: "str | None" = None


@dataclass(frozen=True)
class AidOffset:
    kind: str
    annual_amount: "float | Unknown"
    status: str
    applies_years: object
    notes: "str | None" = None


@dataclass(frozen=True)
class FundingPolicy:
    order: str
    manual_schedule: tuple = ()
    shortfall_sources: "tuple[str, ...]" = ()


@dataclass(frozen=True)
class EducationV3:
    id: str
    beneficiary: str
    start_year: int
    end_year: int
    annual_cost: "float | Unknown"
    cost_inflation_parameter_role: "str | None"
    aid_offsets: "tuple[AidOffset, ...]"
    funding_accounts: "tuple[str, ...]"
    funding_policy: FundingPolicy
    flexibility: "str | None" = None
    notes: "str | None" = None


@dataclass(frozen=True)
class EducationFundingCapacityV3:
    id: str
    starts_at: str
    ends_at: str
    annual_amount: "float | Unknown"
    source: "str | None"
    redirected_from_contribution_ref: "str | None"
    allocable_to: object
    status: "str | None" = None


@dataclass(frozen=True)
class ObligationV3:
    id: str
    label: str
    target_year: int
    estimated_total_cost: "float | Unknown"
    funding_accounts: "tuple[str, ...]"
    flexibility: str


@dataclass(frozen=True)
class GoalsV3:
    desired_annual_spending: "float | Unknown"
    other: tuple = ()


@dataclass(frozen=True)
class SafetyReservePolicyV3:
    target_months_of_essential: float
    rationale: "str | None" = None
    decision_ref: "str | None" = None


@dataclass(frozen=True)
class ObservedLiability:
    tax_year: int
    scope: str
    jurisdiction: str
    includes_payroll: bool
    amount: "float | Unknown"
    basis_income: "float | Unknown"
    status: str = "ACTUAL"
    source: "str | None" = None
    notes: "str | None" = None


@dataclass(frozen=True)
class TaxV3:
    observed_liability: "tuple[ObservedLiability, ...]"
    marginal_rate_parameter_role: "str | None" = None
    capital_gains_parameter_role: "str | None" = None
    social_security_rate_role: "str | None" = None
    social_security_wage_base_growth_role: "str | None" = None
    medicare_rate_role: "str | None" = None
    additional_medicare_rate_role: "str | None" = None


@dataclass(frozen=True)
class ProfileV3:
    schema_version: int
    synthetic: bool
    profile_version: "int | None"
    profile_as_of: "str | None"
    household: "tuple[HouseholdMemberV3, ...]"
    income_sources: "tuple[IncomeSourceV3, ...]"
    income_net_annual_estimate: "float | Unknown"
    spending: SpendingV3
    liquid: "tuple[LiquidAssetV3, ...]"
    investments: "tuple[InvestmentV3, ...]"
    debt: "tuple[DebtV3, ...]"
    contributions: "tuple[ContributionV3, ...]"
    education: "tuple[EducationV3, ...]"
    education_funding_capacity: "tuple[EducationFundingCapacityV3, ...]"
    obligations: "tuple[ObligationV3, ...]"
    goals: GoalsV3
    safety_reserve: SafetyReservePolicyV3
    tax: TaxV3
    field_meta: "dict[str, FieldMeta]" = field(default_factory=dict)


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------


def _require(mapping: dict, key: str, *, where: str):
    if not isinstance(mapping, dict) or key not in mapping or mapping[key] in (None, ""):
        raise ProfileV3ValidationError(f"{where}: missing required field '{key}'")
    return mapping[key]


def _one_of(value, allowed: set, *, where: str, field_name: str):
    if value not in allowed:
        raise ProfileV3ValidationError(
            f"{where}: field '{field_name}' has invalid value {value!r} — expected one of {sorted(allowed)}"
        )
    return value


def _field(mapping: dict, key: str, *, where: str, field_meta: dict, path: str,
           expected_dollar_class: "str | None" = None, required: bool = False):
    """unwrap_field + Unknown-normalization + field_meta bookkeeping, in one call."""
    raw = mapping.get(key) if isinstance(mapping, dict) else None
    if raw in (None, "", "UNKNOWN", "unknown"):
        if required:
            raise ProfileV3ValidationError(f"{where}: missing required field '{key}'")
        return UNKNOWN
    value, meta = unwrap_field(
        raw, where=f"{where}.{key}",
        dollar_class_required=expected_dollar_class is not None,
        expected_dollar_class=expected_dollar_class,
    )
    if meta is not None:
        field_meta[path] = meta
    return value


def _resolve_lifecycle_event(value, *, where: str, member_ids: set, debt_ids: set, education_ids: set):
    if value in (None, ""):
        return None
    if value in ("never", "now"):
        return value
    if re.match(r"^year:\d{4}$", value):
        return value
    m = _LIFECYCLE_EVENT_RE.match(value)
    if not m:
        raise ProfileV3ReferenceError(f"{where}: {value!r} is not a recognized typed lifecycle event")
    kind, ref_id = m.group(1), m.group(2)
    if kind in ("retirement", "medicare", "child_independent"):
        if ref_id not in member_ids:
            raise ProfileV3ReferenceError(f"{where}: {value!r} references unknown member id {ref_id!r}")
    elif kind == "debt_payoff":
        if ref_id not in debt_ids:
            raise ProfileV3ReferenceError(f"{where}: {value!r} references unknown debt id {ref_id!r}")
    elif kind in ("education_start", "education_end"):
        if ref_id not in education_ids:
            raise ProfileV3ReferenceError(f"{where}: {value!r} references unknown education id {ref_id!r}")
    return value


def _resolve_parameter_role(role, *, where: str, registry: Registry, required: bool = False):
    if role in (None, ""):
        if required:
            raise ProfileV3ValidationError(f"{where}: missing required parameter role")
        return None
    if role not in registry.parameters:
        raise ProfileV3ReferenceError(f"{where}: parameter role {role!r} does not resolve against the registry")
    return role


def _resolve_statutory_fact(ref, *, where: str, registry: Registry):
    if ref in (None, ""):
        return None
    if ref not in registry.statutory_facts:
        raise ProfileV3ReferenceError(f"{where}: statutory_fact_ref {ref!r} does not resolve against the registry")
    return ref


# --------------------------------------------------------------------------
# Section parsers
# --------------------------------------------------------------------------


def _parse_household(raw: dict, *, field_meta: dict, registry: Registry) -> "tuple[HouseholdMemberV3, ...]":
    members_raw = _require(raw, "members", where="household")
    if not isinstance(members_raw, list) or not members_raw:
        raise ProfileV3ValidationError("household.members: must be a non-empty list")

    out = []
    seen_ids = set()
    for i, m in enumerate(members_raw):
        where = f"household.members[{i}]"
        mid = _require(m, "id", where=where)
        if mid in seen_ids:
            raise ProfileV3ValidationError(f"{where}: duplicate member id {mid!r}")
        seen_ids.add(mid)
        role = _one_of(_require(m, "role", where=where), _VALID_ROLE, where=where, field_name="role")
        birth_year = _require(m, "birth_year", where=where)

        retirement = m.get("retirement") or {}
        retirement_status = retirement.get("status")
        if retirement_status is not None:
            _one_of(retirement_status, _VALID_RETIREMENT_STATUS, where=f"{where}.retirement", field_name="status")

        hc = m.get("healthcare") or {}
        avail_raw = hc.get("availability") or {}
        availability = HealthcareAvailability(
            employer_coverage_while_working=bool(avail_raw.get("employer_coverage_while_working", False)),
            dependent_coverage_available_to=tuple(avail_raw.get("dependent_coverage_available_to") or ()),
            retiree_coverage_available=bool(avail_raw.get("retiree_coverage_available", False)),
        )
        elections = []
        for j, e in enumerate(hc.get("elections") or []):
            ewhere = f"{where}.healthcare.elections[{j}]"
            status = _one_of(_require(e, "status", where=ewhere), _VALID_ELECTION_STATUS,
                              where=ewhere, field_name="status")
            elections.append(HealthcareElection(
                starts_at=_require(e, "starts_at", where=ewhere),
                ends_at=_require(e, "ends_at", where=ewhere),
                elected=_require(e, "elected", where=ewhere),
                status=status,
            ))

        out.append(HouseholdMemberV3(
            id=mid, role=role, birth_year=birth_year,
            retirement_target_date=retirement.get("target_date"),
            retirement_target_age=retirement.get("target_age", UNKNOWN),
            retirement_status=retirement_status,
            medicare_eligible_age=m.get("medicare_eligible_age", 65),
            independent_year=m.get("independent_year"),
            healthcare_availability=availability,
            healthcare_elections=tuple(elections),
        ))

    # Criterion 8: dependent_coverage_available_to[] and dependent_of:<id> must resolve.
    for i, member in enumerate(out):
        where = f"household.members[{i}].healthcare.availability.dependent_coverage_available_to"
        for dep_id in member.healthcare_availability.dependent_coverage_available_to:
            if dep_id not in seen_ids:
                raise ProfileV3ReferenceError(f"{where}: {dep_id!r} does not resolve against household.members[].id")
        for j, election in enumerate(member.healthcare_elections):
            ewhere = f"household.members[{i}].healthcare.elections[{j}].elected"
            if election.elected.startswith("dependent_of:"):
                dep_id = election.elected.split(":", 1)[1]
                if dep_id not in seen_ids:
                    raise ProfileV3ReferenceError(f"{ewhere}: {dep_id!r} does not resolve against household.members[].id")

    return tuple(out)


def _parse_income(raw: dict, *, field_meta: dict, registry: Registry) -> "tuple[tuple[IncomeSourceV3, ...], object]":
    sources_raw = _require(raw, "sources", where="income")
    if not isinstance(sources_raw, list) or not sources_raw:
        raise ProfileV3ValidationError("income.sources: must be a non-empty list")

    out = []
    seen_ids = set()
    for i, s in enumerate(sources_raw):
        where = f"income.sources[{i}]"
        sid = _require(s, "id", where=where)
        if sid in seen_ids:
            raise ProfileV3ValidationError(f"{where}: duplicate income source id {sid!r}")
        seen_ids.add(sid)
        kind = _one_of(s.get("kind", "employment"), _VALID_INCOME_KIND, where=where, field_name="kind")
        stability = _one_of(_require(s, "stability", where=where), _VALID_STABILITY,
                             where=where, field_name="stability")
        growth_role = _resolve_parameter_role(s.get("growth_parameter_role"), where=f"{where}.growth_parameter_role",
                                               registry=registry)
        gross_annual = _field(s, "gross_annual", where=where, field_meta=field_meta,
                               path=f"income.sources[{i}].gross_annual",
                               expected_dollar_class="current_run_rate_nominal", required=True)
        out.append(IncomeSourceV3(
            id=sid, owner=_require(s, "owner", where=where), kind=kind, label=s.get("label", ""),
            gross_annual=gross_annual, stability=stability, growth_parameter_role=growth_role,
            starts_at=_require(s, "starts_at", where=where), ends_at=s.get("ends_at"),
        ))

    net_estimate = _field(raw, "net_annual_estimate", where="income", field_meta=field_meta,
                           path="income.net_annual_estimate", expected_dollar_class="current_run_rate_nominal")
    return tuple(out), net_estimate


def _parse_spending(raw: dict, *, field_meta: dict, registry: Registry, member_ids: set) -> SpendingV3:
    where = "spending"
    if not isinstance(raw, dict):
        raise ProfileV3ValidationError(f"{where}: missing or not a mapping")
    totals_authority = _one_of(raw.get("totals_authority", "declared"), _VALID_TOTALS_AUTHORITY,
                                where=where, field_name="totals_authority")

    categories = []
    for i, c in enumerate(raw.get("categories") or []):
        cwhere = f"{where}.categories[{i}]"
        cid = _require(c, "id", where=cwhere)
        derived_from = c.get("derived_from")
        annual_amount_raw = c.get("annual_amount")

        # Criterion 6: derived_from + independent annual_amount is rejected.
        if derived_from and annual_amount_raw not in (None, ""):
            raise ProfileV3ValidationError(
                f"{cwhere}: 'annual_amount' must be omitted when 'derived_from' is set ({derived_from!r}) — "
                "declaring both would create two independent values for one payment"
            )
        if not derived_from and annual_amount_raw in (None, ""):
            raise ProfileV3ValidationError(
                f"{cwhere}: 'annual_amount' is required when 'derived_from' is not set"
            )

        annual_amount = UNKNOWN
        if annual_amount_raw not in (None, ""):
            annual_amount = _field(c, "annual_amount", where=cwhere, field_meta=field_meta,
                                    path=f"spending.categories[{i}].annual_amount",
                                    expected_dollar_class="real_planning")

        classification = _one_of(_require(c, "classification", where=cwhere), _VALID_CLASSIFICATION,
                                  where=cwhere, field_name="classification")
        cash_flow_pattern = _one_of(c.get("cash_flow_pattern", "recurring"), _VALID_CASH_FLOW_PATTERN,
                                     where=cwhere, field_name="cash_flow_pattern")

        lifecycle = c.get("lifecycle") or {}
        member_ref = c.get("member_ref")
        starts_at = lifecycle.get("starts_at")
        ends_at = lifecycle.get("ends_at")
        # A member-scoped ends_at requires member_ref (Model Spec §7, member-scoped endpoints policy).
        if ends_at and _LIFECYCLE_EVENT_RE.match(ends_at or "") and not member_ref:
            m = _LIFECYCLE_EVENT_RE.match(ends_at)
            if m and m.group(1) in ("retirement", "medicare", "child_independent") and not member_ref:
                raise ProfileV3ValidationError(
                    f"{cwhere}: lifecycle.ends_at {ends_at!r} is member-scoped but 'member_ref' is not set — "
                    "a combined category cannot carry one member's endpoint"
                )
        if member_ref and member_ref not in member_ids:
            raise ProfileV3ReferenceError(f"{cwhere}.member_ref: {member_ref!r} does not resolve against household.members[].id")

        inflation_role = _resolve_parameter_role(c.get("inflation_parameter_role"),
                                                  where=f"{cwhere}.inflation_parameter_role", registry=registry)

        categories.append(SpendingCategoryV3(
            id=cid, label=c.get("label"), annual_amount=annual_amount, classification=classification,
            cash_flow_pattern=cash_flow_pattern, recurrence=c.get("recurrence"), derived_from=derived_from,
            member_ref=member_ref, starts_at=starts_at, ends_at=ends_at,
            multiplier_by_state=lifecycle.get("multiplier_by_state") or {}, constant=bool(lifecycle.get("constant", False)),
            inflation_parameter_role=inflation_role, notes=c.get("notes"),
        ))

    return SpendingV3(
        totals_authority=totals_authority,
        totals_tolerance_pct=raw.get("totals_tolerance_pct", 1),
        annual_total=_field(raw, "annual_total", where=where, field_meta=field_meta, path="spending.annual_total",
                             expected_dollar_class="real_planning"),
        essential=_field(raw, "essential", where=where, field_meta=field_meta, path="spending.essential",
                          expected_dollar_class="real_planning"),
        lifestyle=_field(raw, "lifestyle", where=where, field_meta=field_meta, path="spending.lifestyle",
                          expected_dollar_class="real_planning"),
        discretionary=_field(raw, "discretionary", where=where, field_meta=field_meta, path="spending.discretionary",
                              expected_dollar_class="real_planning"),
        categories=tuple(categories),
    )


def _parse_liquid_and_investments(liquid_raw, investments_raw, *, field_meta: dict) -> "tuple[tuple, tuple]":
    liquid = []
    investments = []
    all_ids: set = set()

    def _check_unique(item_id, where):
        if item_id in all_ids:
            raise ProfileV3ValidationError(
                f"{where}: id {item_id!r} is already used elsewhere in liquid[] or investments[] — "
                "a balance may appear in exactly one place"
            )
        all_ids.add(item_id)

    for i, item in enumerate(liquid_raw or []):
        where = f"liquid[{i}]"
        lid = _require(item, "id", where=where)
        _check_unique(lid, where)
        access = _one_of(_require(item, "access", where=where), _VALID_ACCESS, where=where, field_name="access")
        purpose = item.get("purpose")
        if purpose is not None:
            _one_of(purpose, _VALID_LIQUID_PURPOSE, where=where, field_name="purpose")
        pool = item.get("pool")
        if pool is not None:
            _one_of(pool, _VALID_LIQUID_POOL, where=where, field_name="pool")
        liquid.append(LiquidAssetV3(
            id=lid, label=_require(item, "label", where=where),
            approx_value=_field(item, "approx_value", where=where, field_meta=field_meta,
                                 path=f"liquid[{i}].approx_value", expected_dollar_class="point_in_time_nominal",
                                 required=True),
            access=access, purpose=purpose, pool=pool,
        ))

    for i, item in enumerate(investments_raw or []):
        where = f"investments[{i}]"
        iid = _require(item, "id", where=where)
        _check_unique(iid, where)
        container = _one_of(_require(item, "container", where=where), _VALID_CONTAINER,
                             where=where, field_name="container")
        tax_character = _one_of(_require(item, "tax_character", where=where), _VALID_TAX_CHARACTER,
                                 where=where, field_name="tax_character")
        pool = _one_of(_require(item, "pool", where=where), _VALID_INVESTMENT_POOL, where=where, field_name="pool")
        liquidity = _one_of(_require(item, "liquidity", where=where), _VALID_LIQUIDITY,
                             where=where, field_name="liquidity")
        alloc_raw = item.get("allocation") or {}
        allocation = InvestmentAllocationV3(
            equity_pct=alloc_raw.get("equity_pct", UNKNOWN), fixed_income_pct=alloc_raw.get("fixed_income_pct", UNKNOWN),
            cash_pct=alloc_raw.get("cash_pct", UNKNOWN), other_pct=alloc_raw.get("other_pct", UNKNOWN),
        )
        pcts = [p for p in (allocation.equity_pct, allocation.fixed_income_pct, allocation.cash_pct, allocation.other_pct)
                if p is not UNKNOWN]
        if pcts and abs(sum(pcts) - 100) > 1:
            raise ProfileV3ValidationError(f"{where}.allocation: percentages sum to {sum(pcts)}, must sum to 100 (±1)")

        investments.append(InvestmentV3(
            id=iid, label=_require(item, "label", where=where), owner=item.get("owner", ""),
            approx_value=_field(item, "approx_value", where=where, field_meta=field_meta,
                                 path=f"investments[{i}].approx_value", expected_dollar_class="point_in_time_nominal",
                                 required=True),
            container=container, tax_character=tax_character,
            basis_value=_field(item, "basis_value", where=where, field_meta=field_meta,
                                path=f"investments[{i}].basis_value", expected_dollar_class="point_in_time_nominal"),
            earnings_value=_field(item, "earnings_value", where=where, field_meta=field_meta,
                                   path=f"investments[{i}].earnings_value", expected_dollar_class="point_in_time_nominal"),
            pool=pool, liquidity=liquidity, intended_purpose=item.get("intended_purpose", ""),
            beneficiary=item.get("beneficiary"), return_parameter_role=item.get("return_parameter_role"),
            in_college_return_parameter_role=item.get("in_college_return_parameter_role"),
            allocation=allocation,
        ))

    return tuple(liquid), tuple(investments)


def _parse_debt(raw, *, field_meta: dict) -> "tuple[DebtV3, ...]":
    out = []
    seen_ids = set()
    for i, item in enumerate(raw or []):
        where = f"debt[{i}]"
        did = _require(item, "id", where=where)
        if did in seen_ids:
            raise ProfileV3ValidationError(f"{where}: duplicate debt id {did!r}")
        seen_ids.add(did)
        out.append(DebtV3(
            id=did, label=_require(item, "label", where=where),
            balance=_field(item, "balance", where=where, field_meta=field_meta, path=f"debt[{i}].balance",
                            expected_dollar_class="point_in_time_nominal", required=True),
            apr_pct=_require(item, "apr_pct", where=where), term_months=_require(item, "term_months", where=where),
            months_remaining=_require(item, "months_remaining", where=where),
            monthly_payment=_field(item, "monthly_payment", where=where, field_meta=field_meta,
                                    path=f"debt[{i}].monthly_payment", expected_dollar_class="nominal_contractual",
                                    required=True),
            payoff_date=item.get("payoff_date"),
            type=_one_of(_require(item, "type", where=where), _VALID_DEBT_TYPE, where=where, field_name="type"),
            fixed_or_variable=_one_of(_require(item, "fixed_or_variable", where=where), _VALID_FIXED_VARIABLE,
                                       where=where, field_name="fixed_or_variable"),
            prepayment_penalty=str(item.get("prepayment_penalty") or "none"),
        ))
    return tuple(out)


def _parse_contributions(raw, *, field_meta: dict, registry: Registry, investment_ids: set, income_ids: set) -> "tuple[ContributionV3, ...]":
    out = []
    seen_ids = set()
    for i, item in enumerate(raw or []):
        where = f"contributions[{i}]"
        cid = _require(item, "id", where=where)
        if cid in seen_ids:
            raise ProfileV3ValidationError(f"{where}: duplicate contribution id {cid!r}")
        seen_ids.add(cid)

        account_ref = _require(item, "account_ref", where=where)
        if account_ref not in investment_ids:
            raise ProfileV3ReferenceError(f"{where}.account_ref: {account_ref!r} does not resolve against investments[].id")

        contributor = _one_of(_require(item, "contributor", where=where), _VALID_CONTRIBUTOR,
                               where=where, field_name="contributor")
        destination = _one_of(_require(item, "destination", where=where), _VALID_DESTINATION,
                               where=where, field_name="destination")
        mechanism = _one_of(_require(item, "mechanism", where=where), _VALID_MECHANISM,
                             where=where, field_name="mechanism")

        limit_group_ref = item.get("limit_group_ref")
        if limit_group_ref is not None:
            _one_of(limit_group_ref, _VALID_LIMIT_GROUP, where=where, field_name="limit_group_ref")

        amount_raw = item.get("amount")
        formula_raw = item.get("formula")
        # Criterion 9: amount and formula are mutually exclusive, and exactly one must be present.
        if amount_raw not in (None, "") and formula_raw:
            raise ProfileV3ValidationError(f"{where}: 'amount' and 'formula' are mutually exclusive — set exactly one")
        if amount_raw in (None, "") and not formula_raw:
            raise ProfileV3ValidationError(f"{where}: exactly one of 'amount' or 'formula' is required")

        amount = UNKNOWN
        formula = None
        if amount_raw not in (None, ""):
            amount = _field(item, "amount", where=where, field_meta=field_meta, path=f"contributions[{i}].amount",
                             expected_dollar_class="planned_nominal")
        else:
            fkind = formula_raw.get("kind")
            income_source_ref = formula_raw.get("income_source_ref")
            if fkind == "pct_of_income":
                if not income_source_ref:
                    raise ProfileV3ValidationError(f"{where}.formula: kind 'pct_of_income' requires 'income_source_ref'")
                if income_source_ref not in income_ids:
                    raise ProfileV3ReferenceError(
                        f"{where}.formula.income_source_ref: {income_source_ref!r} does not resolve against income.sources[].id"
                    )
            match_rules = tuple(
                MatchTier(employee_contributes_up_to_pct=t["employee_contributes_up_to_pct"],
                          employer_matches_pct=t["employer_matches_pct"])
                for t in (formula_raw.get("match_rules") or [])
            )
            formula = ContributionFormula(kind=fkind, pct=formula_raw.get("pct"),
                                          income_source_ref=income_source_ref, match_rules=match_rules,
                                          match_schedule_text=formula_raw.get("match_schedule_text"))

        status = _one_of(_require(item, "status", where=where), _VALID_CONTRIBUTION_STATUS,
                          where=where, field_name="status")
        classification = item.get("classification")
        if classification is not None:
            _one_of(classification, _VALID_CONTRIBUTION_CLASS, where=where, field_name="classification")

        limit_policy_raw = item.get("limit_policy") or {}
        limit_policy = LimitPolicy(
            statutory_fact_ref=_resolve_statutory_fact(limit_policy_raw.get("statutory_fact_ref"),
                                                        where=f"{where}.limit_policy.statutory_fact_ref", registry=registry),
            limit_growth_parameter_role=_resolve_parameter_role(
                limit_policy_raw.get("limit_growth_parameter_role"),
                where=f"{where}.limit_policy.limit_growth_parameter_role", registry=registry),
            contribute_to_limit=limit_policy_raw.get("contribute_to_limit"),
        )

        out.append(ContributionV3(
            id=cid, owner=_require(item, "owner", where=where), account_ref=account_ref,
            contributor=contributor, destination=destination, mechanism=mechanism,
            plan_ref=item.get("plan_ref"), limit_group_ref=limit_group_ref, amount=amount, formula=formula,
            starts_at=item.get("starts_at"), ends_at=item.get("ends_at"), classification=classification,
            limit_policy=limit_policy, status=status, notes=item.get("notes"),
        ))
    return tuple(out)


def _parse_education(raw, *, field_meta: dict, registry: Registry, member_ids: set, account_ids: set) -> "tuple[EducationV3, ...]":
    out = []
    seen_ids = set()
    for i, item in enumerate(raw or []):
        where = f"education[{i}]"
        eid = _require(item, "id", where=where)
        if eid in seen_ids:
            raise ProfileV3ValidationError(f"{where}: duplicate education id {eid!r}")
        seen_ids.add(eid)

        beneficiary = _require(item, "beneficiary", where=where)
        if beneficiary not in member_ids:
            raise ProfileV3ReferenceError(f"{where}.beneficiary: {beneficiary!r} does not resolve against household.members[].id")

        cost_role = _resolve_parameter_role(item.get("cost_inflation_parameter_role"),
                                             where=f"{where}.cost_inflation_parameter_role", registry=registry)

        aid_offsets = []
        for j, a in enumerate(item.get("aid_offsets") or []):
            awhere = f"{where}.aid_offsets[{j}]"
            kind = _one_of(_require(a, "kind", where=awhere), _VALID_AID_KIND, where=awhere, field_name="kind")
            status = _one_of(_require(a, "status", where=awhere), _VALID_AID_STATUS, where=awhere, field_name="status")
            aid_offsets.append(AidOffset(
                kind=kind,
                annual_amount=_field(a, "annual_amount", where=awhere, field_meta=field_meta,
                                      path=f"{where}.aid_offsets[{j}].annual_amount",
                                      expected_dollar_class="real_planning", required=True),
                status=status, applies_years=a.get("applies_years"), notes=a.get("notes"),
            ))

        funding_accounts = tuple(item.get("funding_accounts") or ())
        for acc in funding_accounts:
            if acc not in account_ids:
                raise ProfileV3ReferenceError(f"{where}.funding_accounts: {acc!r} does not resolve against investments[].id")

        fp_raw = item.get("funding_policy") or {}
        order = _one_of(_require(fp_raw, "order", where=f"{where}.funding_policy"), _VALID_FUNDING_ORDER,
                         where=f"{where}.funding_policy", field_name="order")
        # Criterion 13: parse and validate `order` only. NO smoothing algorithm implemented here or anywhere.
        shortfall_sources = tuple(fp_raw.get("shortfall_sources") or ())
        for s in shortfall_sources:
            _one_of(s, _VALID_SHORTFALL_SOURCE, where=f"{where}.funding_policy.shortfall_sources", field_name="shortfall_sources")
        funding_policy = FundingPolicy(order=order, manual_schedule=tuple(fp_raw.get("manual_schedule") or ()),
                                        shortfall_sources=shortfall_sources)

        out.append(EducationV3(
            id=eid, beneficiary=beneficiary, start_year=_require(item, "start_year", where=where),
            end_year=_require(item, "end_year", where=where),
            annual_cost=_field(item, "annual_cost", where=where, field_meta=field_meta,
                                path=f"education[{i}].annual_cost", expected_dollar_class="real_planning",
                                required=True),
            cost_inflation_parameter_role=cost_role, aid_offsets=tuple(aid_offsets),
            funding_accounts=funding_accounts, funding_policy=funding_policy,
            flexibility=item.get("flexibility"), notes=item.get("notes"),
        ))
    return tuple(out)


def _parse_obligations(raw, *, field_meta: dict, account_ids: set) -> "tuple[ObligationV3, ...]":
    out = []
    for i, item in enumerate(raw or []):
        where = f"obligations[{i}]"
        funding_accounts = tuple(item.get("funding_accounts") or ())
        for acc in funding_accounts:
            if acc not in account_ids:
                raise ProfileV3ReferenceError(f"{where}.funding_accounts: {acc!r} does not resolve against liquid[]/investments[].id")
        out.append(ObligationV3(
            id=_require(item, "id", where=where), label=_require(item, "label", where=where),
            target_year=_require(item, "target_year", where=where),
            estimated_total_cost=_field(item, "estimated_total_cost", where=where, field_meta=field_meta,
                                         path=f"obligations[{i}].estimated_total_cost",
                                         expected_dollar_class="real_planning", required=True),
            funding_accounts=funding_accounts,
            flexibility=_one_of(_require(item, "flexibility", where=where), _VALID_FLEXIBILITY,
                                 where=where, field_name="flexibility"),
        ))
    return tuple(out)


def _parse_goals(raw: dict, *, field_meta: dict) -> GoalsV3:
    goals = (raw or {}).get("retirement") or {}
    return GoalsV3(
        desired_annual_spending=_field(goals, "desired_annual_spending", where="goals.retirement",
                                        field_meta=field_meta, path="goals.retirement.desired_annual_spending",
                                        expected_dollar_class="real_planning"),
        other=tuple((raw or {}).get("other") or ()),
    )


def _parse_safety_reserve(raw: dict) -> SafetyReservePolicyV3:
    where = "safety_reserve"
    months = _require(raw, "target_months_of_essential", where=where)
    return SafetyReservePolicyV3(target_months_of_essential=months, rationale=raw.get("rationale"),
                                  decision_ref=raw.get("decision_ref"))


def _parse_tax(raw: dict, *, field_meta: dict, registry: Registry) -> TaxV3:
    tax = raw.get("tax") or {}
    observed = []
    for i, o in enumerate(tax.get("observed_liability") or []):
        where = f"tax.observed_liability[{i}]"
        scope = _one_of(_require(o, "scope", where=where), _VALID_TAX_SCOPE, where=where, field_name="scope")
        if "includes_payroll" not in o:
            raise ProfileV3ValidationError(f"{where}: 'includes_payroll' is required and must never be ambiguous")
        observed.append(ObservedLiability(
            tax_year=_require(o, "tax_year", where=where), scope=scope,
            jurisdiction=_require(o, "jurisdiction", where=where), includes_payroll=bool(o["includes_payroll"]),
            amount=_field(o, "amount", where=where, field_meta=field_meta, path=f"tax.observed_liability[{i}].amount",
                          expected_dollar_class="observed_period_nominal", required=True),
            basis_income=_field(o, "basis_income", where=where, field_meta=field_meta,
                                 path=f"tax.observed_liability[{i}].basis_income",
                                 expected_dollar_class="observed_period_nominal"),
            status=o.get("status", "ACTUAL"), source=o.get("source"), notes=o.get("notes"),
        ))

    payroll = tax.get("payroll") or {}
    return TaxV3(
        observed_liability=tuple(observed),
        marginal_rate_parameter_role=_resolve_parameter_role(tax.get("marginal_rate_parameter_role"),
                                                              where="tax.marginal_rate_parameter_role", registry=registry),
        capital_gains_parameter_role=_resolve_parameter_role(tax.get("capital_gains_parameter_role"),
                                                              where="tax.capital_gains_parameter_role", registry=registry),
        social_security_rate_role=_resolve_parameter_role(payroll.get("social_security_rate_role"),
                                                           where="tax.payroll.social_security_rate_role", registry=registry),
        social_security_wage_base_growth_role=_resolve_parameter_role(
            payroll.get("social_security_wage_base_growth_role"),
            where="tax.payroll.social_security_wage_base_growth_role", registry=registry),
        medicare_rate_role=_resolve_parameter_role(payroll.get("medicare_rate_role"),
                                                    where="tax.payroll.medicare_rate_role", registry=registry),
        additional_medicare_rate_role=_resolve_parameter_role(payroll.get("additional_medicare_rate_role"),
                                                               where="tax.payroll.additional_medicare_rate_role",
                                                               registry=registry),
    )


def load_profile_v3(raw: dict, path, *, registry: Registry) -> ProfileV3:
    """`raw` is the already-parsed YAML mapping; `path` is used only for error
    messages. `synthetic` and `schema_version` are validated by the caller
    (`profile_load.load_profile`) before this is invoked."""
    field_meta: "dict[str, FieldMeta]" = {}

    household = _parse_household(raw.get("household") or {}, field_meta=field_meta, registry=registry)
    member_ids = {m.id for m in household}
    debt = _parse_debt(raw.get("debt"), field_meta=field_meta)
    debt_ids = {d.id for d in debt}

    income_sources, income_net = _parse_income(raw.get("income") or {}, field_meta=field_meta, registry=registry)
    income_ids = {s.id for s in income_sources}

    liquid, investments = _parse_liquid_and_investments(raw.get("liquid"), raw.get("investments"), field_meta=field_meta)
    account_ids = {a.id for a in liquid} | {a.id for a in investments}

    education = _parse_education(raw.get("education"), field_meta=field_meta, registry=registry,
                                  member_ids=member_ids, account_ids=account_ids)
    education_ids = {e.id for e in education}

    spending = _parse_spending(raw.get("spending") or {}, field_meta=field_meta, registry=registry, member_ids=member_ids)
    contributions = _parse_contributions(raw.get("contributions"), field_meta=field_meta, registry=registry,
                                          investment_ids={a.id for a in investments}, income_ids=income_ids)
    obligations = _parse_obligations(raw.get("obligations"), field_meta=field_meta, account_ids=account_ids)
    goals = _parse_goals(raw.get("goals") or {}, field_meta=field_meta)
    safety_reserve = _parse_safety_reserve(raw.get("safety_reserve") or {})
    tax = _parse_tax(raw, field_meta=field_meta, registry=registry)

    education_funding_capacity = []
    for i, item in enumerate(raw.get("education_funding_capacity") or []):
        where = f"education_funding_capacity[{i}]"
        allocable_to = item.get("allocable_to")
        if allocable_to not in (None, "all") and isinstance(allocable_to, list):
            for eid in allocable_to:
                if eid not in education_ids:
                    raise ProfileV3ReferenceError(f"{where}.allocable_to: {eid!r} does not resolve against education[].id")
        education_funding_capacity.append(EducationFundingCapacityV3(
            id=_require(item, "id", where=where), starts_at=item.get("starts_at"), ends_at=item.get("ends_at"),
            annual_amount=_field(item, "annual_amount", where=where, field_meta=field_meta,
                                  path=f"{where}.annual_amount", expected_dollar_class="planned_nominal", required=True),
            source=item.get("source"), redirected_from_contribution_ref=item.get("redirected_from_contribution_ref"),
            allocable_to=allocable_to, status=item.get("status"),
        ))

    # Typed lifecycle event resolution (criterion 5) — sweep every event-shaped
    # string we've collected, now that every id-namespace is known.
    for i, m in enumerate(raw.get("household", {}).get("members") or []):
        retirement = m.get("retirement") or {}
        # target_date/target_age are not lifecycle-event strings; nothing to resolve there.
        indep = m.get("independent_year")
        hc = m.get("healthcare") or {}
        for j, e in enumerate(hc.get("elections") or []):
            _resolve_lifecycle_event(e.get("starts_at"), where=f"household.members[{i}].healthcare.elections[{j}].starts_at",
                                      member_ids=member_ids, debt_ids=debt_ids, education_ids=education_ids)
            _resolve_lifecycle_event(e.get("ends_at"), where=f"household.members[{i}].healthcare.elections[{j}].ends_at",
                                      member_ids=member_ids, debt_ids=debt_ids, education_ids=education_ids)
    for i, s in enumerate(raw.get("income", {}).get("sources") or []):
        _resolve_lifecycle_event(s.get("starts_at"), where=f"income.sources[{i}].starts_at",
                                  member_ids=member_ids, debt_ids=debt_ids, education_ids=education_ids)
        _resolve_lifecycle_event(s.get("ends_at"), where=f"income.sources[{i}].ends_at",
                                  member_ids=member_ids, debt_ids=debt_ids, education_ids=education_ids)
    for i, c in enumerate(raw.get("spending", {}).get("categories") or []):
        lifecycle = c.get("lifecycle") or {}
        _resolve_lifecycle_event(lifecycle.get("starts_at"), where=f"spending.categories[{i}].lifecycle.starts_at",
                                  member_ids=member_ids, debt_ids=debt_ids, education_ids=education_ids)
        _resolve_lifecycle_event(lifecycle.get("ends_at"), where=f"spending.categories[{i}].lifecycle.ends_at",
                                  member_ids=member_ids, debt_ids=debt_ids, education_ids=education_ids)
    for i, d in enumerate(raw.get("debt") or []):
        pass  # payoff_date is a calendar date, not a typed event — nothing to resolve.
    for i, c in enumerate(raw.get("contributions") or []):
        _resolve_lifecycle_event(c.get("starts_at"), where=f"contributions[{i}].starts_at",
                                  member_ids=member_ids, debt_ids=debt_ids, education_ids=education_ids)
        _resolve_lifecycle_event(c.get("ends_at"), where=f"contributions[{i}].ends_at",
                                  member_ids=member_ids, debt_ids=debt_ids, education_ids=education_ids)

    return ProfileV3(
        schema_version=raw["schema_version"], synthetic=raw["synthetic"],
        profile_version=raw.get("profile_version"), profile_as_of=raw.get("profile_as_of"),
        household=household, income_sources=income_sources, income_net_annual_estimate=income_net,
        spending=spending, liquid=liquid, investments=investments, debt=debt, contributions=contributions,
        education=education, education_funding_capacity=tuple(education_funding_capacity),
        obligations=obligations, goals=goals, safety_reserve=safety_reserve, tax=tax,
        field_meta=field_meta,
    )
