import uuid

from app.db.uuid_types import GUID


def test_guid_roundtrip_uses_uuid_value():
    sample = uuid.uuid4()
    guid = GUID()
    value = guid.process_bind_param(sample, None)
    assert isinstance(value, bytes)
    assert len(value) == 16
    assert guid.process_result_value(value, None) == sample


def test_guid_rejects_invalid_uuid_string():
    guid = GUID()
    try:
        guid.process_bind_param("not-a-uuid", None)
    except ValueError:
        return
    raise AssertionError("Expected ValueError for invalid UUID string")
