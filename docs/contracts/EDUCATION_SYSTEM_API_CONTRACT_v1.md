# Education System API Contract

**Version:** 1.8.0
**Date:** 2026-09-29
**Status:** Design/Implementation (offline-tested; NOT live-accepted)

F-085, F-090 and F-091 review items are implemented and offline-tested
(V-217, V-222, V-224, V-225). Live acceptance is a separate gate.
1.5.0 adds per-service, per-intent sender profiles (P1) with server-side
enforcement; the legacy explicit-account contract is preserved unchanged.
1.6.0 adds the read-only delivery preflight (P2) and wires the same local
execution policy into real send admission.
1.7.0 adds durable, atomic delivery capacity reservations (P3) in the
coordinator store; a reservation fixes local admission accounting only and
never promises provider capacity or delivery.
1.8.0 adds the composite OTP delivery pipeline (P4) with durable state tracking,
automatic contact import if missing, capacity reservation verification and
zero raw OTP/phone data exposure.

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
  (`messages.send`, `messages.status`, `contacts.resolve`, `otp.deliver`, `agent.chat`).
  Missing, empty or unknown fence values are rejected at issuance — omitting
  a fence never grants unlimited access, and accounts created later stay
  inaccessible unless re-issued. Legacy credential rows without an explicit
  account list fail closed at use. Revocation and rotation take effect
  immediately; the acting role is the least-privileged `user`.

## Operations

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

#### 1a. Sender selection with sender profiles (1.5.0)

The request body may use sender profiles instead of naming an account:

```json
{
  "sender_profile_id": "<uuid>",
  "intent": "otp",
  "peer_reference": {"kind": "dialog", "value": "user:123456"},
  "text": "123456",
  "confirm": true
}
```

- `intent` accepts `otp` or `notification` and maps to the legacy
  `message_type` values `otp`/`notice`. When `intent` is present it is
  authoritative; otherwise `message_type` keeps its documented meaning.
- `sender_profile_id` is optional. When given, it must reference an enabled
  profile of the calling credential; the bridge routes the send to the
  account pinned by that profile. A `messenger_account_id` in the same
  request must equal the pinned account (`409 sender_profile_mismatch`
  otherwise).
- **Migration policy (legacy `messenger_account_id`):** requests that name an
  explicit account keep working exactly as before, within the credential
  account/provider fences. Once an enabled profile is configured for the
  request's intent, a different explicit `messenger_account_id` is rejected
  with `409 sender_profile_mismatch` — an account id is never a bypass route.
- A request with neither `sender_profile_id` nor `messenger_account_id` is
  rejected with `400 sender_not_configured`. No default sender exists: being
  first in a list or most recently used never makes an account the sender.
- Pinned-account failures: if the pinned account is missing, archived,
  disabled, quarantined, or its phone account is disabled/archived, the send
  is refused with `409 account_unavailable` (snapshot; the provider may still
  refuse later). A disabled or foreign profile answers
  `400 sender_not_configured`.
- Errors: `sender_not_configured` (400), `account_unavailable` (409),
  `sender_profile_mismatch` (409), `m2m_sender_intent_invalid` (400).
  Provider refusal after admission still follows the delivery-status rules
  below; a profile snapshot never guarantees provider success.

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

#### 1b. Account-scoped compatibility route

`POST /api/v2/m2m/messenger-accounts/<messenger_account_id>/messages/send-text`
is a compatibility alias of the canonical send route above: the account is
taken from the path, `message_type` defaults to `notice`, and a missing
`idempotency_key` is derived from the `X-Request-Id` header. Everything else —
the `confirm: true` requirement, scope, account/provider fences and durable
idempotency — is identical to the canonical route; a request that omits
`confirm` is rejected with `400 m2m_confirm_required` exactly like the
canonical route.

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
- The claim stays registered and owned until the reply is fully stored or
  explicitly failed (F-091); it is not removed during the lock-protected
  exchange transaction. The user message, the agent message and the
  replayable reply record are stored atomically: other requests observe the
  full exchange or nothing. If storing fails after the adapter answered — for
  example the session expired while the adapter ran and the per-service session capacity
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

## Delivery preflight (1.6.0)

`POST /api/v2/m2m/delivery/preflight` requires `messages.send` and answers,
read-only, whether the bridge is locally ready to attempt a new delivery
for the pinned sender — before any OTP flow starts.

