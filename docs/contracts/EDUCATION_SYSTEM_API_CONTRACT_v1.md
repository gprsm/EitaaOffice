# Education System API Contract

**Version:** 1.1.0
**Date:** 2026-09-27
**Status:** Design/Implementation under security review (offline-tested; NOT live-accepted)

**Open review finding:** F-085. Do not treat this version as a production
authorization or chat-continuity contract until its account, receipt and chat
ownership issues are resolved.

## Data Ownership Boundaries

| Data | Owner | Notes |
|---|---|---|
| Web user identity, OTP, confirmation | Education System | |
| Operator permissions, web session | Education System | |
| Notification text & recipients | Education System | |
| M2M token validation | Eitaa Bridge | |
| Sender account selection | Eitaa Bridge | |
| Recipient resolution in messenger | Eitaa Bridge | Read-only; never writes contacts. |
| Message delivery execution | Eitaa Bridge | Via the provider-neutral orchestrator only. |
| Provider delivery receipt | Eitaa Bridge | Only what the provider actually reports. |
| Agent gateway | Eitaa Bridge | Test adapter until a real one is configured. |

## Authentication

- All `/api/v2/m2m/*` endpoints require `Authorization: Bearer eb_svc_…`.
  The token is issued by an admin via `/api/v2/service-credentials`, stored
  server-side only as a PBKDF2-HMAC-SHA256 hash, and is independent of
  AppUser sessions/CSRF.
- Every request must carry `X-Request-Id`. Bodies are limited to 64 KB.
- Per-credential rate limit: 60 requests/minute. Repeated invalid tokens are
  throttled globally (fail-closed anti-DoS guard).
- A credential is scoped to `allowed_providers`,
  `allowed_messenger_account_ids` (nullable = unrestricted) and `scopes`
  (`messages.send`, `contacts.resolve`, `agent.chat`). Revocation and rotation
  take effect immediately; the acting role is the least-privileged `user`.

## Operations

### 1. `POST /api/v2/m2m/messages/send-text`
**Headers:**
- `Authorization`: Bearer `<M2M_TOKEN>`
- `X-Request-Id`: `<UUID>`
- `Content-Type`: application/json

**Request Body:**
```json
{
  "idempotency_key": "msg_234234234",
  "messenger_account_id": "<uuid>",
  "message_type": "notice",
  "peer_reference": {"kind": "dialog", "value": "user:123456"},
  "text": "Hello world",
  "confirm": true
}
```
- `message_type`: `otp` (text ≤ 256 chars) or `notice` (text ≤ 4096 chars).
- `confirm` must be `true`.
- `peer_reference.kind` accepts only `dialog` with the opaque dialog key
  (`<user|chat|channel>:<id>`) returned by the resolve operation. Raw phone
  numbers/usernames are rejected with `409 m2m_recipient_unresolved` — they
  are never used as peer references.
- `idempotency_key`: 16–128 chars of `[A-Za-z0-9._:-]`. Retries of the same
  logical message must reuse the same key.

**Response (Success):**
```json
{
  "ok": true,
  "request_id": "…",
  "delivery_status": "provider_succeeded",
  "message_reference": "…",
  "safe_reason_code": "…"
}
```

### 2. `POST /api/v2/m2m/recipients/resolve`
**Request Body:**
```json
{
  "messenger_account_id": "<uuid>",
  "recipients": [{"kind": "phone", "value": "+989123456789"}]
}
```
- Read-only lookup in the shared contact directory plus the sender account's
  dialog catalog. No contact import or data change happens here; if an import
  is needed it is a separate, separately-authorized operation (not exposed via
  M2M).
- Values are echoed back only as SHA-256 `value_hash`; raw phone numbers are
  never returned.
- `status: "resolved"` means the dialog is send-ready and `peer_reference` can
  be passed to send-text. `unresolved` (+`requires_import: true`) means the
  bridge will not attempt delivery. `unsupported` covers kinds the bridge
  cannot look up (or worker-process mode where the catalog is unavailable).

**Response (Success):**
```json
{
  "ok": true,
  "results": [
    {"kind": "phone", "value_hash": "…", "status": "resolved",
     "peer_reference": "user:123456", "reason": null}
  ],
  "requires_import": false
}
```

