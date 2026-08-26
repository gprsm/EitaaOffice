from __future__ import annotations

import base64
import json
import struct
from dataclasses import dataclass
from typing import Any, Iterable

from .errors import ProtocolError


WIRE_VARINT = 0
WIRE_FIXED64 = 1
WIRE_LENGTH = 2
WIRE_FIXED32 = 5


def encode_varint(value: int) -> bytes:
    if value < 0:
        value &= (1 << 64) - 1
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def decode_varint(data: bytes | bytearray | memoryview, offset: int = 0) -> tuple[int, int]:
    result = 0
    shift = 0
    pos = offset
    while pos < len(data) and shift < 70:
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return result, pos
        shift += 7
    raise ProtocolError("Invalid or truncated varint")


class ProtoWriter:
    def __init__(self) -> None:
        self._buf = bytearray()

    def _tag(self, field: int, wire: int) -> None:
        if field <= 0:
            raise ValueError("Protobuf field number must be positive")
        self._buf.extend(encode_varint((field << 3) | wire))

    def varint(self, field: int, value: int) -> "ProtoWriter":
        self._tag(field, WIRE_VARINT)
        self._buf.extend(encode_varint(value))
        return self

    int32 = varint
    int64 = varint

    def bool(self, field: int, value: bool) -> "ProtoWriter":
        return self.varint(field, 1 if value else 0)

    def fixed32(self, field: int, value: int) -> "ProtoWriter":
        self._tag(field, WIRE_FIXED32)
        self._buf.extend(struct.pack("<I", value & 0xFFFFFFFF))
        return self

    def fixed64(self, field: int, value: int) -> "ProtoWriter":
        self._tag(field, WIRE_FIXED64)
        self._buf.extend(struct.pack("<Q", value & 0xFFFFFFFFFFFFFFFF))
        return self

    def bytes(self, field: int, value: bytes | bytearray | memoryview) -> "ProtoWriter":
        raw = bytes(value)
        self._tag(field, WIRE_LENGTH)
        self._buf.extend(encode_varint(len(raw)))
        self._buf.extend(raw)
        return self

    def string(self, field: int, value: str) -> "ProtoWriter":
        return self.bytes(field, value.encode("utf-8"))

    def message(self, field: int, value: "ProtoWriter | bytes") -> "ProtoWriter":
        return self.bytes(field, value.build() if isinstance(value, ProtoWriter) else value)

    def repeated_varint(self, field: int, values: Iterable[int], *, packed: bool = False) -> "ProtoWriter":
        values = list(values)
        if packed:
            body = b"".join(encode_varint(v) for v in values)
            return self.bytes(field, body)
        for value in values:
            self.varint(field, value)
        return self

    def repeated_bytes(self, field: int, values: Iterable[bytes]) -> "ProtoWriter":
        for value in values:
            self.bytes(field, value)
        return self

    def raw(self, value: bytes) -> "ProtoWriter":
        self._buf.extend(value)
        return self

    def build(self) -> bytes:
        return bytes(self._buf)


@dataclass(slots=True)
class ProtoField:
    number: int
    wire: int
    value: int | bytes


class ProtoReader:
    def __init__(self, data: bytes | bytearray | memoryview):
        self.data = memoryview(data)
        self.offset = 0

    @property
    def has_more(self) -> bool:
        return self.offset < len(self.data)

    def read_varint(self) -> int:
        value, self.offset = decode_varint(self.data, self.offset)
        return value

    def tag(self) -> tuple[int, int]:
        tag = self.read_varint()
        field, wire = tag >> 3, tag & 7
        if field <= 0 or wire not in {WIRE_VARINT, WIRE_FIXED64, WIRE_LENGTH, WIRE_FIXED32}:
            raise ProtocolError(f"Unsupported protobuf tag field={field} wire={wire}")
        return field, wire

    def read_bytes(self) -> bytes:
        length = self.read_varint()
        end = self.offset + length
        if end > len(self.data):
            raise ProtocolError("Truncated length-delimited field")
        value = self.data[self.offset:end].tobytes()
        self.offset = end
        return value

    def read_fixed32(self) -> int:
        end = self.offset + 4
        if end > len(self.data):
            raise ProtocolError("Truncated fixed32")
        value = struct.unpack("<I", self.data[self.offset:end])[0]
        self.offset = end
        return value

    def read_fixed64(self) -> int:
        end = self.offset + 8
        if end > len(self.data):
            raise ProtocolError("Truncated fixed64")
        value = struct.unpack("<Q", self.data[self.offset:end])[0]
        self.offset = end
        return value

    def read_value(self, wire: int) -> int | bytes:
        if wire == WIRE_VARINT:
            return self.read_varint()
        if wire == WIRE_LENGTH:
            return self.read_bytes()
        if wire == WIRE_FIXED32:
            return self.read_fixed32()
        if wire == WIRE_FIXED64:
            return self.read_fixed64()
        raise ProtocolError(f"Unsupported wire type {wire}")

    def fields(self) -> list[ProtoField]:
        out: list[ProtoField] = []
        while self.has_more:
            number, wire = self.tag()
            out.append(ProtoField(number, wire, self.read_value(wire)))
        return out