**Request:**
```json
{
  "sender_profile_id": "<uuid>",
  "intent": "otp",
  "recipient_kind": "existing"
}
```
- `intent` is `otp` | `notification`; `recipient_kind` is `existing` |
  `new`. No phone number or recipient identity is needed for the snapshot.
  The legacy explicit `messenger_account_id` is accepted under the same
  fences as send-text; once a profile pins the intent it must match.
- **Read-only guarantee:** the endpoint never resolves, imports, sends,
  reserves, acquires a token, performs a worker RPC or changes the circuit.
  Repeated reads are stable; nothing appears in `account_execution_limits`
  because of a preflight.

**Response:**
```json
{
  "ok": true,
  "decision": "ready",
  "can_attempt": true,
  "retry_after_seconds": null,
  "sender_profile_revision": 2,
  "observed_at": "2026-09-28T12:00:00.000Z",
  "valid_until": "2026-09-28T12:00:05.000Z",
  "steps": ["resolve", "send"],
  "constraints": [
    {"scope": "account", "operation": "messages.send_text",
     "source": "local_policy", "certainty": "assumed",
     "reason": null, "retry_after_seconds": null, "updated_at": "..."}
  ],
  "capacity_guaranteed": false
}
```
- `decision` is `ready` | `wait` | `unavailable` | `unsupported` | `unknown`.
  `ready` means an attempt is allowed by all locally known policy — it never
  guarantees provider capacity or acceptance (`capacity_guaranteed` is
  always `false`). A preflight that answered `ready` and a later refused
  send are both explainable: the real send re-acquires atomically and the
  provider can still refuse.
- The three limits stay separate and are reported as constraints:
  `credential_quota` (per-credential HTTP request window; status polling
  counts here and is never mistaken for messages), `local_policy`
  (account+operation token bucket and circuit) and `provider_observed`
  (cooldown learned from the provider, e.g. flood-wait). Absence of a
  cooldown means only "nothing observed", never "quota is unlimited"; a
  never-exercised account reports a `local_policy` constraint with
  `certainty: "assumed"`.
- `retry_after_seconds` is the ceiling (not the optimistic minimum) across
  the blockers on this path, rounded up to whole seconds. `steps` lists the
  operations the recipient path still needs (`existing`: resolve → send;
  `new`: prepare_contact → resolve → send).
- HTTP mapping: a valid inspection may answer `200` with `decision: wait`;
  a genuinely unavailable pinned account answers `503`; an unauthorized
  account/service answers `403` and receives no constraint details; an
  exhausted request quota refuses the request itself with `429` and a
  `Retry-After` header. `unsupported` (unknown recipient kind) is `200`
  with `can_attempt: false`.
- **Real-send enforcement (P2):** the same `AccountExecutionPolicyService`
  instance that the preflight snapshots gates every fresh mutation attempt
  in the orchestrator (atomic `acquire` before the provider call; success /
  failure / circuit recorded afterwards). A successful replay never
  consumes a token — with an empty local bucket a replay of an already
  completed key still replays. Admission denial surfaces as
  `429 provider_operation_rate_limited` (or `503
  provider_operation_circuit_open`) with a ceiling-rounded `Retry-After`
  header; refusals happen before the provider is contacted. There is no
  documented public rate limit for Eitaa/Bale in this system: local policy
  values are configuration, not provider facts, and are never presented as
  such.

## Delivery reservations (1.7.0)

A reservation pins one short-lived local capacity slot to a sender and a
recipient binding so two racing requests cannot both take the last slot.
Capacity decision, bucket debit and the row insert are ONE SQLite
transaction (`BEGIN IMMEDIATE`) in the coordinator store — atomic across
connections and processes, with no await/worker/network inside. A
reservation is local admission accounting only: it never promises provider
capacity, provider acceptance or message delivery, and `ready`/reserved is
not a capacity guarantee.

### `POST /api/v2/m2m/delivery/reservations` — create (scope `messages.send`)

```json
{
  "sender_profile_id": "<uuid>",
  "intent": "otp",
  "recipient": {"kind": "phone", "value": "+989120000001"},
  "idempotency_key": "res-key-000000000001",
  "ttl_seconds": 120
}
```
- The recipient is a canonical E.164 phone and is ONLY stored as an
  HMAC-SHA256 binding under the server identity key over
  (intent, service, phone) — a bare phone hash is searchable in reverse
  and is never used. The raw value and any OTP never touch this table,
  logs, receipts or reports.
