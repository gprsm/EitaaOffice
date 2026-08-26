# Protocol Notes and Confidence Matrix

This implementation is original. Public projects and prior traffic captures were used only as independent observations.

## High-confidence observations

- Authentication calls use gRPC-Web framing over `https://next-ws.bale.ai/<service>/<method>`.
- `ValidateCode` yields a JWT that is exchanged at `/set-cookie/`; the resulting HttpOnly `access_token` authenticates WebSocket.
- WebSocket endpoint is `wss://next-ws.bale.ai/ws/` with Bale Web Origin and the access-token cookie.
- Handshake envelope: outer field 3; inner field 1 protocol version and inner field 2 API version.
- Current reference values used by this build: protocol 1, API 151668.
- RPC envelope: outer field 1; service=1, method=2, payload=3, request ID=5.
- Ping envelope: outer field 2.
- Incoming top-level fields observed: RPC/push=1, push container=2, terminate=3, pong=4, handshake=5.
- `SubscribeToUpdates` can terminate periodically and should be reissued without rebuilding the whole session.

## Medium-confidence typed helpers

- `LoadHistory`: peer=1, offset date=2, load mode=4, limit=5.
- `SendMessage`: peer=1, random ID=2, content=3, extended peer=6.
- Text content: content field 15 containing a nested message with text field 1.
- Document content: content field 4 with file ID/access hash/size/name/MIME and caption wrapper.
- `UpdateMessage`, `DeleteMessage`, presence methods and contact request layouts.

These helpers have a raw-RPC escape hatch. If a server response disagrees, capture request/response bytes and patch only `codecs.py`.

## Lower-confidence / version-sensitive areas

- Exact `ValidatePassword` and `SignUp` request/response wrappers.
- Fully typed `LoadDialogs` response.
- Fully typed User/Contact response records.
- Some file-upload responses may not expose access hash in the same field across versions.
- Service/method catalog is broader than the set of typed wrappers and may drift.

## Debugging order

1. Confirm `/set-cookie/` issued `access_token`.
2. Confirm the cookie—not the OTP JWT—is sent to WebSocket.
3. Capture the first outbound and inbound WebSocket frames.
4. Compare server proto/API versions with `config.py`.
5. Run `SubscribeToUpdates` only after successful handshake.
6. For an RPC error, retain service, method, request hex, response/error code and current web-client capture.
