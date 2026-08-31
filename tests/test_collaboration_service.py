import pytest

from app.services.collaboration import merge_field_changes, resource_revision, validate_draft_changes


def test_disjoint_field_changes_merge_against_the_server_snapshot():
    merged = merge_field_changes(
        server_values={"notes": "server note", "num_adults": 1},
        base_values={"notes": "old note", "num_adults": 1},
        changes={"num_adults": 2},
    )

    assert merged.conflicting_fields == ()
    assert merged.values == {"notes": "server note", "num_adults": 2}


def test_same_field_change_is_returned_as_a_structured_conflict():
    merged = merge_field_changes(
        server_values={"notes": "other operator", "num_adults": 1},
        base_values={"notes": "original", "num_adults": 1},
        changes={"notes": "my operator note"},
    )

    assert merged.conflicting_fields == ("notes",)
    assert merged.values["notes"] == "other operator"
    assert merged.values["num_adults"] == 1


def test_revision_is_stable_and_sensitive_draft_fields_are_rejected():
    assert resource_revision({"b": 2, "a": 1}) == resource_revision({"a": 1, "b": 2})
    with pytest.raises(ValueError, match="not editable"):
        validate_draft_changes("reservation", {"amount_paid": 100})
    with pytest.raises(ValueError, match="not editable"):
        validate_draft_changes("settings", {"api_key": "secret"})
