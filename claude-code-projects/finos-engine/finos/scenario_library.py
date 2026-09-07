"""scenario_library: path -> ScenarioLibrary.

Loads and fail-closed validates the Scenario Library
(`schemas/scenario-library.schema.yaml`, rev 4.1): the override tagged-union
validation (F2 criterion 11) and the `expected_outcome.status:
APPROVED_TARGET` reproducibility gate (criterion 12). No scenario is ever
*executed* here — there is no timeline engine in F2, only structural and
reference validation of the scenario's shape.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from .registry_load import Registry

_SEGMENT_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*)(\[id=([^\]]+)\])?$")
_VALID_TARGET = {"profile", "parameter_binding"}
_VALID_VERSION_POLICY = {"pinned", "latest"}
_VALID_DEFINITION_STATUS = {"APPROVED", "DRAFT", "SUPERSEDED", "ARCHIVED"}
_VALID_OUTCOME_STATUS = {"PRELIMINARY", "REVIEWED", "APPROVED_TARGET", "SUPERSEDED"}
_VALID_TOLERANCE_KIND = {"exact", "absolute", "relative_pct", "range", "qualitative"}
_VALID_RECONCILIATION_POLICY = {"flag_only", "flag_and_block"}


class ScenarioLibraryError(Exception):
    """Base for every typed error this module raises."""


class ScenarioLibraryFormatError(ScenarioLibraryError):
    """The scenario library file could not be found, opened, or parsed."""


class ScenarioLibraryValidationError(ScenarioLibraryError):
    """A required field is missing or has an invalid value."""


class ScenarioOverrideError(ScenarioLibraryError):
    """An override is mis-tagged, half-specified, or references something
    that does not resolve. Fail closed — a mis-tagged override that silently
    no-ops is worse than one that errors (schema rev 4.1 rationale)."""


@dataclass(frozen=True)
class RebindTo:
    assumption_id: str
    version_policy: str
    pinned_version: "int | None" = None


@dataclass(frozen=True)
class ScenarioOverride:
    target: str
    reason: str
    path: "str | None" = None
    value: object = None
    parameter_role: "str | None" = None
    rebind_to: "RebindTo | None" = None


@dataclass(frozen=True)
class ToleranceSpec:
    kind: str
    value: "float | None" = None
    low: "float | None" = None
    high: "float | None" = None


@dataclass(frozen=True)
class ExpectedOutcomeMetric:
    metric: str
    expected: object
    tolerance: ToleranceSpec
    rationale: "str | None" = None


@dataclass(frozen=True)
class ExpectedOutcome:
    status: str
    source: "str | None" = None
    as_of: "str | None" = None
    derived_by: "str | None" = None
    confidence: "str | None" = None
    metrics: "tuple[ExpectedOutcomeMetric, ...]" = ()
    reconciliation_policy: str = "flag_only"
    notes: "str | None" = None


@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    description: "str | None"
    definition_status: str
    inherits: "str | None"
    assumption_set: str
    return_path: "str | None"
    overrides: "tuple[ScenarioOverride, ...]"
    toggles: dict
    expected_outcome: "ExpectedOutcome | None"
    source: "str | None" = None
    notes: "str | None" = None


@dataclass(frozen=True)
class ScenarioLibrary:
    schema_version: int
    scenarios: "dict[str, Scenario]"


def _require(mapping: dict, key: str, *, where: str):
    if not isinstance(mapping, dict) or key not in mapping or mapping[key] in (None, ""):
        raise ScenarioLibraryValidationError(f"{where}: missing required field '{key}'")
    return mapping[key]


def _resolve_profile_path(profile_raw: dict, path: str, *, where: str):
    """Resolves a dotted path with `[id=...]` list filters against the RAW
    parsed profile mapping (not the typed ProfileV3) — the schema's own
    dotted-path examples (e.g. `household.members[id=adult_1].retirement.
    target_age`) are written against the YAML shape directly, so resolving
    against the YAML mapping needs no attribute-name translation layer."""
    obj = profile_raw
    for seg in path.split("."):
        m = _SEGMENT_RE.match(seg)
        if not m:
            raise ScenarioOverrideError(f"{where}: path segment {seg!r} in {path!r} is not well-formed")
        attr, _, filter_id = m.groups()
        if not isinstance(obj, dict) or attr not in obj:
            raise ScenarioOverrideError(f"{where}: path {path!r} does not resolve against the profile (no field {attr!r})")
        obj = obj[attr]
        if filter_id is not None:
            if not isinstance(obj, list):
                raise ScenarioOverrideError(f"{where}: path {path!r} — {attr!r} is not a list, cannot filter by id")
            match = next((item for item in obj if isinstance(item, dict) and item.get("id") == filter_id), None)
            if match is None:
                raise ScenarioOverrideError(f"{where}: path {path!r} — no entry with id={filter_id!r} in {attr!r}")
            obj = match
    return obj


def _parse_override(raw: dict, *, where: str, registry: Registry, profile_raw: "dict | None") -> ScenarioOverride:
    target = _one_of_target(_require(raw, "target", where=where), where=where)
    reason = _require(raw, "reason", where=where)

    has_path_group = raw.get("path") is not None or raw.get("value") is not None
    has_binding_group = raw.get("parameter_role") is not None or raw.get("rebind_to") is not None

    if target == "profile":
        if raw.get("path") is None or raw.get("value") is None:
            raise ScenarioOverrideError(f"{where}: target 'profile' requires both 'path' and 'value'")
        if has_binding_group:
            raise ScenarioOverrideError(f"{where}: target 'profile' forbids 'parameter_role'/'rebind_to'")
        path = raw["path"]
        if profile_raw is not None:
            _resolve_profile_path(profile_raw, path, where=where)
        return ScenarioOverride(target=target, reason=reason, path=path, value=raw["value"])

    # target == "parameter_binding"
    if raw.get("parameter_role") is None or raw.get("rebind_to") is None:
        raise ScenarioOverrideError(f"{where}: target 'parameter_binding' requires both 'parameter_role' and 'rebind_to'")
    if has_path_group:
        raise ScenarioOverrideError(f"{where}: target 'parameter_binding' forbids 'path'/'value'")

    parameter_role = raw["parameter_role"]
    if parameter_role not in registry.parameters:
        raise ScenarioOverrideError(f"{where}.parameter_role: {parameter_role!r} does not resolve against the registry")

    rb_raw = raw["rebind_to"]
    assumption_id = _require(rb_raw, "assumption_id", where=f"{where}.rebind_to")
    if not any(aid == assumption_id for (aid, _v) in registry.assumptions):
        raise ScenarioOverrideError(f"{where}.rebind_to.assumption_id: {assumption_id!r} does not resolve against the registry")
    version_policy = _require(rb_raw, "version_policy", where=f"{where}.rebind_to")
    if version_policy not in _VALID_VERSION_POLICY:
        raise ScenarioLibraryValidationError(f"{where}.rebind_to.version_policy: must be one of {sorted(_VALID_VERSION_POLICY)}")
    pinned_version = rb_raw.get("pinned_version")
    if version_policy == "pinned":
        if pinned_version is None:
            raise ScenarioOverrideError(f"{where}.rebind_to: version_policy 'pinned' requires 'pinned_version'")
        if (assumption_id, pinned_version) not in registry.assumptions:
            raise ScenarioOverrideError(
                f"{where}.rebind_to.pinned_version: {pinned_version} is not a published version of {assumption_id!r}"
            )
    else:
        if pinned_version is not None:
            raise ScenarioOverrideError(
                f"{where}.rebind_to: version_policy 'latest' must not carry a stale 'pinned_version'"
            )

    return ScenarioOverride(
        target=target, reason=reason, parameter_role=parameter_role,
        rebind_to=RebindTo(assumption_id=assumption_id, version_policy=version_policy, pinned_version=pinned_version),
    )


def _one_of_target(value, *, where: str) -> str:
    if value not in _VALID_TARGET:
        raise ScenarioLibraryValidationError(f"{where}: target must be one of {sorted(_VALID_TARGET)}, got {value!r}")
    return value


def _parse_expected_outcome(raw: "dict | None", *, where: str, registry: Registry, assumption_set_id: str) -> "ExpectedOutcome | None":
    if not raw:
        return None
    status = _require(raw, "status", where=where)
    if status not in _VALID_OUTCOME_STATUS:
        raise ScenarioLibraryValidationError(f"{where}.status: must be one of {sorted(_VALID_OUTCOME_STATUS)}")

    # Criterion 12: APPROVED_TARGET requires every binding in the scenario's
    # assumption_set to be pinned. Fail closed on any `latest` binding.
    if status == "APPROVED_TARGET":
        assumption_set = registry.assumption_sets.get(assumption_set_id)
        if assumption_set is None:
            raise ScenarioOverrideError(f"{where}: assumption_set {assumption_set_id!r} does not resolve against the registry")
        unpinned = [b.role for b in assumption_set.bindings if b.version_policy != "pinned"]
        if unpinned:
            raise ScenarioLibraryValidationError(
                f"{where}: expected_outcome.status is APPROVED_TARGET but assumption_set "
                f"{assumption_set_id!r} has non-pinned binding(s) for role(s) {sorted(unpinned)} — "
                "a `latest` binding re-resolves on revision, so the approved target would silently move"
            )

    metrics = []
    for i, m in enumerate(raw.get("metrics") or []):
        mwhere = f"{where}.metrics[{i}]"
        tol_raw = _require(m, "tolerance", where=mwhere)
        kind = _require(tol_raw, "kind", where=f"{mwhere}.tolerance")
        if kind not in _VALID_TOLERANCE_KIND:
            raise ScenarioLibraryValidationError(f"{mwhere}.tolerance.kind: must be one of {sorted(_VALID_TOLERANCE_KIND)}")
        metrics.append(ExpectedOutcomeMetric(
            metric=_require(m, "metric", where=mwhere), expected=m.get("expected"),
            tolerance=ToleranceSpec(kind=kind, value=tol_raw.get("value"), low=tol_raw.get("low"), high=tol_raw.get("high")),
            rationale=m.get("rationale"),
        ))

    reconciliation_policy = raw.get("reconciliation_policy", "flag_only")
    if reconciliation_policy not in _VALID_RECONCILIATION_POLICY:
        raise ScenarioLibraryValidationError(
            f"{where}.reconciliation_policy: must be one of {sorted(_VALID_RECONCILIATION_POLICY)}"
        )
    if reconciliation_policy == "flag_and_block" and status != "APPROVED_TARGET":
        raise ScenarioLibraryValidationError(
            f"{where}: reconciliation_policy 'flag_and_block' requires status APPROVED_TARGET"
        )

    return ExpectedOutcome(
        status=status, source=raw.get("source"), as_of=raw.get("as_of"), derived_by=raw.get("derived_by"),
        confidence=raw.get("confidence"), metrics=tuple(metrics), reconciliation_policy=reconciliation_policy,
        notes=raw.get("notes"),
    )


def load_scenario_library(path, *, registry: Registry, profile_raw: "dict | None" = None) -> ScenarioLibrary:
    """Read-only. `profile_raw` is the RAW parsed profile mapping (not
    `ProfileV3`) — when supplied, `target: profile` override paths are
    resolved against it; when omitted, path syntax is still validated but
    not resolved (a documented choice, not a silent pass)."""
    path = Path(path)
    if not path.is_file():
        raise ScenarioLibraryFormatError(f"scenario library file not found: {path}")
    try:
        text = path.read_text()
    except OSError as exc:
        raise ScenarioLibraryFormatError(f"could not read {path}: {exc}") from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ScenarioLibraryFormatError(f"{path}: could not parse YAML ({exc})") from exc
    if not isinstance(raw, dict):
        raise ScenarioLibraryFormatError(f"{path}: top-level content must be a mapping")

    scenarios: "dict[str, Scenario]" = {}
    for i, s in enumerate(raw.get("scenarios") or []):
        where = f"scenarios[{i}]"
        sid = _require(s, "id", where=where)
        if sid in scenarios:
            raise ScenarioLibraryValidationError(f"{where}: duplicate scenario id {sid!r}")

        definition_status = _require(s, "definition_status", where=where)
        if definition_status not in _VALID_DEFINITION_STATUS:
            raise ScenarioLibraryValidationError(f"{where}.definition_status: must be one of {sorted(_VALID_DEFINITION_STATUS)}")

        assumption_set_id = _require(s, "assumption_set", where=where)
        if assumption_set_id not in registry.assumption_sets:
            raise ScenarioOverrideError(f"{where}.assumption_set: {assumption_set_id!r} does not resolve against the registry")

        return_path_id = s.get("return_path")
        if return_path_id is not None and return_path_id not in registry.return_paths:
            raise ScenarioOverrideError(f"{where}.return_path: {return_path_id!r} does not resolve against the registry")

        overrides = tuple(
            _parse_override(o, where=f"{where}.overrides[{j}]", registry=registry, profile_raw=profile_raw)
            for j, o in enumerate(s.get("overrides") or [])
        )

        expected_outcome = _parse_expected_outcome(
            s.get("expected_outcome"), where=f"{where}.expected_outcome", registry=registry,
            assumption_set_id=assumption_set_id,
        )

        scenarios[sid] = Scenario(
            id=sid, name=s.get("name", ""), description=s.get("description"),
            definition_status=definition_status, inherits=s.get("inherits"),
            assumption_set=assumption_set_id, return_path=return_path_id, overrides=overrides,
            toggles=s.get("toggles") or {}, expected_outcome=expected_outcome,
            source=s.get("source"), notes=s.get("notes"),
        )

    return ScenarioLibrary(schema_version=raw.get("schema_version", 1), scenarios=scenarios)
