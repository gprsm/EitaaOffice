"""P4 stage-aware OTP delivery pipeline integration tests.

Verifies:
- P4-A01: Fresh and existing recipient handling, correct name and peer mapping, stage progression.
- P4-A02: Idempotent replay, conflict detection on changed payload, expiry, crash/uncertain outcome, zero resend.
- P4-A03: Contact created without rollback on send failure; honest external outcome recording.
- P4-A04: Privacy (zero raw phone/OTP in status or DB), isolation across service credentials, and scope enforcement.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from eitaa_bridge.application.api import ApiResponse
from eitaa_bridge.application.m2m_api import dispatch_m2m
from eitaa_bridge.application.otp_delivery_pipeline import (
    handle_otp_delivery_create,
    handle_otp_delivery_status,
)
from eitaa_bridge.errors import ProviderExtensionError
from eitaa_bridge.infrastructure.coordinator import (
    CoordinatorDatabase,
    ProtectedPhone,
)
from eitaa_bridge.infrastructure.coordinator.otp_deliveries import (
    OtpDeliveryRecord,
    ServiceOtpDeliveryStore,
)
from eitaa_bridge.infrastructure.coordinator.reservations import (
    ServiceDeliveryReservationStore,
)
from eitaa_bridge.infrastructure.coordinator.service_credentials import (
    ServiceCredentialService,
)
from eitaa_bridge.providers.contracts import (
    ProviderContactMutationReceipt,
    ProviderPeerReference,
    ProviderSendReceipt,
    ProviderSendStatus,
)

_TEST_KEY = b"p4-otp-delivery-test-key"
_BASE_TIME = datetime(2026, 9, 29, 10, 0, 0, tzinfo=timezone.utc)


def _mac(payload: bytes) -> str:
    return hashlib.sha256(_TEST_KEY + b"|" + payload).hexdigest()


class FakeAuthContext:
    def __init__(
        self,
        service_id: str,
        scopes: list[str] | None = None,
        allowed_accounts: list[str] | None = None,
    ):
        self.service_id = service_id
        self.id = service_id
        self.credential_id = service_id
        self.service_name = "test-exam-service"
        self.scopes = list(scopes or ["otp.deliver", "messages.send", "contacts.import", "messages.status"])
        self.allowed_messenger_account_ids = allowed_accounts or []
        self.allowed_providers = ["eitaa", "bale"]


class FakeOrchestrator:
    def __init__(self):
        self.upsert_calls: list[dict] = []
        self.send_calls: list[dict] = []
        self.upsert_failure: Exception | None = None
        self.send_failure: Exception | None = None
        self.send_timeout: bool = False

    async def upsert_contact(
        self, *, actor, messenger_account_id, correlation_id, deadline_unix_ms, request, **kwargs
    ):
        self.upsert_calls.append(
            {
                "account_id": messenger_account_id,
                "display_name": request.display_name,
                "idempotency_key": request.idempotency_key,
            }
        )
        if self.upsert_failure:
            raise self.upsert_failure
        return ProviderContactMutationReceipt(
            contact_reference="contact:998877",
            created=True,
        )

    async def send_text(
        self, *, actor, messenger_account_id, request, correlation_id, deadline_unix_ms, **kwargs
    ):
        self.send_calls.append(
            {
                "account_id": messenger_account_id,
                "peer": request.peer.opaque_reference,
                "text": request.text,
                "idempotency_key": request.idempotency_key,
            }
        )
        if self.send_timeout:
            raise asyncio.TimeoutError("send timed out")
        if self.send_failure:
            raise self.send_failure
        return ProviderSendReceipt(
            message_reference="msg_ref_998811",
            status=ProviderSendStatus.SUCCEEDED,
        )


def _bootstrap_coordinator(tmp_path: Path) -> tuple[CoordinatorDatabase, str, str, str]:
    db_path = tmp_path / "coordinator.sqlite3"
    coordinator = CoordinatorDatabase(db_path)
    coordinator.initialize()
    account_summary = coordinator.bootstrap_legacy_account(
        protected_phone=ProtectedPhone(
            ciphertext=b"ciphertext",
            key_version=1,
            fingerprint="c" * 64,
            display_hint="+••••••••12",
        ),
        display_name="Admin",
        backup_name="backup.zip",
        source_manifest_sha256="d" * 64,
        source_file_count=1,
        source_total_bytes=100,
    )
    cred, _ = ServiceCredentialService(coordinator).create_credential(
        service_name="test-exam-service",
        allowed_providers=["eitaa", "bale"],
        allowed_messenger_account_ids=[account_summary.messenger_account_id],
        scopes=["messages.send", "contacts.import", "otp.deliver", "messages.status"],
        description="P4 fixture",
        created_by_app_user_id=account_summary.app_user_id,
    )
    return coordinator, account_summary.messenger_account_id, account_summary.app_user_id, cred.id


def _create_reservation(
    res_store: ServiceDeliveryReservationStore,
    *,
    cred_id: str,
    actor_id: str,
    account_id: str,
    phone: str,
    idempotency_key: str = "res-idemp-00000001",
    provider: str = "eitaa",
    ttl_seconds: int = 300,
):
    binding = res_store.bind_recipient(
        normalized_value=phone,
        intent="otp",
        service_id=cred_id,
    )
    return res_store.create(
        service_credential_id=cred_id,
        actor_app_user_id=actor_id,
        intent="otp",
        provider=provider,
        messenger_account_id=account_id,
        recipient_binding=binding,
        idempotency_key=idempotency_key,
        ttl_seconds=ttl_seconds,
    )


def test_fresh_recipient_resolve_import_send(tmp_path):
    """P4-A01: Fresh recipient phone triggers resolve -> import -> send."""
    async def _test():
        coordinator, account_id, admin_id, cred_id = _bootstrap_coordinator(tmp_path)
        auth_ctx = FakeAuthContext(service_id=cred_id, allowed_accounts=[account_id])
        res_store = ServiceDeliveryReservationStore(coordinator, binding_mac=_mac, now=lambda: _BASE_TIME)
        otp_store = ServiceOtpDeliveryStore(coordinator, binding_mac=_mac, clock=lambda: _BASE_TIME)
        orchestrator = FakeOrchestrator()

        phone = "+989121112233"
        res = _create_reservation(res_store, cred_id=auth_ctx.id, actor_id=admin_id, account_id=account_id, phone=phone)

        body = {
            "reservation_id": res.id,
            "idempotency_key": "otp-delivery-key-001",
            "recipient": {"kind": "phone", "value": phone, "display_name": "سارا رضایی"},
            "challenge_ref": "chal_user_1001",
            "message_text": "کد تأیید ورود شما: ۱۲۳۴۵۶",
        }

        resp = await handle_otp_delivery_create(
            body,
            auth_ctx,
            orchestrator=orchestrator,
            coordinator=coordinator,
            reservation_store=res_store,
            otp_store=otp_store,
        )

        assert resp.status == 201
        assert resp.payload["ok"] is True
        delivery = resp.payload["delivery"]
        assert delivery["stage"] == "completed"
        assert delivery["state"] == "accepted"
        assert delivery["contact_status"] == "created"
        assert delivery["send_status"] == "accepted"
        assert delivery["provider_message_id"] == "msg_ref_998811"

        # Orchestrator called for both import and send
        assert len(orchestrator.upsert_calls) == 1
        assert orchestrator.upsert_calls[0]["display_name"] == "سارا رضایی"
        assert len(orchestrator.send_calls) == 1
        assert orchestrator.send_calls[0]["peer"] == "user:998877"

        # Reservation was consumed
        updated_res = res_store.status(reservation_id=res.id, service_credential_id=auth_ctx.id)
        assert updated_res.state == "consumed"
        assert updated_res.operation_id == delivery["id"]

    asyncio.run(_test())


def test_existing_recipient_skips_contact_import(tmp_path):
    """P4-A01: If recipient contact is already known, contact import is skipped."""
    async def _test():
        coordinator, account_id, admin_id, cred_id = _bootstrap_coordinator(tmp_path)
        auth_ctx = FakeAuthContext(service_id=cred_id, allowed_accounts=[account_id])
        res_store = ServiceDeliveryReservationStore(coordinator, binding_mac=_mac, now=lambda: _BASE_TIME)
        otp_store = ServiceOtpDeliveryStore(coordinator, binding_mac=_mac, clock=lambda: _BASE_TIME)
        orchestrator = FakeOrchestrator()

        phone = "+989122223344"
        res = _create_reservation(res_store, cred_id=auth_ctx.id, actor_id=admin_id, account_id=account_id, phone=phone)

        # Mock resolver that finds existing contact
        def mock_resolver(normalized_items, acc_id):
            return [{
                "kind": "phone",
                "status": "matched",
                "peer_reference": {"kind": "dialog", "value": "user:554433"},
            }]

        body = {
            "reservation_id": res.id,
            "idempotency_key": "otp-delivery-key-002",
            "recipient": {"kind": "phone", "value": phone, "display_name": "علی محمدی"},
            "challenge_ref": "chal_user_1002",
            "message_text": "کد فعال‌سازی شما: ۶۵۴۳۲۱",
        }

        resp = await handle_otp_delivery_create(
            body,
            auth_ctx,
            orchestrator=orchestrator,
            coordinator=coordinator,
            reservation_store=res_store,
            otp_store=otp_store,
            resolve_handler=mock_resolver,
        )

        assert resp.status == 201
        delivery = resp.payload["delivery"]
        assert delivery["stage"] == "completed"
        assert delivery["state"] == "accepted"
        assert delivery["contact_status"] == "existing"
        assert delivery["send_status"] == "accepted"

        # Contact was NOT imported again!
        assert len(orchestrator.upsert_calls) == 0
        # Send went straight to the matched peer
        assert len(orchestrator.send_calls) == 1
        assert orchestrator.send_calls[0]["peer"] == "user:554433"

    asyncio.run(_test())


def test_idempotent_replay_and_conflict(tmp_path):
    """P4-A02: Replay returns HTTP 200 without duplicate execution; altered payload returns 409."""
    async def _test():
        coordinator, account_id, admin_id, cred_id = _bootstrap_coordinator(tmp_path)
        auth_ctx = FakeAuthContext(service_id=cred_id, allowed_accounts=[account_id])
        res_store = ServiceDeliveryReservationStore(coordinator, binding_mac=_mac, now=lambda: _BASE_TIME)
        otp_store = ServiceOtpDeliveryStore(coordinator, binding_mac=_mac, clock=lambda: _BASE_TIME)
        orchestrator = FakeOrchestrator()

        phone = "+989123334455"
        res = _create_reservation(res_store, cred_id=auth_ctx.id, actor_id=admin_id, account_id=account_id, phone=phone)

        body = {
            "reservation_id": res.id,
            "idempotency_key": "otp-delivery-key-003",
            "recipient": {"kind": "phone", "value": phone},
            "challenge_ref": "chal_user_1003",
            "message_text": "کد ورود: ۹۹۸۸۷۷",
        }

        first = await handle_otp_delivery_create(
            body,
            auth_ctx,
            orchestrator=orchestrator,
            coordinator=coordinator,
            reservation_store=res_store,
            otp_store=otp_store,
        )
        assert first.status == 201
        delivery_id = first.payload["delivery"]["id"]

        # Identical replay returns HTTP 200
        replay = await handle_otp_delivery_create(
            body,
            auth_ctx,
            orchestrator=orchestrator,
            coordinator=coordinator,
            reservation_store=res_store,
            otp_store=otp_store,
        )
        assert replay.status == 200
        assert replay.payload["replayed"] is True
        assert replay.payload["delivery"]["id"] == delivery_id
        # No extra calls were made
        assert len(orchestrator.upsert_calls) == 1
        assert len(orchestrator.send_calls) == 1

        # Conflict: same idempotency key with different payload
        conflict_body = dict(body)
        conflict_body["message_text"] = "کد ورود متفاوت: ۱۱۱۱۱۱"
        conflict = await handle_otp_delivery_create(
            conflict_body,
            auth_ctx,
            orchestrator=orchestrator,
            coordinator=coordinator,
            reservation_store=res_store,
            otp_store=otp_store,
        )
        assert conflict.status == 409
        assert conflict.payload["code"] == "otp_delivery_conflict"

    asyncio.run(_test())


def test_recipient_binding_mismatch_rejected(tmp_path):
    """P4-A04: Attempting delivery to a phone differing from the reservation binding is rejected."""
    async def _test():
        coordinator, account_id, admin_id, cred_id = _bootstrap_coordinator(tmp_path)
        auth_ctx = FakeAuthContext(service_id=cred_id, allowed_accounts=[account_id])
        res_store = ServiceDeliveryReservationStore(coordinator, binding_mac=_mac, now=lambda: _BASE_TIME)
        otp_store = ServiceOtpDeliveryStore(coordinator, binding_mac=_mac, clock=lambda: _BASE_TIME)
        orchestrator = FakeOrchestrator()

        phone_a = "+989124445566"
        phone_b = "+989127778899"
        res = _create_reservation(res_store, cred_id=auth_ctx.id, actor_id=admin_id, account_id=account_id, phone=phone_a)

        body = {
            "reservation_id": res.id,
            "idempotency_key": "otp-delivery-key-004",
            "recipient": {"kind": "phone", "value": phone_b},  # Mismatched phone!
            "challenge_ref": "chal_1004",
            "message_text": "کد: ۱۲۳",
        }

        resp = await handle_otp_delivery_create(
            body,
            auth_ctx,
            orchestrator=orchestrator,
            coordinator=coordinator,
            reservation_store=res_store,
            otp_store=otp_store,
        )
        assert resp.status == 400
        assert resp.payload["code"] == "delivery_recipient_mismatch"
        assert len(orchestrator.upsert_calls) == 0
        assert len(orchestrator.send_calls) == 0

    asyncio.run(_test())


def test_expired_before_dispatch_does_not_send(tmp_path):
    """P4-A02: If reservation has expired by the time delivery runs, sending is aborted."""
    async def _test():
        coordinator, account_id, admin_id, cred_id = _bootstrap_coordinator(tmp_path)
        auth_ctx = FakeAuthContext(service_id=cred_id, allowed_accounts=[account_id])
        curr_time = _BASE_TIME
        res_store = ServiceDeliveryReservationStore(coordinator, binding_mac=_mac, now=lambda: curr_time)
        otp_store = ServiceOtpDeliveryStore(coordinator, binding_mac=_mac, clock=lambda: curr_time)
        orchestrator = FakeOrchestrator()

        phone = "+989125556677"
        res = _create_reservation(res_store, cred_id=auth_ctx.id, actor_id=admin_id, account_id=account_id, phone=phone, ttl_seconds=30)

        # Fast forward clock past TTL
        curr_time = _BASE_TIME + timedelta(seconds=60)

        body = {
            "reservation_id": res.id,
            "idempotency_key": "otp-delivery-key-005",
            "recipient": {"kind": "phone", "value": phone},
            "challenge_ref": "chal_1005",
            "message_text": "کد: ۹۹۹",
        }

        resp = await handle_otp_delivery_create(
            body,
            auth_ctx,
            orchestrator=orchestrator,
            coordinator=coordinator,
            reservation_store=res_store,
            otp_store=otp_store,
        )
        # The reservation was already expired, consume rejected
        assert resp.status == 409
        assert resp.payload["code"] in ("delivery_reservation_expired", "delivery_reservation_inactive")
        assert len(orchestrator.upsert_calls) == 0
        assert len(orchestrator.send_calls) == 0

    asyncio.run(_test())


def test_contact_import_failure_is_retryable(tmp_path):
    """P4-A02: Contact import failure records rejected state and marks retryable."""
    async def _test():
        coordinator, account_id, admin_id, cred_id = _bootstrap_coordinator(tmp_path)
        auth_ctx = FakeAuthContext(service_id=cred_id, allowed_accounts=[account_id])
        res_store = ServiceDeliveryReservationStore(coordinator, binding_mac=_mac, now=lambda: _BASE_TIME)
        otp_store = ServiceOtpDeliveryStore(coordinator, binding_mac=_mac, clock=lambda: _BASE_TIME)
        orchestrator = FakeOrchestrator()
        orchestrator.upsert_failure = ProviderExtensionError("Contact limit reached", code="provider_contact_limit_exceeded")

        phone = "+989126667788"
        res = _create_reservation(res_store, cred_id=auth_ctx.id, actor_id=admin_id, account_id=account_id, phone=phone)

        body = {
            "reservation_id": res.id,
            "idempotency_key": "otp-delivery-key-006",
            "recipient": {"kind": "phone", "value": phone},
            "challenge_ref": "chal_1006",
            "message_text": "کد: ۷۷۷",
        }

        resp = await handle_otp_delivery_create(
            body,
            auth_ctx,
            orchestrator=orchestrator,
            coordinator=coordinator,
            reservation_store=res_store,
            otp_store=otp_store,
        )
        assert resp.status == 201
        delivery = resp.payload["delivery"]
        assert delivery["stage"] == "completed"
        assert delivery["state"] == "rejected"
        assert delivery["contact_status"] == "failed"
        assert delivery["retryable"] is True
        assert len(orchestrator.send_calls) == 0

    asyncio.run(_test())


def test_send_failure_after_contact_creation_does_not_rollback_contact(tmp_path):
    """P4-A03: Contact creation is retained when send is rejected (no fake rollback)."""
    async def _test():
        coordinator, account_id, admin_id, cred_id = _bootstrap_coordinator(tmp_path)
        auth_ctx = FakeAuthContext(service_id=cred_id, allowed_accounts=[account_id])
        res_store = ServiceDeliveryReservationStore(coordinator, binding_mac=_mac, now=lambda: _BASE_TIME)
        otp_store = ServiceOtpDeliveryStore(coordinator, binding_mac=_mac, clock=lambda: _BASE_TIME)
        orchestrator = FakeOrchestrator()
        orchestrator.send_failure = ProviderExtensionError("User blocked bot", code="provider_peer_blocked")

        phone = "+989127778899"
        res = _create_reservation(res_store, cred_id=auth_ctx.id, actor_id=admin_id, account_id=account_id, phone=phone)

        body = {
            "reservation_id": res.id,
            "idempotency_key": "otp-delivery-key-007",
            "recipient": {"kind": "phone", "value": phone},
            "challenge_ref": "chal_1007",
            "message_text": "کد: ۸۸۸",
        }

        resp = await handle_otp_delivery_create(
            body,
            auth_ctx,
            orchestrator=orchestrator,
            coordinator=coordinator,
            reservation_store=res_store,
            otp_store=otp_store,
        )
        assert resp.status == 201
        delivery = resp.payload["delivery"]
        assert delivery["stage"] == "completed"
        assert delivery["state"] == "rejected"
        assert delivery["contact_status"] == "created"  # Contact remains created!
        assert delivery["send_status"] == "rejected"
        assert delivery["safe_reason_code"] == "provider_peer_blocked"

    asyncio.run(_test())


def test_send_timeout_is_uncertain_and_never_auto_retried(tmp_path):
    """P4-A02: Network timeout during send records uncertain outcome; never auto-retried."""
    async def _test():
        coordinator, account_id, admin_id, cred_id = _bootstrap_coordinator(tmp_path)
        auth_ctx = FakeAuthContext(service_id=cred_id, allowed_accounts=[account_id])
        res_store = ServiceDeliveryReservationStore(coordinator, binding_mac=_mac, now=lambda: _BASE_TIME)
        otp_store = ServiceOtpDeliveryStore(coordinator, binding_mac=_mac, clock=lambda: _BASE_TIME)
        orchestrator = FakeOrchestrator()
        orchestrator.send_timeout = True

        phone = "+989128889900"
        res = _create_reservation(res_store, cred_id=auth_ctx.id, actor_id=admin_id, account_id=account_id, phone=phone)

        body = {
            "reservation_id": res.id,
            "idempotency_key": "otp-delivery-key-008",
            "recipient": {"kind": "phone", "value": phone},
            "challenge_ref": "chal_1008",
            "message_text": "کد: ۰۰۰",
        }

        resp = await handle_otp_delivery_create(
            body,
            auth_ctx,
            orchestrator=orchestrator,
            coordinator=coordinator,
            reservation_store=res_store,
            otp_store=otp_store,
        )
        assert resp.status == 201
        delivery = resp.payload["delivery"]
        assert delivery["stage"] == "uncertain"
        assert delivery["state"] == "uncertain"
        assert delivery["send_status"] == "uncertain"
        assert delivery["retryable"] is False

    asyncio.run(_test())


def test_service_isolation_and_privacy(tmp_path):
    """P4-A04: Zero raw phone/OTP in status or DB; cross-service queries return 404."""
    async def _test():
        coordinator, account_id, admin_id, cred_a_id = _bootstrap_coordinator(tmp_path)
        # Create second credential for service B
        cred_b, _ = ServiceCredentialService(coordinator).create_credential(
            service_name="test-service-b",
            allowed_providers=["eitaa", "bale"],
            allowed_messenger_account_ids=[account_id],
            scopes=["messages.send", "contacts.import", "otp.deliver", "messages.status"],
            description="P4 fixture B",
            created_by_app_user_id=admin_id,
        )

        auth_a = FakeAuthContext(service_id=cred_a_id, allowed_accounts=[account_id])
        auth_b = FakeAuthContext(service_id=cred_b.id, allowed_accounts=[account_id])
        res_store = ServiceDeliveryReservationStore(coordinator, binding_mac=_mac, now=lambda: _BASE_TIME)
        otp_store = ServiceOtpDeliveryStore(coordinator, binding_mac=_mac, clock=lambda: _BASE_TIME)
        orchestrator = FakeOrchestrator()

        phone = "+989129990011"
        otp_code = "SECRET_OTP_987654"
        res = _create_reservation(res_store, cred_id=auth_a.id, actor_id=admin_id, account_id=account_id, phone=phone)

        body = {
            "reservation_id": res.id,
            "idempotency_key": "otp-delivery-key-009",
            "recipient": {"kind": "phone", "value": phone},
            "challenge_ref": "chal_1009",
            "message_text": f"کد شما: {otp_code}",
        }

        create_resp = await handle_otp_delivery_create(
            body,
            auth_a,
            orchestrator=orchestrator,
            coordinator=coordinator,
            reservation_store=res_store,
            otp_store=otp_store,
        )
        assert create_resp.status == 201
        delivery_id = create_resp.payload["delivery"]["id"]

        # Verify status query for Service A
        status_a = handle_otp_delivery_status(delivery_id, auth_a, otp_store)
        assert status_a.status == 200
        deliv_data = status_a.payload["delivery"]

        # Privacy checks on JSON response
        deliv_str = str(deliv_data)
        assert phone not in deliv_str
        assert otp_code not in deliv_str
        assert "SECRET_OTP" not in deliv_str

        # Privacy checks on Database rows
        record = otp_store.get_by_id(delivery_id)
        assert record is not None
        rec_str = str(record)
        assert phone not in rec_str
        assert otp_code not in rec_str

        # Isolation check: Service B querying Service A's delivery returns 404
        status_b = handle_otp_delivery_status(delivery_id, auth_b, otp_store)
        assert status_b.status == 404
        assert status_b.payload["code"] == "otp_delivery_not_found"

    asyncio.run(_test())


def test_scope_enforcement(tmp_path):
    """P4-A04: Rejection when service token lacks required delivery scope."""
    async def _test():
        coordinator, account_id, admin_id, cred_id = _bootstrap_coordinator(tmp_path)
        # Auth context missing both otp.deliver and contacts.import
        unscoped_auth = FakeAuthContext(service_id=cred_id, scopes=["messages.send"])
        res_store = ServiceDeliveryReservationStore(coordinator, binding_mac=_mac, now=lambda: _BASE_TIME)
        otp_store = ServiceOtpDeliveryStore(coordinator, binding_mac=_mac, clock=lambda: _BASE_TIME)
        orchestrator = FakeOrchestrator()

        body = {
            "reservation_id": "00000000-0000-4000-8000-000000000001",
            "idempotency_key": "otp-delivery-key-010",
            "recipient": {"kind": "phone", "value": "+989120001122"},
            "challenge_ref": "chal_1010",
            "message_text": "کد: ۱۱۱",
        }

        resp = await handle_otp_delivery_create(
            body,
            unscoped_auth,
            orchestrator=orchestrator,
            coordinator=coordinator,
            reservation_store=res_store,
            otp_store=otp_store,
        )
        assert resp.status == 403
        assert resp.payload["code"] == "m2m_scope_insufficient"

    asyncio.run(_test())


def test_bale_recipient_peer_preserved(tmp_path):
    """P4-A01: Bale account delivery preserves Bale user peer representation."""
    async def _test():
        coordinator, account_id, admin_id, cred_id = _bootstrap_coordinator(tmp_path)
        bale_account_id = str(uuid4())
        now_str = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        with coordinator._connect() as conn:
            pa_id = conn.execute("SELECT phone_account_id FROM messenger_accounts WHERE id=?", (account_id,)).fetchone()[0]
            conn.execute(
                """
                INSERT INTO messenger_accounts (
                    id, phone_account_id, provider, label, lifecycle_state,
                    desired_worker_state, capability_revision, created_at, updated_at
                ) VALUES (?, ?, 'bale', 'Bale Test Account', 'active', 'running', 1, ?, ?)
                """,
                (bale_account_id, pa_id, now_str, now_str),
            )
            conn.execute(
                """
                INSERT INTO account_execution_limits (
                    messenger_account_id, provider, operation_scope, capacity,
                    refill_per_second, available_tokens, last_refill_at, circuit_state,
                    consecutive_failures, created_at, updated_at
                ) VALUES (?, 'bale', 'messages.send_text', 5, 1.0, 5.0, ?, 'closed', 0, ?, ?)
                """,
                (bale_account_id, now_str, now_str, now_str),
            )
            conn.commit()

        auth_ctx = FakeAuthContext(service_id=cred_id, allowed_accounts=[bale_account_id])
        res_store = ServiceDeliveryReservationStore(coordinator, binding_mac=_mac, now=lambda: _BASE_TIME)
        otp_store = ServiceOtpDeliveryStore(coordinator, binding_mac=_mac, clock=lambda: _BASE_TIME)
        orchestrator = FakeOrchestrator()

        phone = "+989129998877"
        res = _create_reservation(
            res_store,
            cred_id=auth_ctx.id,
            actor_id=admin_id,
            account_id=bale_account_id,
            phone=phone,
            provider="bale",
        )

        body = {
            "reservation_id": res.id,
            "idempotency_key": "otp-delivery-key-011",
            "recipient": {"kind": "phone", "value": phone, "display_name": "بله کاربر"},
            "challenge_ref": "chal_bale_1011",
            "message_text": "کد ورود شما در بله: ۳۳۴۴۵۵",
        }

        resp = await handle_otp_delivery_create(
            body,
            auth_ctx,
            orchestrator=orchestrator,
            coordinator=coordinator,
            reservation_store=res_store,
            otp_store=otp_store,
        )
        assert resp.status == 201
        assert len(orchestrator.send_calls) == 1
        # Check that peer reference maintains Bale format
        assert orchestrator.send_calls[0]["peer"].startswith("bale:")

    asyncio.run(_test())


def test_dispatch_m2m_routing_for_otp_deliveries(tmp_path):
    """P4-A01/A04: dispatch_m2m routes POST and GET for OTP deliveries correctly."""
    async def _test():
        coordinator, account_id, admin_id, cred_id = _bootstrap_coordinator(tmp_path)
        auth_ctx = FakeAuthContext(service_id=cred_id, allowed_accounts=[account_id])
        res_store = ServiceDeliveryReservationStore(coordinator, binding_mac=_mac, now=lambda: _BASE_TIME)
        otp_store = ServiceOtpDeliveryStore(coordinator, binding_mac=_mac, clock=lambda: _BASE_TIME)
        orchestrator = FakeOrchestrator()

        phone = "+989128881122"
        res = _create_reservation(res_store, cred_id=auth_ctx.id, actor_id=admin_id, account_id=account_id, phone=phone)

        body = {
            "reservation_id": res.id,
            "idempotency_key": "otp-delivery-key-012",
            "recipient": {"kind": "phone", "value": phone},
            "challenge_ref": "chal_1012",
            "message_text": "کد ورود: ۴۴۵۵۶۶",
        }

        # Test POST route via dispatch_m2m
        create_resp = await dispatch_m2m(
            "POST",
            "/api/v2/m2m/otp/deliveries",
            body=body,
            service_auth_context=auth_ctx,
            request_id="req-m2m-test-01",
            orchestrator=orchestrator,
            coordinator=coordinator,
            reservation_store=res_store,
            otp_delivery_store=otp_store,
        )
        assert create_resp.status == 201
        deliv_id = create_resp.payload["delivery"]["id"]

        # Test GET status route via dispatch_m2m
        status_resp = await dispatch_m2m(
            "GET",
            f"/api/v2/m2m/otp/deliveries/{deliv_id}",
            body=None,
            service_auth_context=auth_ctx,
            request_id="req-m2m-test-02",
            orchestrator=orchestrator,
            coordinator=coordinator,
            reservation_store=res_store,
            otp_delivery_store=otp_store,
        )
        assert status_resp.status == 200
        assert status_resp.payload["delivery"]["id"] == deliv_id
        assert status_resp.payload["delivery"]["state"] == "accepted"

    asyncio.run(_test())
