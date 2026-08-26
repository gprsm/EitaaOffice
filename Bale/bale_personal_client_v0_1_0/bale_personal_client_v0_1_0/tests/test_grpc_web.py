from bale_personal_client.grpc_web import frame_grpc_web, unframe_grpc_web


def test_grpc_web_framing_and_trailers():
    payload = b"abc"
    trailers = b"grpc-status: 0\r\ngrpc-message: \r\n"
    framed = frame_grpc_web(payload) + bytes([0x80]) + len(trailers).to_bytes(4, "big") + trailers
    payloads, parsed = unframe_grpc_web(framed)
    assert payloads == [payload]
    assert parsed["grpc-status"] == "0"
