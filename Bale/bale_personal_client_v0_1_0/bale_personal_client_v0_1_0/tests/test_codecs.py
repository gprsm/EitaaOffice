from bale_personal_client.codecs import (
    build_load_history,
    build_send_message,
    decode_history,
    encode_peer,
    encode_text_content,
)
from bale_personal_client.models import Peer, PeerType
from bale_personal_client.wire import ProtoWriter, get_first, parse_fields


def test_peer_and_send_text_shape():
    peer = Peer(id=42, type=PeerType.PRIVATE, access_hash=99)
    peer_fields = parse_fields(encode_peer(peer))
    assert get_first(peer_fields, 1) == 1
    assert get_first(peer_fields, 2) == 42
    assert get_first(peer_fields, 3) == 99

    raw = build_send_message(peer, 777, encode_text_content("hello"))
    fields = parse_fields(raw)
    assert get_first(fields, 2) == 777
    content = parse_fields(get_first(fields, 3))
    text_message = parse_fields(get_first(content, 15))
    assert get_first(text_message, 1) == b"hello"


def test_load_history_and_decode_text_message():
    peer = Peer(id=42)
    request = parse_fields(build_load_history(peer, limit=7))
    assert get_first(request, 4) == 2
    assert get_first(request, 5) == 7

    message_content = encode_text_content("sample")
    message = (
        ProtoWriter().int64(1, 10).int64(2, 11).int64(3, 12).message(4, message_content).build()
    )
    response = ProtoWriter().message(1, message).build()
    decoded = decode_history(response, peer)
    assert len(decoded) == 1
    assert decoded[0].sender_id == 10
    assert decoded[0].message_id == 11
    assert decoded[0].text == "sample"
