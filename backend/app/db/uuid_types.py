import uuid

from sqlalchemy import TypeDecorator
from sqlalchemy.dialects.mysql import BINARY


class GUID(TypeDecorator):
    impl = BINARY
    cache_ok = True

    def __init__(self, length: int = 16, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.impl = BINARY(length)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(str(value))
        return value.bytes

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(bytes=value)


def uuid_to_mysql_bytes(value: uuid.UUID | str | None) -> bytes | None:
    if value is None:
        return None
    return uuid.UUID(str(value)).bytes


def mysql_bytes_to_uuid(value: bytes | bytearray | None) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, bytearray):
        value = bytes(value)
    return uuid.UUID(bytes=value)