- `ttl_seconds` defaults to 120; bounds are 30–600.
- Idempotency: the key is scoped to the credential. Retrying the same key
  with the same payload returns the SAME reservation record (whatever its
  state — a terminal record is replayed, never revived). Reusing the key
  with a different payload answers `409 delivery_reservation_conflict`.
- Response `201`: `{ok, reservation: {id, state, provider,
  messenger_account_id, sender_profile_id, sender_profile_revision,
  operation_costs, token_reserved, token_refunded, send_started,
  operation_id, created_at, updated_at, expires_at}}`.
- Refusals before any insert: `429 delivery_reservation_capacity_unavailable`
  (+ `Retry-After`, refill-based), `429 delivery_reservation_outstanding_limit`
  (max 4 outstanding per credential), `429 delivery_reservation_rate_limited`
  (max 12 creates/minute/credential), `503 delivery_reservation_circuit_open`,
  `400 delivery_reservation_ttl_invalid`, `400 m2m_phone_invalid`,
  `400 delivery_recipient_unsupported`, `403 m2m_account_not_allowed` /
  `m2m_provider_not_allowed` / `m2m_scope_insufficient` (fences as in
  send-text; an unauthorized caller learns no constraint details).

### `GET /api/v2/m2m/delivery/reservations/{id}` — status

Owner-only (the calling credential): foreign or unknown ids answer
`404 delivery_reservation_not_found` with no details. Lazy expiry runs on
every read with the same atomic transition as the janitor.

### `POST /api/v2/m2m/delivery/reservations/{id}/cancel` — cancel

Owner-only and idempotent. Only a certain-not-started slot refunds its
token (bounded by bucket capacity, exactly once). A cancelled reservation
is never revived.

### State machine and accounting

- `reserved → consumed | cancelled | expired`; terminal states are final
  and never return to `reserved`. Expiry (lazy or janitor) is the same
  atomic transition and refunds the slot once.
- `consume` (internal, used by the delivery pipeline in a later phase)
  attaches ONE durable `operation_id` (UNIQUE). Repeating the same
  operation id returns the consumed record without a second debit; a
  different operation id is `409 delivery_reservation_already_consumed`.
  Consumption re-checks the account lifecycle (`409 account_unavailable`)
  and the pinned profile revision: a changed revision answers
  `409 sender_profile_revision_changed` and the caller reserves fresh —
  the pinned account is never switched silently.
- `send_started` is recorded when the provider RPC begins; from that point
  a refund is forbidden even if the outcome is later uncertain — timeout
  is not a refund.
- The debit uses the SAME account bucket as preflight and send admission
  (`messages.send_text`): a legacy unreserved send can never take a slot a
  reservation already debited, and cancelling/expiring frees it again.
- Records persist across restarts; rows are never deleted (retention is a
  metadata concern for a later phase). `operation_id` is unique per
  reservation and durable.

## OTP Delivery Pipeline (1.8.0)

`POST /api/v2/m2m/otp/deliveries` requires `otp.deliver` (or `messages.send`) scope.
Coordinates admission, contact resolution, auto-import if missing, and message dispatch
using a pre-acquired capacity reservation.

### `POST /api/v2/m2m/otp/deliveries` — dispatch
**Request Body:**
```json
{
  "idempotency_key": "otp-delivery-key-0000000001",
  "reservation_id": "<uuid>",
  "phone": "+989120000001",
  "text": "Your verification code is: 123456",
  "contact_name": "Applicant",
  "challenge_reference": "chal-00000001"
}
```
- `phone` must match the `recipient_binding` HMAC stored in the reservation.
- `reservation_id` must be in `reserved` state and belonging to the calling service credential.
- `challenge_reference` is an opaque identifier for correlation; neither phone nor raw OTP text is stored in SQLite or logs.
- Steps:
  1. Validate reservation & verify HMAC binding match (`400 delivery_reservation_recipient_mismatch` if mismatched).
  2. Resolve recipient contact via provider.
  3. If unmapped/not found, import contact (`contacts.import` / `contacts.upsert`) to obtain a dialog peer.
  4. Consume capacity reservation with durable `operation_id`.
  5. Dispatch text to provider.
  6. Return delivery status record.

