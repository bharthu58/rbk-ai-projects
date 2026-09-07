"""Required test 9 (SPEC): fail-closed behaviour across every error path —
one place that names every typed error this engine can raise, so a future
change that silently swallows one of them shows up as a single obvious
failure here, in addition to each error's own dedicated test elsewhere."""

from pathlib import Path

import pytest

from finos.profile_load import (
    ProfileFileError,
    ProfileFormatError,
    ProfileValidationError,
    SchemaVersionError,
    SyntheticFlagError,
    load_profile,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("fixture_name,expected_error", [
    ("does-not-exist.yaml", ProfileFileError),
    ("malformed-yaml-syntax.yaml", ProfileFormatError),
    ("malformed-missing-synthetic-flag.yaml", SyntheticFlagError),
    ("malformed-unknown-schema-version.yaml", SchemaVersionError),
    ("malformed-negative-values.yaml", ProfileValidationError),
])
def test_every_malformed_fixture_fails_closed_with_the_right_typed_error(fixture_name, expected_error):
    with pytest.raises(expected_error):
        load_profile(FIXTURES / fixture_name)


def test_every_typed_error_is_a_profile_error_subclass():
    """A caller can always catch the base class without enumerating every
    specific subtype — but the specific type is still available when wanted."""
    from finos.profile_load import ProfileError
    for cls in (ProfileFileError, ProfileFormatError, ProfileValidationError,
                SchemaVersionError, SyntheticFlagError):
        assert issubclass(cls, ProfileError)


def test_non_mapping_yaml_top_level_fails_closed(tmp_path):
    path = tmp_path / "profile.yaml"
    path.write_text("- just\n- a\n- list\n")
    with pytest.raises(ProfileFormatError):
        load_profile(path)


def test_empty_file_fails_closed(tmp_path):
    path = tmp_path / "profile.yaml"
    path.write_text("")
    with pytest.raises((SyntheticFlagError, ProfileFormatError)):
        load_profile(path)
