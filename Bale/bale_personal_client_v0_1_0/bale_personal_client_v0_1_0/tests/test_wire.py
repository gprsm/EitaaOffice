from bale_personal_client.wire import (
    ProtoWriter,
    decode_tree,
    encode_field_spec,
    get_all,
    get_first,
    parse_fields,
)


def test_varint_and_nested_roundtrip():
    raw = (
        ProtoWriter()
        .int64(1, 123456789)
        .string(2, "سلام")
        .message(3, ProtoWriter().bool(1, True).int32(2, 151668))
        .build()
    )
    fields = parse_fields(raw)
    assert get_first(fields, 1) == 123456789
    assert get_first(fields, 2).decode() == "سلام"
    nested = parse_fields(get_first(fields, 3))
    assert get_first(nested, 1) == 1
    assert get_first(nested, 2) == 151668


def test_repeated_and_json_spec():
    raw = encode_field_spec([
        {"field": 1, "type": "repeated_int", "value": [1, 2, 3]},
        {"field": 2, "type": "message", "value": [
            {"field": 1, "type": "string", "value": "ok"}
        ]},
    ])
    fields = parse_fields(raw)
    assert get_all(fields, 1) == [1, 2, 3]
    assert get_first(parse_fields(get_first(fields, 2)), 1) == b"ok"
    assert decode_tree(raw)
