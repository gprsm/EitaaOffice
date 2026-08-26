from bale_personal_client.config import BaleConfig
from bale_personal_client.models import BaleSession
from bale_personal_client.wire import get_first, parse_fields
from bale_personal_client.ws import BaleWebSocket


def test_handshake_frame():
    ws = BaleWebSocket(BaleConfig(), BaleSession(access_token="x"))
    top = parse_fields(ws._handshake_frame())
    inner = parse_fields(get_first(top, 3))
    assert get_first(inner, 1) == 1
    assert get_first(inner, 2) == 151668


def test_rpc_and_ping_frames():
    raw = BaleWebSocket._rpc_frame("svc", "Method", b"payload", 9)
    inner = parse_fields(get_first(parse_fields(raw), 1))
    assert get_first(inner, 1) == b"svc"
    assert get_first(inner, 2) == b"Method"
    assert get_first(inner, 3) == b"payload"
    assert get_first(inner, 5) == 9

    ping = parse_fields(get_first(parse_fields(BaleWebSocket._ping_frame(4)), 2))
    assert get_first(ping, 1) == 4
