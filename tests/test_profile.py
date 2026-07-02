"""Tests for auth/profile.py: parse, save/load round-trip, builder fallback."""

from __future__ import annotations

from hssk.auth.profile import (
    ProfileData,
    _extract_facility_id,
    load_profile,
    parse_profile,
    save_profile,
)

# ---------------------------------------------------------------------------
# _extract_facility_id
# ---------------------------------------------------------------------------


def test_extract_facility_id_standard():
    assert _extract_facility_id("bnh_27084_lienbao") == "27084"


def test_extract_facility_id_no_match():
    assert _extract_facility_id("admin") is None


def test_extract_facility_id_multiple_segments():
    assert _extract_facility_id("prefix_99999_suffix_extra") == "99999"


# ---------------------------------------------------------------------------
# parse_profile
# ---------------------------------------------------------------------------

_SAMPLE_RESPONSE = {
    "code": 20000,
    "data": {
        "keycloakUserId": "fe371646-1981-41d4-a0ea-b720a7a84515",
        "fullname": "Trạm y tế Liên Bão",
        "username": "bnh_27084_lienbao",
        "isActive": True,
    },
}


def test_parse_profile_happy_path():
    p = parse_profile(_SAMPLE_RESPONSE)
    assert p is not None
    assert p.display_name == "Trạm y tế Liên Bão"
    assert p.username == "bnh_27084_lienbao"
    assert p.healthfacilities_id == "27084"


def test_parse_profile_missing_data_key():
    assert parse_profile({}) is None


def test_parse_profile_empty_data():
    assert parse_profile({"data": {}}) is None


def test_parse_profile_partial_fields():
    raw = {"data": {"fullname": "Test Station", "username": "no_id_here"}}
    p = parse_profile(raw)
    assert p is not None
    assert p.display_name == "Test Station"
    assert p.healthfacilities_id is None


def test_parse_profile_none_input():
    assert parse_profile(None) is None


def test_parse_profile_camelcase_fullname():
    raw = {"data": {"fullName": "Station Alt", "username": "x_12345_y"}}
    p = parse_profile(raw)
    assert p is not None
    assert p.display_name == "Station Alt"
    assert p.healthfacilities_id == "12345"


def test_parse_profile_failure_is_logged_at_debug(caplog):
    import logging

    class _Boom(dict):
        def get(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise RuntimeError("boom")

    with caplog.at_level(logging.DEBUG, logger="hssk.auth.profile"):
        assert parse_profile(_Boom()) is None
    assert "could not parse profile response" in caplog.text


# ---------------------------------------------------------------------------
# identity_label
# ---------------------------------------------------------------------------


def test_identity_label_with_id():
    p = ProfileData(
        display_name="Trạm y tế Liên Bão",
        username="bnh_27084_lienbao",
        healthfacilities_id="27084",
        captured_at=0.0,
    )
    assert p.identity_label() == "Trạm y tế Liên Bão (27084)"


def test_identity_label_without_id():
    p = ProfileData(
        display_name="Trạm y tế Liên Bão",
        username="admin",
        healthfacilities_id=None,
        captured_at=0.0,
    )
    assert p.identity_label() == "Trạm y tế Liên Bão"


# ---------------------------------------------------------------------------
# save / load round-trip
# ---------------------------------------------------------------------------


def test_save_load_roundtrip(tmp_path):
    p = parse_profile(_SAMPLE_RESPONSE)
    assert p is not None
    path = tmp_path / "profile.json"
    save_profile(p, path=path)
    loaded = load_profile(path=path)
    assert loaded is not None
    assert loaded.display_name == p.display_name
    assert loaded.username == p.username
    assert loaded.healthfacilities_id == p.healthfacilities_id


def test_load_profile_missing_file(tmp_path):
    assert load_profile(path=tmp_path / "no_such_file.json") is None


def test_load_profile_corrupt_file(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text("not json", encoding="utf-8")
    assert load_profile(path=path) is None