### 3. `GET /api/v2/m2m/messages/{idempotency_key}/status`
**Response (Success):**
```json
{
  "ok": true,
  "delivery_status": "provider_succeeded",
  "message_reference": "…",
  "timestamp": "…"
}
```
- When the credential restricts messenger accounts, lookups are fenced to
  those accounts. Known limitation: the receipt store keys by
  `idempotency_key` only; keep keys service-unique.

### 4. `POST /api/v2/m2m/agent/chat`
**Request Body:**
```json
{
  "web_user_id": "<site user id>",
  "session_id": "<chat session id>",
  "message": "Ping"
}
```
**Response (Success):**
```json
{
  "ok": true,
  "response": "Pong",
  "session_id": "…",
  "is_test_response": true
}
```
- Requires the `agent.chat` scope. The web user identity, the chat session,
  the AppUser session and the provider session are distinct concepts and are
  never merged into one identifier.
- Until a real agent adapter is configured, the test adapter answers and every
  response carries `is_test_response: true`; consumers must not present it as
  a real agent answer. Message size (≤ 4096 chars), per-service session cap
  (100), session TTL (1 hour) and context window (20 messages) are enforced.

### 5. `GET /api/v2/m2m/agent/health`
**Response (Success):**
```json
{"ok": true, "agent_available": true, "adapter_type": "test"}
```

## Delivery Status Definitions
- `accepted` — Bridge received the request and delivery is in progress
- `provider_succeeded` — Provider reported success (not guaranteed delivery to the person)
- `uncertain` — Provider did not confirm; DO NOT auto-retry
- `not_found` — No receipt for this idempotency key
- `rejected` (HTTP 4xx) — Request validation failed; safe to fix and retry
- `unresolved` — Recipient not found / not send-ready in messenger
- `unsupported` — Recipient kind not supported by the provider or mode

## Retry Rules
- `rejected`: Fix request and retry with the SAME idempotency_key
- `uncertain`: Do NOT auto-retry. Requires manual investigation / a safety witness.
- `provider_succeeded`: No retry needed
- The idempotency key must be preserved across retries
- Different idempotency_key = different message (will send again)

## Provider Limitations
- **Eitaa**: send-text accepts only dialog references produced by resolve.
  Resolve is a read-only lookup in the account's dialog catalog backed by the
  shared contact directory; a contact without an active dialog stays
  `unresolved`. Contact import is a separate operation, not part of M2M.
- **Bale Bot** (`providers/bale_bot`, official Bot API only): scaffold,
  not registered in the provider registry — fail-closed until the owner
  supplies the official bot documentation/token and live gates pass.
  The Bot API cannot resolve phone numbers; it can only message users who
  already started a conversation with the bot.
- **Bale Personal** (owner decision F-086/ADR-60, 2026-09-27): authorized as
  a first-class product path alongside the bot. The client
  (`application/bale_client`) ships with the product and its adapter is
  offline contract-verified; provider-side send over the orchestrator is not
  live-accepted yet and multi-provider onboarding/worker wiring is the next
  authorized phase (`provider_onboarding_wiring_pending`). Personal Bale
  delivery today runs through the Bale-branch v1 surface (session ops
  live-accepted, V-194).
- **Agent**: the test adapter returns a fixed marked response; a real adapter
  requires explicit configuration (vendor, URL, credential) that must not be
  guessed.

## Configuration Guide
1. **Create a service credential**: In the Settings panel, create a credential;
   the token is shown ONCE and never stored in plaintext.
2. **Assign accounts/scopes**: bound to specific messenger accounts and scopes.
3. **Rotate**: invalidates the old token immediately and issues a new one.
4. **Revoke**: disables the credential immediately.
5. **Agent config**: a real agent adapter requires explicit configuration;
   until then every chat response is marked `is_test_response: true`.

## Open Implementation Gaps (F-085)

- A credential created with no selected messenger accounts currently has an
  unrestricted account list. The service authorization path does not perform
  an AppUser membership check. Issue only explicitly account-bound credentials
  while this boundary is being corrected.
- Receipt status is not bound to a service identity and currently lacks a
  scope check. Do not share status keys across services or rely on this route
  for service-isolated receipt access.
- Chat has no `message_id` or replay protection. Stored message history is not
  passed to the agent adapter, and the configurable adapter is not wired into
  runtime configuration. Chat continuity and live agent connection are pending.
- The per-request service authorization context requires explicit reset;
  a same-context request sequence has not been regression tested.
