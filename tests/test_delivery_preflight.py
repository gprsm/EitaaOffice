"""P2 delivery preflight and real rate-policy enforcement tests.

Every fixture is synthetic and offline; nothing touches bridge.json,
operational data or any live provider. The tests assert a read-only
preflight with honest constraint sources and times, zero side effects
(no acquire, no worker RPC, no contact write, no circuit change), the
same policy enforced on the real send path (no hand-made bypass), honest
unavailability, per-account isolation and no token consumption on replay.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

import eitaa_bridge.application.api as api_module
from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.application.m2m_api import dispatch_m2m
from eitaa_bridge.infrastructure.coordinator import (
    CoordinatorAppAuth,
    CoordinatorDatabase,
    ProtectedPhone,
    StaticSubjectFingerprinter,
)
from eitaa_bridge.infrastructure.coordinator.rate_policy import (
    AccountExecutionPolicyService,
    ClassifiedFailure,
    ExecutionErrorClass,
    classify_failure,
)
from eitaa_bridge.providers.contracts import (
    ProviderCapability,
    ProviderContactMutationReceipt,
    ProviderSendReceipt,
    ProviderSendStatus,
)

_PREFLIGHT_ROUTE = "/api/v2/m2m/delivery/preflight"
_SEND_ROUTE = "/api/v2/m2m/messages/send-text"
_BASE_TIME = datetime(2026, 9, 28, 12, 0, 0, tzinfo=timezone.utc)


def _prepared_api(config_file: Path, monkeypatch) -> tuple[BridgeApplicationApi, str]:
    payload = json.loads(config_file.read_text(encoding="utf-8"))
    payload["features"] = {
        "multi_session": {"enabled": True},
        "app_user_auth": {
            "enabled": True,
            "self_registration_enabled": True,
            "idle_timeout_minutes": 525_600,
            "absolute_timeout_hours": 8_760,
            "max_failed_attempts": 5,
            "lockout_minutes": 15,
        },
    }
    config_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    database_path = config_file.parent / "data" / "coordinator" / "coordinator.sqlite3"
    account_summary = CoordinatorDatabase(database_path).bootstrap_legacy_account(
        protected_phone=ProtectedPhone(
            ciphertext=b"protected-phone",
            key_version=1,
            fingerprint="b" * 64,
            display_hint="+••••••••67",
        ),
        display_name="Initial administrator",
        backup_name="verified.zip",
        source_manifest_sha256="a" * 64,
        source_file_count=1,
        source_total_bytes=1,
    )
    auth = CoordinatorAppAuth(
        database_path,
        fingerprinter=StaticSubjectFingerprinter(b"preflight-test-subject"),
    )
    monkeypatch.setattr(
        api_module,
        "CoordinatorAppAuth",
        lambda _database_path, *, policy: auth,
    )
    api = BridgeApplicationApi(config_file)
    return api, account_summary.messenger_account_id


def _cookie_token(response) -> str:
    cookie = response.headers["Set-Cookie"]
    name, token = cookie.split(";", 1)[0].split("=", 1)
    assert name == "eitaa_bridge_app_session"
    return token


def _setup_admin(api: BridgeApplicationApi) -> tuple[str, str]:
    setup = api.dispatch(
        "POST",
        "/api/v2/app-auth/setup",
        body={
            "username": "local.admin",
            "password": "correct horse battery staple",
            "display_name": "مدیر آزمون",
        },
        client_kind="test",
    )
    assert setup.status == 201, setup.payload
    return _cookie_token(setup), setup.payload["csrf_token"]


def _onboard_account(api, token, csrf, *, provider, phone, label) -> str:
    response = api.dispatch(
        "POST",
        "/api/v2/messenger-accounts",
        body={"provider": provider, "phone": phone, "label": label},
        app_session_token=token,
        csrf_token=csrf,
    )
    assert response.status == 201, response.payload
    return response.payload["account"]["messenger_account_id"]


def _issue_credential(api, token, csrf, name, account_ids, providers, scopes=None) -> dict:
    response = api.dispatch(
        "POST",
        "/api/v2/service-credentials",
        body={
            "service_name": name,
            "description": "P2 preflight fixture",
            "allowed_providers": providers,
            "allowed_messenger_account_ids": account_ids,
            "scopes": scopes or ["messages.send", "messages.status"],
        },
        app_session_token=token,
        csrf_token=csrf,
    )
    assert response.status == 200, response.payload
    return response.payload


class FakeAuthContext:
    """A service token context for direct dispatch_m2m calls."""

    def __init__(self, scopes=None, allowed_accounts=None):
        self.scopes = list(scopes or ["messages.send", "messages.status"])
        self.allowed_messenger_account_ids = allowed_accounts
        self.allowed_providers = ["eitaa"]
        self.id = "00000000-0000-4000-8000-0000000000c1"
        self.credential_id = "cred-a"
        self.service_name = "exam-service"


class FailingOrchestrator:
    """Any mutation reaching the orchestrator during preflight fails the test."""

    def __init__(self) -> None:
        self.calls = 0

    async def send_text(self, **kwargs):
        self.calls += 1
        raise AssertionError("preflight must never reach the send path")

    async def upsert_contact(self, **kwargs):
        self.calls += 1
        raise AssertionError("preflight must never touch contacts")


class FakeEitaaAdapter:
    """Offline stand-in for the eitaa application adapter."""

    def __init__(self) -> None:
        self.calls = 0

    @property
    def manifest(self):
        return SimpleNamespace(
            provider="eitaa", capabilities={ProviderCapability.MESSAGES_SEND}
        )

    async def send_text(self, context, request):
        self.calls += 1
        return ProviderSendReceipt(
            ProviderSendStatus.SUCCEEDED,
            message_reference=f"synthetic-{self.calls}",
            safe_reason_code=None,
        )


async def _call_m2m(method, path, body, auth_ctx, coordinator, quota_reader=None):
    return await dispatch_m2m(
        method,
        path,
        body,
        auth_ctx,
        "req-1",
        None,
        coordinator,
        request_quota_reader=quota_reader,
    )


def _preflight(coordinator, auth_ctx, **overrides):
    body = {
        "intent": "otp",
        "recipient_kind": "existing",
        "messenger_account_id": overrides.pop("messenger_account_id", None),
    }
    body.update(overrides)
    return asyncio.run(_call_m2m("POST", _PREFLIGHT_ROUTE, body, auth_ctx, coordinator))


def _limit_count(api: BridgeApplicationApi) -> int:
    with sqlite3.connect(api._coordinator.path) as connection:
        return connection.execute(
            "SELECT COUNT(*) FROM account_execution_limits"
        ).fetchone()[0]


def _archive_account(api: BridgeApplicationApi, account_id: str) -> None:
    with sqlite3.connect(api._coordinator.path) as connection:
        connection.execute(
            "UPDATE messenger_accounts SET lifecycle_state='archived' WHERE id=?",
            (account_id,),
        )
        connection.commit()


@pytest.fixture()
def prepared(config_file, monkeypatch):
    api, account_id = _prepared_api(config_file, monkeypatch)
    return api, account_id


def test_composition_shares_one_policy_instance(prepared):
    api, account_id = prepared
    # Admission and outcome recording share one token owner across the
    # orchestrator and the persistent-job path.
    assert api._execution_policy is not None
    assert api._provider_orchestrator._execution_policy is api._execution_policy


def test_preflight_ready_is_read_only_and_repeatable(prepared):
    api, account_id = prepared
    guard = FailingOrchestrator()
    api._provider_orchestrator = guard
    auth_ctx = FakeAuthContext(allowed_accounts=[account_id])

    rows_before = _limit_count(api)
    first = _preflight(api._coordinator, auth_ctx, messenger_account_id=account_id)
    second = _preflight(api._coordinator, auth_ctx, messenger_account_id=account_id)

    assert first.status == second.status == 200
    assert first.payload["decision"] == "ready"
    assert first.payload["can_attempt"] is True
    assert first.payload["capacity_guaranteed"] is False
    assert first.payload["steps"] == ["resolve", "send"]
    assert first.payload["observed_at"] and first.payload["valid_until"]
    # No local limit row existed: reported as assumed, never as unlimited.
    assert any(
        constraint["source"] == "local_policy" and constraint["certainty"] == "assumed"
        for constraint in first.payload["constraints"]
    )
    # Repeated reads change nothing: same row count, same decision, and the
    # send path was never reached.
    assert second.payload["decision"] == "ready"
    assert _limit_count(api) == rows_before
    assert guard.calls == 0


def test_preflight_unsupported_recipient_kind(prepared):
    api, account_id = prepared
    auth_ctx = FakeAuthContext(allowed_accounts=[account_id])
    response = _preflight(
        api._coordinator,
        auth_ctx,
        messenger_account_id=account_id,
        recipient_kind="group",
    )
    assert response.status == 200
    assert response.payload["decision"] == "unsupported"
    assert response.payload["can_attempt"] is False


def test_policy_refill_cooldown_and_circuit_with_fake_clock(prepared):
    api, account_id = prepared
    policy = api._execution_policy

    # Five quick acquires drain the default bucket (capacity 5, refill 1/s).
    for index in range(5):
        permit = policy.acquire(
            messenger_account_id=account_id,
            operation_scope="messages.send_text",
            now=_BASE_TIME + timedelta(milliseconds=index),
        )
        assert permit.allowed, index
    drained = policy.acquire(
        messenger_account_id=account_id,
        operation_scope="messages.send_text",
        now=_BASE_TIME + timedelta(milliseconds=100),
    )
    assert drained.allowed is False
    assert drained.blocked_reason == "rate_limited"

    # The read-only snapshot recomputes refill to now without consuming:
    # two consecutive reads at the same instant return identical values and
    # no row mutation happens.
    snap = policy.read_only_snapshot(
        messenger_account_id=account_id,
        operation_scope="messages.send_text",
        now=_BASE_TIME + timedelta(seconds=2),
    )
    assert snap["blocked_reason"] is None
    again = policy.read_only_snapshot(
        messenger_account_id=account_id,
        operation_scope="messages.send_text",
        now=_BASE_TIME + timedelta(seconds=2),
    )
    assert again["available_tokens"] == snap["available_tokens"]

    # A provider cooldown longer than the local backoff wins the retry time.
    policy.record_failure(
        messenger_account_id=account_id,
        operation_scope="messages.send_text",
        failure=ClassifiedFailure(
            ExecutionErrorClass.TRANSIENT, "provider_flood_wait", 600_000
        ),
        now=_BASE_TIME,
    )
    later = policy.read_only_snapshot(
        messenger_account_id=account_id,
        operation_scope="messages.send_text",
        now=_BASE_TIME + timedelta(seconds=1),
    )
    assert later["blocked_reason"] == "retry_after"
    assert later["retry_after_ms"] >= 599_000


def test_circuit_opens_and_recovers_through_half_open(prepared):
    api, account_id = prepared
    policy = api._execution_policy
    for index in range(5):
        policy.record_failure(
            messenger_account_id=account_id,
            operation_scope="messages.send_text",
            failure=ClassifiedFailure(
                ExecutionErrorClass.TRANSIENT, "provider_busy", 5_000
            ),
            now=_BASE_TIME + timedelta(seconds=index),
        )
    opened = policy.read_only_snapshot(
        messenger_account_id=account_id,
        operation_scope="messages.send_text",
        now=_BASE_TIME + timedelta(seconds=5),
    )
    assert opened["blocked_reason"] == "circuit_open"

    # After the open window the circuit passes through half_open once.
    probe = policy.acquire(
        messenger_account_id=account_id,
        operation_scope="messages.send_text",
        now=_BASE_TIME + timedelta(seconds=35),
    )
    assert probe.circuit_state == "half_open"
    policy.record_success(
        messenger_account_id=account_id,
        operation_scope="messages.send_text",
        claim_id=probe.claim_id,
        now=_BASE_TIME + timedelta(seconds=36),
    )
    closed = policy.read_only_snapshot(
        messenger_account_id=account_id,
        operation_scope="messages.send_text",
        now=_BASE_TIME + timedelta(seconds=33),
    )
    assert closed["circuit_state"] == "closed"


def test_account_a_does_not_block_account_b(prepared):
    api, account_a = prepared
    token, csrf = _setup_admin(api)
    account_b = _onboard_account(
        api, token, csrf,
        provider="eitaa", phone="+989120000002", label="حساب دوم آزمون",
    )
    auth_ctx = FakeAuthContext(allowed_accounts=[account_a, account_b])

    for _ in range(5):
        permit = api._execution_policy.acquire(
            messenger_account_id=account_a,
            operation_scope="messages.send_text",
        )
        assert permit.allowed
    blocked_a = _preflight(api._coordinator, auth_ctx, messenger_account_id=account_a)
    assert blocked_a.payload["decision"] == "wait"
    assert any(
        constraint["reason"] == "rate_limited"
        and constraint["source"] == "local_policy"
        for constraint in blocked_a.payload["constraints"]
    )
    ready_b = _preflight(api._coordinator, auth_ctx, messenger_account_id=account_b)
    assert ready_b.payload["decision"] == "ready"


def test_preflight_unavailable_account_is_503(prepared):
    api, account_id = prepared
    auth_ctx = FakeAuthContext(allowed_accounts=[account_id])
    _archive_account(api, account_id)
    response = _preflight(api._coordinator, auth_ctx, messenger_account_id=account_id)
    assert response.status == 503
    assert response.payload["decision"] == "unavailable"
    assert response.payload["can_attempt"] is False


def test_unauthorized_account_learns_no_constraint_details(prepared):
    api, account_id = prepared
    auth_ctx = FakeAuthContext(allowed_accounts=["1" * 36])
    response = _preflight(api._coordinator, auth_ctx, messenger_account_id=account_id)
    assert response.status == 403
    assert "constraints" not in response.payload


def test_full_stack_send_enforcement_and_replay(prepared, monkeypatch):
    api, account_id = prepared
    token, csrf = _setup_admin(api)
    credential = _issue_credential(
        api, token, csrf, "preflight-service", [account_id], ["eitaa"]
    )
    svc_token = credential["token"]

    # Deterministic local capacity: refill effectively zero for the test.
    api._execution_policy = AccountExecutionPolicyService(
        api._coordinator, default_refill_per_second=1e-9
    )
    api._provider_orchestrator._execution_policy = api._execution_policy

    fake_adapter = FakeEitaaAdapter()
    api._provider_application_adapter_factories["eitaa"] = lambda account: fake_adapter

    def _m2m_send(key: str):
        return api.dispatch(
            "POST",
            _SEND_ROUTE,
            body={
                "messenger_account_id": account_id,
                "intent": "otp",
                "peer_reference": {"kind": "dialog", "value": "user:123"},
                "text": "hello",
                "idempotency_key": key,
                "confirm": True,
            },
            authorization=f"Bearer {svc_token}",
            correlation_id="req-12345678-1234-1234-1234-123456789012",
        )

    # The first five attempts consume exactly the local bucket; the sixth is
    # refused with 429 + Retry-After before any adapter call.
    for index in range(5):
        response = _m2m_send(f"preflight-send-{index:08d}")
        assert response.status == 200, response.payload
        assert response.payload["delivery_status"] == "provider_succeeded"
    assert fake_adapter.calls == 5

    rejected = _m2m_send("preflight-send-00000999")
    assert rejected.status == 429
    assert rejected.payload["code"] == "provider_operation_rate_limited"
    assert "Retry-After" in rejected.headers
    assert int(rejected.headers["Retry-After"]) >= 1
    assert fake_adapter.calls == 5

    # A replay of the succeeded key never consumes a provider token: even
    # with the bucket empty it replays from the durable receipt instead of
    # being rate limited.
    replay = _m2m_send("preflight-send-00000000")
    assert replay.status == 200, replay.payload
    assert replay.payload["delivery_status"] == "provider_succeeded"
    assert fake_adapter.calls == 5

    # The preflight explains the same wait honestly (deterministic refill ~0).
    auth_ctx = FakeAuthContext(allowed_accounts=[account_id])
    preflight = _preflight(api._coordinator, auth_ctx, messenger_account_id=account_id)
    assert preflight.payload["decision"] == "wait"
    assert preflight.payload["retry_after_seconds"] is not None
    assert any(
        constraint["reason"] == "rate_limited"
        and constraint["source"] == "local_policy"
        for constraint in preflight.payload["constraints"]
    )


def test_invalid_provider_retry_after_is_rejected(prepared):
    api, account_id = prepared
    from eitaa_bridge.errors import CoordinatorSchemaError

    with pytest.raises(Exception) as exc_info:
        classify_failure("provider_flood", retry_after_ms=90_000_000)
    assert getattr(exc_info.value, "code", "") == "execution_policy_retry_after_invalid"


def _set_bucket(api, scope: str, available: float) -> None:
    """Preset one (account, scope) bucket row deterministically."""
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    with sqlite3.connect(api._coordinator.path) as connection:
        connection.execute(
            """
            INSERT INTO account_execution_limits(
                messenger_account_id, provider, operation_scope, capacity,
                refill_per_second, available_tokens, last_refill_at,
                circuit_state, consecutive_failures, created_at, updated_at
            ) VALUES(?, 'eitaa', ?, 5, 1e-09, ?, ?, 'closed', 0, ?, ?)
            ON CONFLICT(messenger_account_id, operation_scope) DO UPDATE
            SET available_tokens=excluded.available_tokens,
                last_refill_at=excluded.last_refill_at
            """,
            (api._prepared_account_id, scope, available, now, now, now),
        )
        connection.commit()


def test_admission_denial_releases_claim_ownership(prepared, monkeypatch):
    """R1: an admission-denied attempt must resolve its ownership — the same
    id is rate-limited again (never poisoned as duplicate_in_progress) and a
    succeeded id still replays without a token."""
    api, account_id = prepared
    api._prepared_account_id = account_id
    token, csrf = _setup_admin(api)
    credential = _issue_credential(
        api, token, csrf, "denial-service", [account_id], ["eitaa"]
    )
    svc_token = credential["token"]

    api._execution_policy = AccountExecutionPolicyService(
        api._coordinator, default_refill_per_second=1e-9
    )
    api._provider_orchestrator._execution_policy = api._execution_policy

    fake_adapter = FakeEitaaAdapter()
    api._provider_application_adapter_factories["eitaa"] = lambda account: fake_adapter

    # Exactly one free slot: the first send consumes it, the second is
    # denied by capacity with refill effectively frozen.
    _set_bucket(api, "messages.send_text", 1.0)

    def _m2m_send(key: str):
        return api.dispatch(
            "POST",
            _SEND_ROUTE,
            body={
                "messenger_account_id": account_id,
                "intent": "otp",
                "peer_reference": {"kind": "dialog", "value": "user:123"},
                "text": "hello",
                "idempotency_key": key,
                "confirm": True,
            },
            authorization=f"Bearer {svc_token}",
            correlation_id="req-12345678-1234-1234-1234-123456789012",
        )

    first = _m2m_send("ownership-key-0000001")
    assert first.status == 200, first.payload
    denied = _m2m_send("ownership-key-0000002")
    assert denied.status == 429
    assert denied.payload["code"] == "provider_operation_rate_limited"

    # The denied attempt's ownership was resolved: the same id is refused by
    # capacity again — never by a lingering in_progress claim.
    again = _m2m_send("ownership-key-0000002")
    assert again.status == 429
    assert again.payload["code"] == "provider_operation_rate_limited"
    with sqlite3.connect(api._coordinator.path) as connection:
        row = connection.execute(
            """
            SELECT outcome, safe_reason_code FROM provider_operation_receipts
            WHERE idempotency_key='ownership-key-0000002'
            """
        ).fetchone()
    assert row is not None
    assert row[0] == "in_progress"
    assert row[1] == "claim_released"

    # The succeeded id still replays from its durable receipt.
    replay = _m2m_send("ownership-key-0000001")
    assert replay.status == 200
    assert replay.payload["delivery_status"] == "provider_succeeded"
    assert fake_adapter.calls == 1


def test_contact_import_enforces_local_capacity(prepared, monkeypatch):
    """R2: contacts.upsert/import is billed by the same policy — an empty
    bucket refuses the import before the adapter and no contact is added."""
    api, account_id = prepared
    api._prepared_account_id = account_id
    token, csrf = _setup_admin(api)
    credential = _issue_credential(
        api, token, csrf, "import-service", [account_id], ["eitaa"],
        scopes=["messages.send", "contacts.import"],
    )
    svc_token = credential["token"]

    api._execution_policy = AccountExecutionPolicyService(
        api._coordinator, default_refill_per_second=1e-9
    )
    api._provider_orchestrator._execution_policy = api._execution_policy

    class ImportCountingAdapter(FakeEitaaAdapter):
        def __init__(self):
            super().__init__()
            self.imports = 0

        @property
        def manifest(self):
            return SimpleNamespace(
                provider="eitaa",
                capabilities={
                    ProviderCapability.MESSAGES_SEND,
                    ProviderCapability.CONTACTS_WRITE,
                },
            )

        async def list_contacts(self, context, *, cursor=None, limit=100):
            raise AssertionError("not used in this test")

        async def upsert_contact(self, context, request):
            self.imports += 1
            return ProviderContactMutationReceipt(
                contact_reference="user:555", created=True
            )

    counting = ImportCountingAdapter()
    api._provider_application_adapter_factories["eitaa"] = lambda account: counting

    # One free slot in the contacts.upsert bucket: the refusal path drains
    # nothing, so the refusal itself proves admission runs before the adapter.
    _set_bucket(api, "contacts.upsert", 1.0)
    permit = api._execution_policy.acquire(
        messenger_account_id=account_id,
        operation_scope="contacts.upsert",
    )
    assert permit.allowed is True

    def _prepare(key: str):
        return api.dispatch(
            "POST",
            "/api/v2/m2m/recipients/prepare",
            body={
                "messenger_account_id": account_id,
                "provider": "eitaa",
                "phone": "+989120000777",
                "display_name": "گیرندهٔ آزمون",
                "idempotency_key": key,
                "confirm": True,
            },
            authorization=f"Bearer {svc_token}",
            correlation_id="req-12345678-1234-1234-1234-123456789012",
        )

    refused = _prepare("import-key-00000001")
    assert refused.status == 429
    assert refused.payload["code"] == "provider_operation_rate_limited"
    assert "Retry-After" in refused.headers
    assert counting.imports == 0

    # Free the slot: the import proceeds exactly once and the replay of the
    # same key neither re-imports nor re-debits.
    _set_bucket(api, "contacts.upsert", 1.0)
    accepted = _prepare("import-key-00000001")
    assert accepted.status == 200, accepted.payload
    assert accepted.payload["status"] == "matched"
    assert counting.imports == 1
    replayed = _prepare("import-key-00000001")
    assert replayed.status == 200
    assert counting.imports == 1
