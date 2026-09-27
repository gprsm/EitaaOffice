# Education System API Contract

**Version:** 1.4.0
**Date:** 2026-09-27
**Status:** Design/Implementation (offline-tested; NOT live-accepted)

F-085, F-090 and F-091 review items are implemented and offline-tested
(V-217, V-222, V-224). Live acceptance is a separate gate.

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
- A credential carries explicit fences only: `allowed_providers` (non-empty
  subset of the registered provider catalog), `allowed_messenger_account_ids`
  (non-empty list of accounts that exist at issuance) and `scopes`
  (`messages.send`, `messages.status`, `contacts.resolve`, `agent.chat`).
  Missing, empty or unknown fence values are rejected at issuance — omitting
  a fence never grants unlimited access, and accounts created later stay
  inaccessible unless re-issued. Legacy credential rows without an explicit
  account list fail closed at use. Revocation and rotation take effect
  immediately; the acting role is the least-privileged `user`.

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
Requires the dedicated `messages.status` scope. A receipt is visible only to
the service credential that produced it; unknown keys, other services'
receipts and legacy owner-less receipts (created before service binding)
all answer `not_found` — ownership is never guessed.
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
  those accounts. Keep idempotency keys service-unique; cross-service reuse
  of a key is rejected as an owner mismatch instead of replayed.

### 4. `POST /api/v2/m2m/agent/chat`
**Request Body:**
```json
{
  "web_user_id": "<site user id>",
  "session_id": "<chat session id>",
  "message": "Ping",
  "message_id": "msg-00000001"
}
```
**Response (Success):**
```json
{
  "ok": true,
  "response": "Pong",
  "session_id": "…",
  "is_test_response": true,
  "replayed": false
}
```
- Requires the `agent.chat` scope. The web user identity, the chat session,
  the AppUser session and the provider session are distinct concepts and are
  never merged into one identifier.
- `message_id` (8–128 chars of `[A-Za-z0-9._:-]`) is required and bound to
  the request content. Retrying the same id with the same text inside the
  session window returns the stored reply with `replayed: true`; reusing the
  id with different text is rejected with `409 agent_message_id_conflict`;
  a different id is a new message.
- First-run/replay is decided atomically per
  (service, web user, session, message_id) inside one backend process:
  racing requests wait for the first adapter attempt (bounded wait, 30s by
  default). If the first attempt is still running when the wait expires the
  waiter gets `503 agent_reply_pending`; if it failed, waiters receive the
  same failure; if it was cancelled, waiters get
  `agent_first_attempt_cancelled`. **Scope of the guarantee:** the reply
  cache is in-memory and per-process — after a backend restart, or across
  multiple backend processes, the same message id may run the adapter again.
  No exactly-once execution is claimed beyond this process boundary.
- The claim stays owned until the reply is fully stored or explicitly failed
  (F-091). The user message, the agent message and the replayable reply
  record are stored atomically: other requests observe the full exchange or
  nothing. If storing fails after the adapter answered — for example the
  session expired while the adapter ran and the per-service session capacity
  is exhausted — the partial state is rolled back, the first request gets
  the real failure (e.g. `400 agent_too_many_sessions`), racing waiters
  receive the same error code, nothing half-recorded remains in the history
  or the reply cache, and a later retry with the same message id takes a
  fresh claim (the adapter may run again; see the retry policy above).
  Unknown internal save failures give the first request
  `500 internal_error` and waiters `400 agent_reply_not_stored`; both leave
  the claim resolved, never pending.
- Conversation continuation is real: the adapter receives the bounded prior
  conversation (last 20 turns) of exactly this (service, web user, session);
  other services and users never see it. Session expiry (one hour of
  inactivity) is enforced on every read — expired history and replies are
  erased before any read and never reach the adapter.
- A cached reply keeps its own `is_test_response` flag and text; replay
  returns exactly what was stored, regardless of which adapter is currently
  configured.
- Adapter failures surface as `502 agent_communication_failed`; timeouts and
  outages are upstream failures, not client errors. **Retry policy:** the
  bridge never auto-retries a failed attempt. After a failure it is unknown
  whether the request reached the agent; retrying with the same message id
  will run the adapter again as an explicit caller decision, while a new
  message id is always a new message. Never assume a same-id retry is
  side-effect-free.
- The adapter is wired only from an explicit `bridge.json` `agent_gateway`
  section (`enabled`, `url`, `model`, `api_key_env` naming a set environment
  variable). Nothing is guessed; an invalid section fails startup. Until a
  real adapter is configured and live-accepted, the test adapter answers and
  every response carries `is_test_response: true`; consumers must not present
  it as a real agent answer. Message size (≤ 4096 chars), per-service session
  cap (100), session TTL (1 hour) and context window (20 messages) are
  enforced. The agent surface is chat-only: it cannot send messenger
  messages, execute commands or read user data.

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
5. **Agent config**: a real agent adapter requires explicit configuration —
   `enabled`, `url`, `model` and `api_key_env` naming a set environment
   variable. External endpoints must use HTTPS; plain HTTP is accepted only
   for loopback hosts (`127.0.0.1`, `::1`, `localhost`) as an explicit
   same-host exception. An invalid configuration fails startup; without
   configuration every chat response is marked `is_test_response: true`.