### `GET /api/v2/m2m/otp/deliveries/{id}` — poll status
Owner-only; returns the current status (`accepted`, `provider_succeeded`, `uncertain`, `failed`, `rejected`), provider reference, and timestamps.

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
  (`application/bale_client`) ships with the product and its adapter, worker,
  and multi-provider onboarding are offline contract-verified (`CONTRACT_VERIFIED`,
  `runtime_enabled=True`, `onboarding_enabled=True`). M2M recipient prepare and
  resolve endpoints support Bale references (`bale:user:<id>`); live send
  acceptance remains subject to instant operator permission.
- **Agent**: the test adapter returns a fixed marked response; a real adapter
  requires explicit configuration (vendor, URL, credential) that must not be
  guessed.

## Configuration Guide

### Bale recipient preparation (additive product route, 2026-09-28)

`POST /api/v2/m2m/recipients/prepare` requires `contacts.import`, the bound
account/provider, active membership and the account's `contacts.write` capability.
Body fields: `messenger_account_id`, `provider`, canonical E.164 `phone`,
`display_name`, `idempotency_key`, and `confirm: true`. It performs a named
contact upsert and returns the actual matched account-owned peer. Unresolved
or ambiguous matches fail; no peer is fabricated from a raw phone number.
Existing contacts keep their names. Durable receipts bind actor, credential,
account and payload; uncertain effects are not retried automatically.

`recipients/resolve` stays read-only and requires `contacts.resolve`; import
is never an implicit fallback. `messages/send-text` accepts a private typed
`bale:user:<id>` reference and requires `messages.send`. A successful
`bale:submission:<id>` means provider acceptance, not a delivered message ID
or human read receipt. OTP generation, validation and reservation remain
outside these primitives. These routes are offline verified; Live is pending.

Main-app contact removal and media send are additive account-scoped routes
with capability, confirmation and durable idempotency checks. Media transfer
is limited to 512 KiB and opaque account-owned download handles; filesystem
paths, access hashes and vault secrets never reach the caller.

### Service configuration

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

### Sender profiles (admin configuration, 1.5.0)

Sender profiles are managed by an administrator (AppUser session + CSRF) and
are never reachable with the M2M token:

- `GET /api/v2/service-sender-profiles` — lists all profiles with their
  `revision` and an `account_available` snapshot.
- `PUT /api/v2/service-sender-profiles` — create or update the profile for
  one `(service_credential_id, intent)` pair. Body:
  `service_credential_id`, `intent` (`otp` | `notification`), `provider`,
  `messenger_account_id`, `enabled` (bool), `expected_revision`
  (integer ≥ 1, absent/null only for first-time creation). Returns the
  stored profile with its new `revision`.
- `DELETE /api/v2/service-sender-profiles/{id}` — removes a profile.
- Fence rules (enforced server-side, mirrored in the UI but never trusted
  from it): the intent must be `otp`/`notification`; the provider must exist
  in the provider catalog and be inside the credential's
  `allowed_providers`; the account must exist, belong to the chosen provider
  and be inside the credential's `allowed_messenger_account_ids`. Violations
  answer `400` with `sender_profile_intent_invalid`,
  `sender_profile_enabled_invalid`, `sender_profile_revision_invalid`,
  `sender_profile_credential_unknown`, `sender_profile_provider_unknown`,
  `sender_profile_provider_mismatch`, `m2m_provider_not_allowed`,
  `m2m_account_not_allowed` or `sender_profile_fields_rejected`.
- **Revision control:** every update must carry `expected_revision`. On a
  mismatch the write is refused with `409 stale_revision`; readers re-read
  and retry explicitly. First creation uses no `expected_revision`; updates
  require the current one. Writes are atomic and serialized (`BEGIN
  IMMEDIATE`); two racing edits with the same revision produce exactly one
  winner.
- **Lifecycle:** a profile row is never re-bound silently. When the pinned
  account is removed, archived, disabled or quarantined, the profile stays
  but resolves to `409 account_unavailable` at send time and
  `account_available: false` in the admin list; revoking the credential
  makes every profile of it unusable. Deleting the profile is an explicit
  admin action.
- Synthetic example (fixture): credential `service-a` allowed
  `provider=eitaa`, account `A1`; `PUT` pins `(service-a, otp)` →
  `account=A`; an M2M request with `{"sender_profile_id": …, "intent":
  "otp"}` routes to `A`; a request with `{"intent": "otp",
  "messenger_account_id": other-account}` answers `409 sender_profile_mismatch`.
