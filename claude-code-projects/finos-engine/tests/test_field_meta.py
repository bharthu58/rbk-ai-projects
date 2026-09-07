"""F2 criterion 3 (unit level) and half of criterion 4: the Field[T]
wrapper/unwrapper shared by every v3 loader."""

import pytest

from finos.field_meta import FieldValidationError, unwrap_field


def test_short_form_unwraps_to_scalar_with_no_metadata():
    value, meta = unwrap_field(96000, where="test")
    assert value == 96000
    assert meta is None


def test_long_form_unwraps_to_identical_scalar_plus_metadata():
    raw = {"value": 96000, "status": "ESTIMATE", "dollar_class": "real_planning",
           "source": "2025 spending review"}
    value, meta = unwrap_field(raw, where="test", expected_dollar_class="real_planning")
    assert value == 96000
    assert meta.status == "ESTIMATE"
    assert meta.dollar_class == "real_planning"
    assert meta.source == "2025 spending review"


def test_short_and_long_form_unwrap_to_the_same_scalar():
    short_value, _ = unwrap_field(96000, where="test")
    long_value, _ = unwrap_field(
        {"value": 96000, "status": "ESTIMATE", "dollar_class": "real_planning"},
        where="test", expected_dollar_class="real_planning",
    )
    assert short_value == long_value == 96000


def test_long_form_missing_value_fails_closed():
    with pytest.raises(FieldValidationError):
        unwrap_field({"status": "ESTIMATE"}, where="test")


def test_long_form_missing_status_fails_closed():
    with pytest.raises(FieldValidationError):
        unwrap_field({"value": 100}, where="test")


def test_long_form_invalid_status_fails_closed():
    with pytest.raises(FieldValidationError):
        unwrap_field({"value": 100, "status": "MADE_UP"}, where="test")


def test_monetary_field_missing_dollar_class_fails_closed():
    with pytest.raises(FieldValidationError):
        unwrap_field({"value": 100, "status": "ESTIMATE"}, where="test", dollar_class_required=True)


@pytest.mark.parametrize("dollar_class", [
    "point_in_time_nominal", "current_run_rate_nominal", "observed_period_nominal",
    "real_planning", "nominal_contractual", "planned_nominal",
])
def test_every_input_dollar_class_is_accepted(dollar_class):
    value, meta = unwrap_field(
        {"value": 100, "status": "ESTIMATE", "dollar_class": dollar_class},
        where="test", dollar_class_required=True,
    )
    assert meta.dollar_class == dollar_class


def test_projected_nominal_is_rejected_on_an_input_field():
    """F1 rev 4.1 final audit item 2: `projected_nominal` is engine-output
    only and is never valid on an input field."""
    with pytest.raises(FieldValidationError):
        unwrap_field(
            {"value": 100, "status": "ESTIMATE", "dollar_class": "projected_nominal"},
            where="test", dollar_class_required=True,
        )


def test_unrecognized_dollar_class_fails_closed():
    with pytest.raises(FieldValidationError):
        unwrap_field(
            {"value": 100, "status": "ESTIMATE", "dollar_class": "made_up_class"},
            where="test", dollar_class_required=True,
        )


def test_dollar_class_disagreeing_with_schema_position_fails_closed():
    """A field wrapped with the wrong declared class (e.g. a balance declared
    `real_planning`) is a fail-closed error, not a silent override."""
    with pytest.raises(FieldValidationError):
        unwrap_field(
            {"value": 100, "status": "ESTIMATE", "dollar_class": "real_planning"},
            where="test", expected_dollar_class="point_in_time_nominal",
        )
