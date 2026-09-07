"""profile_load: path -> Profile.

Parses and validates a profile YAML file against the shape defined in
State/profile.schema.yaml, enforces the `synthetic` flag and `schema_version`,
and converts missing optional fields to `Unknown` rather than a default value.
**Read-only — this module never writes to the profile path, under any
circumstance.**

Fail-closed (Phase 3B-4 SPEC rule 3): a missing file, malformed YAML, an
unsupported schema version, or a missing required field raises a typed error
naming what is wrong and, where the field is decision-relevant, which decision
it blocks. Never guess, never silently default a required field.
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .bands import UNKNOWN, Unknown

SUPPORTED_SCHEMA_VERSION = 2

_VALID_STABILITY = {"stable", "variable", "at_risk"}
_VALID_ACCESS = {"immediate", "days", "weeks"}
_VALID_TAX_TREATMENT = {"taxable", "tax_deferred", "tax_free", "education_529"}
_VALID_LIQUIDITY = {"immediate", "days", "penalty_before_age", "locked"}
_VALID_DEBT_TYPE = {"mortgage", "auto", "student", "other"}
_VALID_FIXED_VARIABLE = {"fixed", "variable"}
_VALID_FUNDING_SOURCE = {"529", "taxable", "future_income", "undecided"}
_VALID_FLEXIBILITY = {"fixed", "somewhat_flexible", "flexible"}


class ProfileError(Exception):
    """Base for every typed error this module raises."""


class ProfileFileError(ProfileError):
    """The profile file could not be found or opened."""


class ProfileFormatError(ProfileError):
    """The file is not valid YAML, or not shaped as a mapping."""


class SyntheticFlagError(ProfileError):
    """Missing or non-boolean `synthetic:` — the machine-checkable line between
    test and real data (SPEC rule 5). Refusing to load blocks every decision."""


class SchemaVersionError(ProfileError):
    """`schema_version` missing or not one this engine understands."""


class ProfileValidationError(ProfileError):
    """A required field is missing, empty, or has an invalid value."""


# --------------------------------------------------------------------------
# Profile shape (mirrors State/profile.schema.yaml)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class HouseholdMember:
    role: str
    age: int
    target_retirement_age: "int | Unknown" = UNKNOWN


@dataclass(frozen=True)
class IncomeSource:
    label: str
    gross_annual: float
    stability: str
    growth_assumption_pct: "float | Unknown" = UNKNOWN


@dataclass(frozen=True)
class Spending:
    annual_total: "float | Unknown"
    essential: "float | Unknown"
    lifestyle: "float | Unknown"
    discretionary: "float | Unknown"
    notes: str = ""


@dataclass(frozen=True)
class LiquidAsset:
    label: str
    approx_value: float
    access: str  # immediate | days | weeks
    # Optional (Phase 3B-4a, C2). None means "not declared" — distinct from
    # Unknown, which is reserved for facts the profile doesn't state. Absence
    # of a declared purpose is itself a normal, expected profile shape.
    purpose: "str | None" = None


@dataclass(frozen=True)
class InvestmentAllocation:
    equity_pct: "float | Unknown" = UNKNOWN
    fixed_income_pct: "float | Unknown" = UNKNOWN
    cash_pct: "float | Unknown" = UNKNOWN
    other_pct: "float | Unknown" = UNKNOWN


@dataclass(frozen=True)
class Investment:
    label: str
    approx_value: float
    tax_treatment: str
    liquidity: str
    intended_purpose: str
    allocation: InvestmentAllocation


@dataclass(frozen=True)
class Debt:
    label: str
    balance: float
    apr_pct: float
    term_months: int
    months_remaining: int
    monthly_payment: float
    type: str
    fixed_or_variable: str
    prepayment_penalty: str = "none"


@dataclass(frozen=True)
class Obligation:
    label: str
    target_year: int
    estimated_total_cost: float
    already_funded: float
    funding_source: str
    flexibility: str


@dataclass(frozen=True)
class RetirementGoals:
    target_age_adult_1: "int | Unknown" = UNKNOWN
    target_age_adult_2: "int | Unknown" = UNKNOWN
    desired_annual_spending: "float | Unknown" = UNKNOWN
    social_security_estimate_annual: "float | Unknown" = UNKNOWN
    other_retirement_income: "float | Unknown" = UNKNOWN
    # Phase 3B-4a, C3: one flat ongoing annual figure, no escalation/schedule.
    annual_contribution: "float | Unknown" = UNKNOWN


@dataclass(frozen=True)
class SafetyReservePolicy:
    target_months_of_essential: float
    rationale: str = ""


@dataclass(frozen=True)
class ScenarioAssumptions:
    equity_return_pct: float
    fixed_income_return_pct: float
    inflation_pct: float
    income_continues: "bool | str"
    longevity_age: int


@dataclass(frozen=True)
class TaxAssumptions:
    marginal_federal_pct: str = ""
    marginal_state_pct: str = ""
    capital_gains_pct: str = ""


@dataclass(frozen=True)
class Profile:
    schema_version: int
    synthetic: bool
    household: "list[HouseholdMember]"
    income_sources: "list[IncomeSource]"
    income_net_annual_estimate: "float | Unknown"
    spending: Spending
    liquid: "list[LiquidAsset]"
    investments: "list[Investment]"
    debts: "list[Debt]"
    obligations: "list[Obligation]"
    retirement_goals: RetirementGoals
    safety_reserve: SafetyReservePolicy
    scenario_base: ScenarioAssumptions
    scenario_downside: ScenarioAssumptions
    tax: TaxAssumptions = field(default_factory=TaxAssumptions)


# --------------------------------------------------------------------------
# Parsing helpers — every one converts an absent optional field to UNKNOWN and
# raises ProfileValidationError, naming the field, for a missing required one.
# --------------------------------------------------------------------------


def _require(mapping: dict, key: str, *, where: str, blocks: str):
    if not isinstance(mapping, dict) or key not in mapping or mapping[key] in (None, ""):
        raise ProfileValidationError(f"{where}: missing required field '{key}' — blocks {blocks}")
    return mapping[key]


def _optional(mapping: dict, key: str, default=UNKNOWN):
    if not isinstance(mapping, dict):
        return default
    value = mapping.get(key, default)
    if value in (None, "", "UNKNOWN", "unknown"):
        return default
    return value


def _one_of(value, allowed: set, *, where: str, field_name: str):
    if value not in allowed:
        raise ProfileValidationError(
            f"{where}: field '{field_name}' has invalid value {value!r} — expected one of {sorted(allowed)}"
        )
    return value


def _parse_household(raw: dict) -> "list[HouseholdMember]":
    members_raw = _require(raw, "members", where="household", blocks="every age-driven calculation")
    if not isinstance(members_raw, list) or not members_raw:
        raise ProfileValidationError("household.members: must be a non-empty list")

    members = []
    for i, m in enumerate(members_raw):
        where = f"household.members[{i}]"
        role = _require(m, "role", where=where, blocks="bucket/obligation attribution")
        age = _require(m, "age", where=where, blocks="retirement horizon and reserve sizing")
        if not isinstance(age, int) or isinstance(age, bool) or age < 0 or age > 120:
            raise ProfileValidationError(f"{where}: 'age' must be a plausible integer, got {age!r}")
        target_retirement_age = _optional(m, "target_retirement_age")
        members.append(HouseholdMember(role=role, age=age, target_retirement_age=target_retirement_age))
    return members


def _parse_income(raw: dict) -> "tuple[list[IncomeSource], float | Unknown]":
    sources_raw = _require(raw, "sources", where="income", blocks="reserve and surplus sizing")
    if not isinstance(sources_raw, list) or not sources_raw:
        raise ProfileValidationError("income.sources: must be a non-empty list")

    sources = []
    for i, s in enumerate(sources_raw):
        where = f"income.sources[{i}]"
        label = _require(s, "label", where=where, blocks="income attribution")
        gross_annual = _require(s, "gross_annual", where=where, blocks="reserve and surplus sizing")
        stability = _one_of(
            _require(s, "stability", where=where, blocks="safety reserve sizing"),
            _VALID_STABILITY, where=where, field_name="stability",
        )
        growth = _optional(s, "growth_assumption_pct")
        sources.append(IncomeSource(label=label, gross_annual=gross_annual, stability=stability,
                                     growth_assumption_pct=growth))

    net_estimate = _optional(raw, "net_annual_estimate")
    return sources, net_estimate


def _parse_spending(raw: dict) -> Spending:
    where = "spending"
    if not isinstance(raw, dict):
        raise ProfileValidationError(f"{where}: missing or not a mapping — blocks every downstream decision")
    return Spending(
        annual_total=_optional(raw, "annual_total"),
        essential=_optional(raw, "essential"),
        lifestyle=_optional(raw, "lifestyle"),
        discretionary=_optional(raw, "discretionary"),
        notes=raw.get("notes") or "",
    )


def _parse_liquid(raw) -> "list[LiquidAsset]":
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ProfileValidationError("liquid: must be a list")
    out = []
    for i, item in enumerate(raw):
        where = f"liquid[{i}]"
        label = _require(item, "label", where=where, blocks="bucket assignment")
        value = _require(item, "approx_value", where=where, blocks="resilience funded calculation")
        access = _one_of(
            _require(item, "access", where=where, blocks="resilience funded calculation"),
            _VALID_ACCESS, where=where, field_name="access",
        )
        purpose = item.get("purpose") or None  # optional; None means "not declared"
        out.append(LiquidAsset(label=label, approx_value=value, access=access, purpose=purpose))
    return out


def _parse_investments(raw) -> "list[Investment]":
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ProfileValidationError("investments: must be a list")
    out = []
    for i, item in enumerate(raw):
        where = f"investments[{i}]"
        label = _require(item, "label", where=where, blocks="bucket assignment")
        value = _require(item, "approx_value", where=where, blocks="bucket/surplus sizing")
        tax_treatment = _one_of(
            _require(item, "tax_treatment", where=where, blocks="bucket assignment"),
            _VALID_TAX_TREATMENT, where=where, field_name="tax_treatment",
        )
        liquidity = _one_of(
            _require(item, "liquidity", where=where, blocks="bucket assignment"),
            _VALID_LIQUIDITY, where=where, field_name="liquidity",
        )
        intended_purpose = _require(item, "intended_purpose", where=where, blocks="bucket assignment")
        alloc_raw = item.get("allocation") or {}
        allocation = InvestmentAllocation(
            equity_pct=_optional(alloc_raw, "equity_pct"),
            fixed_income_pct=_optional(alloc_raw, "fixed_income_pct"),
            cash_pct=_optional(alloc_raw, "cash_pct"),
            other_pct=_optional(alloc_raw, "other_pct"),
        )
        out.append(Investment(label=label, approx_value=value, tax_treatment=tax_treatment,
                               liquidity=liquidity, intended_purpose=intended_purpose, allocation=allocation))
    return out


def _parse_debts(raw) -> "list[Debt]":
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ProfileValidationError("debt: must be a list")
    out = []
    for i, item in enumerate(raw):
        where = f"debt[{i}]"
        out.append(Debt(
            label=_require(item, "label", where=where, blocks="debt-vs-invest analysis"),
            balance=_require(item, "balance", where=where, blocks="debt-vs-invest analysis"),
            apr_pct=_require(item, "apr_pct", where=where, blocks="debt-vs-invest analysis"),
            term_months=_require(item, "term_months", where=where, blocks="debt-vs-invest analysis"),
            months_remaining=_require(item, "months_remaining", where=where, blocks="debt-vs-invest analysis"),
            monthly_payment=_require(item, "monthly_payment", where=where, blocks="debt-vs-invest analysis"),
            type=_one_of(_require(item, "type", where=where, blocks="debt-vs-invest analysis"),
                         _VALID_DEBT_TYPE, where=where, field_name="type"),
            fixed_or_variable=_one_of(
                _require(item, "fixed_or_variable", where=where, blocks="debt-vs-invest analysis"),
                _VALID_FIXED_VARIABLE, where=where, field_name="fixed_or_variable",
            ),
            prepayment_penalty=str(item.get("prepayment_penalty") or "none"),
        ))
    return out


def _parse_obligations(raw) -> "list[Obligation]":
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ProfileValidationError("obligations: must be a list")
    out = []
    for i, item in enumerate(raw):
        where = f"obligations[{i}]"
        out.append(Obligation(
            label=_require(item, "label", where=where, blocks="obligations-gap calculation"),
            target_year=_require(item, "target_year", where=where, blocks="obligations-gap calculation"),
            estimated_total_cost=_require(item, "estimated_total_cost", where=where, blocks="obligations-gap calculation"),
            already_funded=_require(item, "already_funded", where=where, blocks="obligations-gap calculation"),
            funding_source=_one_of(
                _require(item, "funding_source", where=where, blocks="obligations-gap calculation"),
                _VALID_FUNDING_SOURCE, where=where, field_name="funding_source",
            ),
            flexibility=_one_of(
                _require(item, "flexibility", where=where, blocks="obligations-gap calculation"),
                _VALID_FLEXIBILITY, where=where, field_name="flexibility",
            ),
        ))
    return out


def _parse_retirement_goals(raw: dict) -> RetirementGoals:
    goals = (raw or {}).get("retirement") or {}
    return RetirementGoals(
        target_age_adult_1=_optional(goals, "target_age_adult_1"),
        target_age_adult_2=_optional(goals, "target_age_adult_2"),
        desired_annual_spending=_optional(goals, "desired_annual_spending"),
        social_security_estimate_annual=_optional(goals, "social_security_estimate_annual"),
        other_retirement_income=_optional(goals, "other_retirement_income"),
        annual_contribution=_optional(goals, "annual_contribution"),
    )


def _parse_safety_reserve(raw: dict) -> SafetyReservePolicy:
    where = "safety_reserve"
    months = _require(raw, "target_months_of_essential", where=where, blocks="resilience sizing")
    if not isinstance(months, (int, float)) or isinstance(months, bool) or months <= 0:
        raise ProfileValidationError(f"{where}: 'target_months_of_essential' must be a positive number, got {months!r}")
    return SafetyReservePolicy(target_months_of_essential=months, rationale=raw.get("rationale") or "")


def _parse_scenario(raw: dict, *, name: str) -> ScenarioAssumptions:
    where = f"scenarios.{name}"
    if not isinstance(raw, dict):
        raise ProfileValidationError(f"{where}: missing or not a mapping — blocks the retirement projection")
    return ScenarioAssumptions(
        equity_return_pct=_require(raw, "equity_return_pct", where=where, blocks="retirement projection"),
        fixed_income_return_pct=_require(raw, "fixed_income_return_pct", where=where, blocks="retirement projection"),
        inflation_pct=_require(raw, "inflation_pct", where=where, blocks="retirement projection"),
        income_continues=_require(raw, "income_continues", where=where, blocks="retirement projection"),
        longevity_age=_require(raw, "longevity_age", where=where, blocks="retirement projection"),
    )


def _parse_scenarios(raw: dict) -> "tuple[ScenarioAssumptions, ScenarioAssumptions]":
    scenarios = raw.get("scenarios") or {}
    base = _parse_scenario(scenarios.get("base") or {}, name="base")
    downside = _parse_scenario(scenarios.get("reasonable_downside") or {}, name="reasonable_downside")
    return base, downside


def _parse_tax(raw: dict) -> TaxAssumptions:
    tax = raw.get("tax") or {}
    return TaxAssumptions(
        marginal_federal_pct=str(tax.get("marginal_federal_pct") or ""),
        marginal_state_pct=str(tax.get("marginal_state_pct") or ""),
        capital_gains_pct=str(tax.get("capital_gains_pct") or ""),
    )


def load_profile(path) -> Profile:
    """Read-only. Never writes to `path` under any circumstance."""
    path = Path(path)
    if not path.is_file():
        raise ProfileFileError(f"profile file not found: {path}")

    try:
        text = path.read_text()
    except OSError as exc:
        raise ProfileFileError(f"could not read {path}: {exc}") from exc

    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ProfileFormatError(f"{path}: could not parse YAML ({exc})") from exc

    if not isinstance(raw, dict):
        raise ProfileFormatError(f"{path}: top-level content must be a mapping")

    if "synthetic" not in raw:
        raise SyntheticFlagError(
            f"{path}: missing required 'synthetic: true|false' — refusing to load. This is "
            "the machine-checkable line between test and real data (SPEC rule 5)."
        )
    synthetic = raw["synthetic"]
    if not isinstance(synthetic, bool):
        raise SyntheticFlagError(f"{path}: 'synthetic' must be a boolean, got {synthetic!r}")

    schema_version = raw.get("schema_version")
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise SchemaVersionError(
            f"{path}: unsupported schema_version {schema_version!r} "
            f"(this engine supports {SUPPORTED_SCHEMA_VERSION}) — blocks every decision until resolved"
        )

    household = _parse_household(raw.get("household") or {})
    income_sources, income_net = _parse_income(raw.get("income") or {})
    spending = _parse_spending(raw.get("spending") or {})
    liquid = _parse_liquid(raw.get("liquid"))
    investments = _parse_investments(raw.get("investments"))
    debts = _parse_debts(raw.get("debt"))
    obligations = _parse_obligations(raw.get("obligations"))
    retirement_goals = _parse_retirement_goals(raw.get("goals") or {})
    safety_reserve = _parse_safety_reserve(raw.get("safety_reserve") or {})
    scenario_base, scenario_downside = _parse_scenarios(raw)
    tax = _parse_tax(raw)

    return Profile(
        schema_version=schema_version,
        synthetic=synthetic,
        household=household,
        income_sources=income_sources,
        income_net_annual_estimate=income_net,
        spending=spending,
        liquid=liquid,
        investments=investments,
        debts=debts,
        obligations=obligations,
        retirement_goals=retirement_goals,
        safety_reserve=safety_reserve,
        scenario_base=scenario_base,
        scenario_downside=scenario_downside,
        tax=tax,
    )
