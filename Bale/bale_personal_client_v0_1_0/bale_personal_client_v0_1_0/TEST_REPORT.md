# Offline Test Report

Generated for v0.1.0.

Command:

```text
python -m pytest -q
```

Result:

```text
9 passed
```

Covered areas:

- Protobuf varint, text, nested messages and repeated fields
- JSON field-spec encoder
- gRPC-Web data/trailer framing
- Peer and SendMessage request shape
- LoadHistory request and text-message decoder
- WebSocket handshake, RPC and ping envelope shape
- AES-GCM/Scrypt session-vault round trip and plaintext leakage check
- JWT-to-access-token cookie exchange using a mocked HTTP transport

Not covered in this environment:

- Live OTP delivery
- Live `/set-cookie/` exchange against Bale
- Live WebSocket handshake
- Server-specific response variants
- Sending/modifying/deleting real messages
- Upload/download integration

Those tests require the user's authorized secondary account and should be run in the sequence documented in README_FA.md.
