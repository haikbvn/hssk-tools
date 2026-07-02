"""The shared create/update response record-id extractor (api/record_id.py)."""

from __future__ import annotations

import pytest

from hssk.api.record_id import extract_record_id


@pytest.mark.parametrize("key", ["medicalRecordId", "id", "recordId"])
def test_direct_key(key: str) -> None:
    assert extract_record_id({key: 555}) == 555


def test_key_priority() -> None:
    assert extract_record_id({"id": 1, "medicalRecordId": 2}) == 2


def test_nested_data_dict() -> None:
    assert extract_record_id({"data": {"medicalRecordId": 7}}) == 7


def test_scalar_data() -> None:
    assert extract_record_id({"data": 42}) == 42


def test_zero_id_is_still_an_id() -> None:
    assert extract_record_id({"id": 0}) == 0


@pytest.mark.parametrize(
    "data",
    [None, "x", 5, [1, 2], {}, {"data": None}, {"data": [1]}, {"other": 1}],
)
def test_unrecognised_shapes_return_none(data: object) -> None:
    assert extract_record_id(data) is None
