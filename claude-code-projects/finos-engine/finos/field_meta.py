"""field_meta: the Field[T] wrapper/unwrapper shared by every v3 loader.

A v3 monetary (or other provenance-bearing) field accepts either form:

    essential: 96000                    # short form — a bare scalar

    essential:                          # long form — provenance
      value: 96000
      dollar_class: real_planning
      status: ESTIMATE
      ...

Short form unwraps to the scalar with no metadata. Long form unwraps to the
*same* scalar plus a `FieldMeta` recording provenance. The two must never
diverge on the scalar they produce — that equality is F2 acceptance
criterion 3.

`value` and `status` are REQUIRED in long form. `dollar_class` is required
whenever the caller declares this a monetary field, and must be one of the
SIX INPUT classes — `projected_nominal` is engine-output-only and is never
valid on an input field (F1 rev 4.1 final audit item 2; F2 criterion 4).
"""

from dataclasses import dataclass

# The seven dollar classes from FINANCIAL-MODEL-SPEC.md §4. Six are valid on
# an input field; `projected_nominal` is engine output only.
INPUT_DOLLAR_CLASSES = frozenset({
    "point_in_time_nominal",
    "current_run_rate_nominal",
    "observed_period_nominal",
    "real_planning",
    "nominal_contractual",
    "planned_nominal",
})
OUTPUT_ONLY_DOLLAR_CLASS = "projected_nominal"
ALL_DOLLAR_CLASSES = INPUT_DOLLAR_CLASSES | {OUTPUT_ONLY_DOLLAR_CLASS}

STATUS_VOCAB = frozenset({"ACTUAL", "CONFIRMED", "ESTIMATE", "PLANNED", "PROVISIONAL"})


class FieldValidationError(Exception):
    """A Field[T] (short or long form) is malformed, or declares a value this
    engine must fail closed on (e.g. `projected_nominal` on an input field,
    or a status outside the vocabulary)."""


@dataclass(frozen=True)
class FieldMeta:
    value: object
    units: "str | None" = None
    dollar_class: "str | None" = None
    dollar_basis: "str | None" = None
    dollars_as_of: "int | None" = None
    as_of: "str | None" = None
    status: "str | None" = None
    source: "str | None" = None
    notes: "str | None" = None


def unwrap_field(raw, *, where: str, dollar_class_required: bool = False,
                  expected_dollar_class: "str | None" = None):
    """Returns (scalar_value, FieldMeta | None).

    `raw` not a mapping -> short form: (raw, None).
    `raw` a mapping -> long form: validates `value`/`status` present,
    `dollar_class` per the rules above, `status` against the vocabulary, and
    returns (value, FieldMeta(...)).

    `expected_dollar_class`, when given, is the ONE dollar class this schema
    position permits (e.g. `income.sources[].gross_annual` must be
    `current_run_rate_nominal`) — a declared class that disagrees is a fail-
    closed error, not a silent override.
    """
    if not isinstance(raw, dict):
        return raw, None

    if "value" not in raw or raw["value"] in (None, ""):
        raise FieldValidationError(f"{where}: long-form field missing required 'value'")
    value = raw["value"]

    status = raw.get("status")
    if not status:
        raise FieldValidationError(f"{where}: long-form field missing required 'status'")
    if status not in STATUS_VOCAB:
        raise FieldValidationError(
            f"{where}: 'status' {status!r} is not in the vocabulary {sorted(STATUS_VOCAB)}"
        )

    dollar_class = raw.get("dollar_class")
    if dollar_class_required or expected_dollar_class is not None:
        if not dollar_class:
            raise FieldValidationError(f"{where}: monetary field missing required 'dollar_class'")
        if dollar_class == OUTPUT_ONLY_DOLLAR_CLASS:
            raise FieldValidationError(
                f"{where}: dollar_class 'projected_nominal' is engine-output-only and is never "
                "valid on an input field"
            )
        if dollar_class not in INPUT_DOLLAR_CLASSES:
            raise FieldValidationError(
                f"{where}: dollar_class {dollar_class!r} is not one of the six input classes "
                f"{sorted(INPUT_DOLLAR_CLASSES)}"
            )
        if expected_dollar_class is not None and dollar_class != expected_dollar_class:
            raise FieldValidationError(
                f"{where}: dollar_class {dollar_class!r} does not match the class this field "
                f"requires ({expected_dollar_class!r})"
            )

    meta = FieldMeta(
        value=value,
        units=raw.get("units"),
        dollar_class=dollar_class,
        dollar_basis=raw.get("dollar_basis"),
        dollars_as_of=raw.get("dollars_as_of"),
        as_of=raw.get("as_of"),
        status=status,
        source=raw.get("source"),
        notes=raw.get("notes"),
    )
    return value, meta