def parse_fields(data: bytes) -> list[ProtoField]:
    return ProtoReader(data).fields()


def get_first(fields: list[ProtoField], number: int, default: Any = None) -> Any:
    for field in fields:
        if field.number == number:
            return field.value
    return default


def get_all(fields: list[ProtoField], number: int) -> list[Any]:
    return [field.value for field in fields if field.number == number]


def wrapped_string(value: str) -> bytes:
    return ProtoWriter().string(1, value).build()


def wrapped_int(value: int) -> bytes:
    return ProtoWriter().int64(1, value).build()


def int_list_wrapper(values: Iterable[int]) -> bytes:
    # Observed nullable/list wrapper shape used by several Bale requests.
    return ProtoWriter().repeated_varint(1, values).build()


def _try_utf8(raw: bytes) -> str | None:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if not text:
        return ""
    printable = sum(ch.isprintable() or ch in "\r\n\t" for ch in text)
    return text if printable / len(text) >= 0.85 else None


def _try_nested(raw: bytes, depth: int, max_depth: int) -> list[dict[str, Any]] | None:
    if not raw or depth >= max_depth:
        return None
    try:
        fields = parse_fields(raw)
    except Exception:
        return None
    if not fields:
        return None
    # Reject many false positives caused by arbitrary bytes.
    if any(field.number > 100_000 for field in fields):
        return None
    return [_field_to_json(field, depth + 1, max_depth) for field in fields]


def _field_to_json(field: ProtoField, depth: int, max_depth: int) -> dict[str, Any]:
    result: dict[str, Any] = {"field": field.number, "wire": field.wire}
    if isinstance(field.value, int):
        result["value"] = field.value
        return result
    raw = field.value
    result["length"] = len(raw)
    text = _try_utf8(raw)
    nested = _try_nested(raw, depth, max_depth)
    if text is not None:
        result["text"] = text
    if nested is not None:
        result["nested"] = nested
    result["hex"] = raw.hex()
    result["base64"] = base64.b64encode(raw).decode("ascii")
    return result


def decode_tree(data: bytes, *, max_depth: int = 5) -> list[dict[str, Any]]:
    return [_field_to_json(field, 0, max_depth) for field in parse_fields(data)]


def encode_field_spec(spec: list[dict[str, Any]] | dict[str, Any]) -> bytes:
    """Encode a JSON-friendly field specification.

    Accepted form::

        [
          {"field": 1, "type": "int", "value": 42},
          {"field": 2, "type": "string", "value": "hello"},
          {"field": 3, "type": "message", "value": [...]},
          {"field": 4, "type": "hex", "value": "0a01ff"}
        ]
    """
    if isinstance(spec, dict):
        spec = spec.get("fields", [])
    if not isinstance(spec, list):
        raise ValueError("Field spec must be a list or {'fields': [...]} object")
    writer = ProtoWriter()
    for item in spec:
        field = int(item["field"])
        kind = str(item.get("type", "int")).lower()
        value = item.get("value")
        if kind in {"int", "int32", "int64", "varint", "enum"}:
            writer.varint(field, int(value))
        elif kind == "bool":
            writer.bool(field, bool(value))
        elif kind == "string":
            writer.string(field, str(value))
        elif kind == "bytes":
            if isinstance(value, str):
                writer.bytes(field, value.encode("utf-8"))
            else:
                writer.bytes(field, bytes(value))
        elif kind == "hex":
            writer.bytes(field, bytes.fromhex(str(value)))
        elif kind == "base64":
            writer.bytes(field, base64.b64decode(str(value)))
        elif kind in {"message", "nested"}:
            writer.bytes(field, encode_field_spec(value))
        elif kind == "repeated_int":
            writer.repeated_varint(field, [int(v) for v in value], packed=bool(item.get("packed", False)))
        elif kind == "repeated_message":
            writer.repeated_bytes(field, [encode_field_spec(v) for v in value])
        elif kind == "fixed32":
            writer.fixed32(field, int(value))
        elif kind == "fixed64":
            writer.fixed64(field, int(value))
        else:
            raise ValueError(f"Unknown field type: {kind}")
    return writer.build()


def pretty_tree(data: bytes) -> str:
    try:
        return json.dumps(decode_tree(data), ensure_ascii=False, indent=2)
    except Exception as exc:
        return json.dumps({"decode_error": str(exc), "hex": data.hex()}, indent=2)
