"""registry_load: path -> Registry.

Loads and fail-closed validates the Parameter & Assumption Registry
(`schemas/assumption-registry.schema.yaml`, rev 4.1). This is F2 scope only
as far as the 14 acceptance criteria require: parameter-role resolution,
dollar-class validation on monetary assumptions, and criterion 10 (every
`required: true` parameter role must be bound in every assumption set;
a pinned binding's version must exist). No projection, no return-path
execution — `return_paths[]` is parsed and validated shape-only.
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .field_meta import INPUT_DOLLAR_CLASSES, OUTPUT_ONLY_DOLLAR_CLASS

_VALID_VERSION_POLICY = {"pinned", "latest"}
_VALID_RETURN_PATH_KIND = {"constant", "sequence"}
_VALID_APPLIES_TO = {"portfolio_total", "asset_class"}


class RegistryError(Exception):
    """Base for every typed error this module raises."""


class RegistryFormatError(RegistryError):
    """The registry file could not be found, opened, or parsed as YAML."""


class RegistryValidationError(RegistryError):
    """A required field is missing or has an invalid value."""


class RegistryReferenceError(RegistryError):
    """A role, assumption id, or version reference does not resolve —
    includes criterion 10's unbound-required-role and missing-pinned-version
    checks."""


@dataclass(frozen=True)
class Parameter:
    role: str
    description: str = ""
    units: "str | None" = None
    dollar_class: "str | None" = None
    required: bool = False
    notes: "str | None" = None


@dataclass(frozen=True)
class StatutoryFact:
    id: str
    kind: str
    tax_year: int
    jurisdiction: str
    value: object
    units: "str | None" = None
    status: str = ""
    source: "str | None" = None
    verified_on: "str | None" = None
    notes: "str | None" = None


@dataclass(frozen=True)
class Assumption:
    id: str
    version: int
    role: str
    category: str = ""
    statement: str = ""
    value: object = None
    units: "str | None" = None
    dollar_class: "str | None" = None
    status: str = ""
    cost_scope: "str | None" = None
    cost_component: "str | None" = None
    source: "str | None" = None
    rationale: "str | None" = None
    notes: "str | None" = None


@dataclass(frozen=True)
class Binding:
    role: str
    assumption_id: str
    version_policy: str
    pinned_version: "int | None" = None


@dataclass(frozen=True)
class AssumptionSet:
    id: str
    name: str = ""
    description: str = ""
    status: str = ""
    bindings: "tuple[Binding, ...]" = ()
    notes: "str | None" = None


@dataclass(frozen=True)
class ReturnPath:
    id: str
    description: str = ""
    applies_to: str = "portfolio_total"
    kind: str = "constant"
    start_anchor: "str | None" = None
    sequence_pct: "tuple[float, ...]" = ()
    after_sequence: "str | None" = None
    rationale: "str | None" = None
    status: str = ""


@dataclass(frozen=True)
class Registry:
    registry_version: int
    registry_as_of: "str | None"
    parameters: "dict[str, Parameter]"          # keyed by role
    statutory_facts: "dict[str, StatutoryFact]"  # keyed by id
    assumptions: "dict[tuple[str, int], Assumption]"  # keyed by (id, version)
    assumption_sets: "dict[str, AssumptionSet]"  # keyed by id
    return_paths: "dict[str, ReturnPath]"        # keyed by id

    def published_versions(self, assumption_id: str) -> "set[int]":
        return {v for (aid, v) in self.assumptions if aid == assumption_id}


def _require(mapping: dict, key: str, *, where: str):
    if not isinstance(mapping, dict) or key not in mapping or mapping[key] in (None, ""):
        raise RegistryValidationError(f"{where}: missing required field '{key}'")
    return mapping[key]


def _parse_parameters(raw: list) -> "dict[str, Parameter]":
    out: "dict[str, Parameter]" = {}
    for i, p in enumerate(raw or []):
        where = f"parameters[{i}]"
        role = _require(p, "role", where=where)
        if role in out:
            raise RegistryValidationError(f"{where}: duplicate parameter role {role!r}")
        dollar_class = p.get("dollar_class")
        if dollar_class is not None and dollar_class not in INPUT_DOLLAR_CLASSES:
            if dollar_class == OUTPUT_ONLY_DOLLAR_CLASS:
                raise RegistryValidationError(
                    f"{where}: dollar_class 'projected_nominal' is engine-output-only, never valid here"
                )
            raise RegistryValidationError(f"{where}: dollar_class {dollar_class!r} is not a valid input class")
        out[role] = Parameter(
            role=role, description=p.get("description", ""), units=p.get("units"),
            dollar_class=dollar_class, required=bool(p.get("required", False)), notes=p.get("notes"),
        )
    return out


def _parse_statutory_facts(raw: list) -> "dict[str, StatutoryFact]":
    out: "dict[str, StatutoryFact]" = {}
    for i, f in enumerate(raw or []):
        where = f"statutory_facts[{i}]"
        fid = _require(f, "id", where=where)
        if fid in out:
            raise RegistryValidationError(f"{where}: duplicate statutory_fact id {fid!r}")
        status = _require(f, "status", where=where)
        if status not in {"ACTUAL", "CONFIRMED"}:
            raise RegistryValidationError(
                f"{where}: statutory_facts status must be ACTUAL or CONFIRMED, got {status!r} — "
                "anything else is a belief and belongs in assumptions[]"
            )
        out[fid] = StatutoryFact(
            id=fid, kind=_require(f, "kind", where=where), tax_year=_require(f, "tax_year", where=where),
            jurisdiction=_require(f, "jurisdiction", where=where), value=_require(f, "value", where=where),
            units=f.get("units"), status=status, source=f.get("source"),
            verified_on=f.get("verified_on"), notes=f.get("notes"),
        )
    return out


def _parse_assumptions(raw: list, parameters: "dict[str, Parameter]") -> "dict[tuple[str, int], Assumption]":
    out: "dict[tuple[str, int], Assumption]" = {}
    for i, a in enumerate(raw or []):
        where = f"assumptions[{i}]"
        aid = _require(a, "id", where=where)
        version = _require(a, "version", where=where)
        key = (aid, version)
        if key in out:
            raise RegistryValidationError(f"{where}: duplicate (id, version) {key!r}")
        role = _require(a, "role", where=where)
        if role not in parameters:
            raise RegistryReferenceError(f"{where}: role {role!r} does not resolve against parameters[]")
        status = _require(a, "status", where=where)
        if status == "ACTUAL":
            raise RegistryValidationError(
                f"{where}: an assumption's status may never be ACTUAL — a measured value is a fact "
                "and belongs in statutory_facts[] or the Profile, not here"
            )
        dollar_class = a.get("dollar_class")
        if dollar_class is not None:
            if dollar_class == OUTPUT_ONLY_DOLLAR_CLASS:
                raise RegistryValidationError(
                    f"{where}: dollar_class 'projected_nominal' is engine-output-only, never valid on an assumption"
                )
            if dollar_class not in INPUT_DOLLAR_CLASSES:
                raise RegistryValidationError(f"{where}: dollar_class {dollar_class!r} is not a valid input class")
        out[key] = Assumption(
            id=aid, version=version, role=role, category=a.get("category", ""),
            statement=a.get("statement", ""), value=a.get("value"), units=a.get("units"),
            dollar_class=dollar_class, status=status, cost_scope=a.get("cost_scope"),
            cost_component=a.get("cost_component"), source=a.get("source"),
            rationale=a.get("rationale"), notes=a.get("notes"),
        )
    return out


def _parse_bindings(raw: list, *, where: str, parameters: "dict[str, Parameter]",
                     assumptions: "dict[tuple[str, int], Assumption]") -> "tuple[Binding, ...]":
    bindings = []
    for i, b in enumerate(raw or []):
        bwhere = f"{where}.bindings[{i}]"
        role = _require(b, "role", where=bwhere)
        if role not in parameters:
            raise RegistryReferenceError(f"{bwhere}: role {role!r} does not resolve against parameters[]")
        assumption_id = _require(b, "assumption_id", where=bwhere)
        version_policy = _require(b, "version_policy", where=bwhere)
        if version_policy not in _VALID_VERSION_POLICY:
            raise RegistryValidationError(f"{bwhere}: version_policy must be one of {sorted(_VALID_VERSION_POLICY)}")
        pinned_version = b.get("pinned_version")
        if version_policy == "pinned":
            if pinned_version is None:
                raise RegistryValidationError(f"{bwhere}: version_policy 'pinned' requires 'pinned_version'")
            if (assumption_id, pinned_version) not in assumptions:
                raise RegistryReferenceError(
                    f"{bwhere}: pinned_version {pinned_version} does not resolve to a published "
                    f"version of assumption {assumption_id!r}"
                )
        else:  # latest
            if pinned_version is not None:
                raise RegistryValidationError(
                    f"{bwhere}: version_policy 'latest' must not carry a stale 'pinned_version' — "
                    "ambiguous about whether the pin was abandoned or forgotten"
                )
        if not any(aid == assumption_id for (aid, _v) in assumptions):
            raise RegistryReferenceError(f"{bwhere}: assumption_id {assumption_id!r} does not resolve against assumptions[]")
        bindings.append(Binding(role=role, assumption_id=assumption_id, version_policy=version_policy,
                                 pinned_version=pinned_version))
    return tuple(bindings)


def _parse_assumption_sets(raw: list, *, parameters: "dict[str, Parameter]",
                            assumptions: "dict[tuple[str, int], Assumption]") -> "dict[str, AssumptionSet]":
    out: "dict[str, AssumptionSet]" = {}
    required_roles = {role for role, p in parameters.items() if p.required}
    for i, s in enumerate(raw or []):
        where = f"assumption_sets[{i}]"
        sid = _require(s, "id", where=where)
        if sid in out:
            raise RegistryValidationError(f"{where}: duplicate assumption_sets id {sid!r}")
        bindings = _parse_bindings(s.get("bindings"), where=where, parameters=parameters, assumptions=assumptions)

        # Criterion 10: every required: true parameter role must be bound.
        bound_roles = {b.role for b in bindings}
        missing = required_roles - bound_roles
        if missing:
            raise RegistryReferenceError(
                f"{where} ({sid!r}): required parameter role(s) {sorted(missing)} have no binding — "
                "unbound_required_roles_policy is fail_closed, never a silent default"
            )

        out[sid] = AssumptionSet(
            id=sid, name=s.get("name", ""), description=s.get("description", ""),
            status=s.get("status", ""), bindings=bindings, notes=s.get("notes"),
        )
    return out


def _parse_return_paths(raw: list) -> "dict[str, ReturnPath]":
    out: "dict[str, ReturnPath]" = {}
    for i, r in enumerate(raw or []):
        where = f"return_paths[{i}]"
        rid = _require(r, "id", where=where)
        if rid in out:
            raise RegistryValidationError(f"{where}: duplicate return_paths id {rid!r}")
        kind = r.get("kind", "constant")
        if kind not in _VALID_RETURN_PATH_KIND:
            raise RegistryValidationError(f"{where}: kind must be one of {sorted(_VALID_RETURN_PATH_KIND)}")
        applies_to = r.get("applies_to", "portfolio_total")
        if applies_to not in _VALID_APPLIES_TO:
            raise RegistryValidationError(f"{where}: applies_to must be one of {sorted(_VALID_APPLIES_TO)}")
        if kind == "sequence" and not r.get("start_anchor"):
            raise RegistryValidationError(f"{where}: kind 'sequence' requires 'start_anchor'")
        out[rid] = ReturnPath(
            id=rid, description=r.get("description", ""), applies_to=applies_to, kind=kind,
            start_anchor=r.get("start_anchor"), sequence_pct=tuple(r.get("sequence_pct") or ()),
            after_sequence=r.get("after_sequence"), rationale=r.get("rationale"), status=r.get("status", ""),
        )
    return out


def load_registry(path) -> Registry:
    """Read-only. Never writes to `path`."""
    path = Path(path)
    if not path.is_file():
        raise RegistryFormatError(f"registry file not found: {path}")
    try:
        text = path.read_text()
    except OSError as exc:
        raise RegistryFormatError(f"could not read {path}: {exc}") from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RegistryFormatError(f"{path}: could not parse YAML ({exc})") from exc
    if not isinstance(raw, dict):
        raise RegistryFormatError(f"{path}: top-level content must be a mapping")

    parameters = _parse_parameters(raw.get("parameters"))
    statutory_facts = _parse_statutory_facts(raw.get("statutory_facts"))
    assumptions = _parse_assumptions(raw.get("assumptions"), parameters)
    assumption_sets = _parse_assumption_sets(raw.get("assumption_sets"), parameters=parameters, assumptions=assumptions)
    return_paths = _parse_return_paths(raw.get("return_paths"))

    return Registry(
        registry_version=raw.get("registry_version", 0),
        registry_as_of=raw.get("registry_as_of"),
        parameters=parameters,
        statutory_facts=statutory_facts,
        assumptions=assumptions,
        assumption_sets=assumption_sets,
        return_paths=return_paths,
    )
