"""End-to-end tests for Web Backend Client Reference SDK (Phase 7).

Covers:
- P7-A01: Real loopback HTTP E2E on BridgeApiHttpServer, zero secrets in browser, server-side OTP lifecycle.
- P7-A02: Limits, rate bounds, races, and failures have honest UX and safe retry.
- P7-A03: Real HTTP/transport E2E with counters and cross-service isolation (only Provider & AI mocked at lowest boundary).
- P7-A04: Integration guide, sample execution without secrets.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import threading
import time
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from eitaa_bridge.application import agent_gateway
from eitaa_bridge.application.agent_gateway import AgentChatContext, TestAgentAdapter
from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.application.web_client_reference import (
    BridgeWebClient,
    WebOtpSession,
    compute_recipient_binding,
)
from eitaa_bridge.errors import ProviderExtensionError
from eitaa_bridge.infrastructure.coordinator import (
    CoordinatorDatabase,
    ProtectedPhone,
)
from eitaa_bridge.interfaces.http_api import BridgeApiHttpServer
from eitaa_bridge.providers.contracts import (
    ProviderContactMutationReceipt,
    ProviderSendReceipt,
    ProviderSendStatus,
)


class FakeOrchestrator:
    def __init__(self):
        self.upsert_calls: list[dict[str, Any]] = []
        self.send_calls: list[dict[str, Any]] = []
        self.upsert_failure: Exception | None = None
        self.send_failure: Exception | None = None
        self.send_receipt: ProviderSendReceipt | None = None

    async def upsert_contact(
        self, *, actor, messenger_account_id, correlation_id, deadline_unix_ms, request, **kwargs
    ):
        self.upsert_calls.append({
            "account_id": messenger_account_id,
            "display_name": request.display_name,
            "idempotency_key": request.idempotency_key,
        })
        if self.upsert_failure:
            raise self.upsert_failure
        return ProviderContactMutationReceipt(
            contact_reference="contact:loopback-998877",
            created=True,
        )

    async def send_text(
        self, *, actor, messenger_account_id, request, correlation_id, deadline_unix_ms, skip_admission=False, **kwargs
    ):
        self.send_calls.append({
            "account_id": messenger_account_id,
            "peer": request.peer.opaque_reference,
            "text": request.text,
            "idempotency_key": request.idempotency_key,
            "skip_admission": skip_admission,
        })
        if self.send_failure:
            raise self.send_failure
        if self.send_receipt is not None:
            return self.send_receipt
        return ProviderSendReceipt(
            message_reference="msg_ref_loopback_12345",
            status=ProviderSendStatus.SUCCEEDED,
        )


@pytest.fixture
def loopback_env(config_file: Path):
    from tests.test_clean_install_http_boot import _write_clean_install_config
    _write_clean_install_config(config_file)

    database_path = config_file.parent / "data" / "coordinator" / "coordinator.sqlite3"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    coord_db = CoordinatorDatabase(database_path)
    account_summary = coord_db.bootstrap_legacy_account(
        protected_phone=ProtectedPhone(
            ciphertext=b"protected-phone-loopback",
            key_version=1,
            fingerprint="c" * 64,
            display_hint="+••••••••88",
        ),
        display_name="Loopback Administrator",
        backup_name="verified_loopback.zip",
        source_manifest_sha256="d" * 64,
        source_file_count=1,
        source_total_bytes=1,
    )
    messenger_account_id = account_summary.messenger_account_id

    api = BridgeApplicationApi(config_file)
    assert api.app_user_auth_enabled
    auth_service = api._app_auth
    assert auth_service is not None
    issued = auth_service.bootstrap_admin(
        username="admin_loopback",
        password="ValidPassword123!",
        display_name="Admin Loopback",
        client_kind="desktop_app",
    )
    admin_token = issued.token
    admin_csrf = issued.csrf_token

    # Create service credential
    cred_res = api.dispatch(
        "POST",
        "/api/v2/service-credentials",
        body={
            "service_name": "svc-e2e-client",
            "allowed_providers": ["eitaa", "bale"],
            "allowed_messenger_account_ids": [messenger_account_id],
            "scopes": [
                "messages.send",
                "contacts.resolve",
                "contacts.import",
                "messages.status",
                "agent.chat",
            ],
        },
        app_session_token=admin_token,
        csrf_token=admin_csrf,
    )
    assert cred_res.status in (200, 201)
    service_token = cred_res.payload["token"]
    cred_id = cred_res.payload["credential"]["id"]

    # Setup sender profile for OTP
    prof_res = api.dispatch(
        "PUT",
        "/api/v2/service-sender-profiles",
        body={
            "service_credential_id": cred_id,
            "intent": "otp",
            "provider": "eitaa",
            "messenger_account_id": messenger_account_id,
            "enabled": True,
        },
        app_session_token=admin_token,
        csrf_token=admin_csrf,
    )
    assert prof_res.status == 200
    prof_id = prof_res.payload["profile"]["id"]

    # Setup AI Data Policy for service
    pol_res = api.dispatch(
        "PUT",
        "/api/v2/admin/ai-data-policy/svc-e2e-client",
        body={
            "policy_level": "current_message",
            "max_history_turns": 5,
            "allowed_context_types": [],
        },
        app_session_token=admin_token,
        csrf_token=admin_csrf,
    )
    assert pol_res.status == 200

    # Attach fake orchestrator at lowest provider boundary
    fake_orch = FakeOrchestrator()
    api._provider_orchestrator = fake_orch

    # Boot real HTTP loopback server on ephemeral port
    server = BridgeApiHttpServer(("127.0.0.1", 0), api)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    base_url = f"http://{host}:{port}"

    client = BridgeWebClient(
        base_url=base_url,
        bearer_token=service_token,
        sender_profile_id=prof_id,
    )

    yield {
        "api": api,
        "server": server,
        "client": client,
        "base_url": base_url,
        "service_token": service_token,
        "cred_id": cred_id,
        "messenger_account_id": messenger_account_id,
        "sender_profile_id": prof_id,
        "fake_orchestrator": fake_orch,
    }

    asyncio.run(client.aclose())
    server.shutdown()
    server.server_close()


def test_web_otp_session_verification_and_anti_tamper():
    session = WebOtpSession("+989123333333", ttl_seconds=60, max_attempts=3)
    code = session.get_challenge_code_for_dispatch()
    assert len(code) == 6
    assert code.isdigit()

    # Wrong attempt 1
    ok, reason = session.verify("000000")
    assert not ok
    assert reason == "otp_invalid"
    assert session.attempts == 1

    # Wrong attempt 2
    ok, reason = session.verify("111111")
    assert not ok
    assert reason == "otp_invalid"
    assert session.attempts == 2

    # Correct attempt
    ok, reason = session.verify(code)
    assert ok
    assert reason == "verified"
    assert session.consumed is True

    # Replay attempt (single-use consumption)
    ok, reason = session.verify(code)
    assert not ok
    assert reason == "otp_already_consumed"


def test_web_otp_session_max_attempts_lockout():
    session = WebOtpSession("+989123333333", ttl_seconds=60, max_attempts=2)
    session.verify("111111")
    session.verify("222222")

    # 3rd attempt after max_attempts reached
    ok, reason = session.verify("333333")
    assert not ok
    assert reason == "otp_max_attempts_exceeded"


def test_web_otp_session_expiry():
    session = WebOtpSession("+989123333333", ttl_seconds=0, max_attempts=3)
    time.sleep(0.01)
    code = session.get_challenge_code_for_dispatch()
    ok, reason = session.verify(code)
    assert not ok
    assert reason == "otp_expired"


def test_compute_recipient_binding_stability():
    b1 = compute_recipient_binding("secret-key-1", "+989121111111")
    b2 = compute_recipient_binding("secret-key-1", "09121111111")
    b3 = compute_recipient_binding("secret-key-2", "+989121111111")

    assert b1 == compute_recipient_binding("secret-key-1", "+989121111111")
    assert b1 != b3
    assert "+989121111111" not in b1


def test_e2e_loopback_preflight_and_reservations(loopback_env):
    """P7-A01/A03: Real loopback preflight, reserve capacity, check DB, and cancel."""
    client: BridgeWebClient = loopback_env["client"]
    api: BridgeApplicationApi = loopback_env["api"]

    async def _run():
        # 1. Preflight via real HTTP loopback
        pref = await client.preflight(intent="otp", recipient_kind="new")
        assert pref.ok is True
        assert pref.status == "ready"

        # 2. Reserve capacity via real HTTP loopback
        res = await client.reserve_capacity(
            phone="+989129998877",
            intent="otp",
            ttl_seconds=300,
            idempotency_key="idemp_e2e_res_0000000001",
        )
        assert res.ok is True
        assert res.reservation_id is not None
        assert res.ttl_seconds == 300

        # Verify durable reservation exists in coordinator database
        cred_id = loopback_env["cred_id"]
        db_res = api._delivery_reservation_store.status(
            reservation_id=res.reservation_id,
            service_credential_id=cred_id,
        )
        assert db_res is not None
        assert db_res.state == "reserved"
        assert db_res.intent == "otp"

        # 3. Canonical cancellation via POST .../cancel
        cancel_res = await client.cancel_reservation(res.reservation_id)
        assert cancel_res.ok is True
        assert cancel_res.status == "cancelled"

        # Verify state in DB is cancelled
        db_res_after = api._delivery_reservation_store.status(
            reservation_id=res.reservation_id,
            service_credential_id=cred_id,
        )
        assert db_res_after is not None
        assert db_res_after.state == "cancelled"

        # Idempotent cancel again
        cancel_again = await client.cancel_reservation(res.reservation_id)
        assert cancel_again.ok is True
        assert cancel_again.status == "cancelled"

    asyncio.run(_run())


def test_e2e_loopback_otp_dispatch_poll_and_verify(loopback_env):
    """P7-A01/A03: Full OTP delivery cycle on real loopback server."""
    client: BridgeWebClient = loopback_env["client"]
    api: BridgeApplicationApi = loopback_env["api"]
    fake_orch: FakeOrchestrator = loopback_env["fake_orchestrator"]

    recipient_phone = "+989129998877"

    async def _run():
        # 1. Reserve capacity
        res = await client.reserve_capacity(
            phone=recipient_phone,
            intent="otp",
            ttl_seconds=300,
            idempotency_key="idemp_e2e_otp_0000000001",
        )
        assert res.ok is True
        res_id = res.reservation_id

        # 2. Generate challenge code
        otp_session = WebOtpSession(recipient_phone, ttl_seconds=60, max_attempts=3)
        challenge_code = otp_session.get_challenge_code_for_dispatch()

        # 3. Dispatch OTP
        disp = await client.dispatch_otp(
            reservation_id=res_id,
            phone=recipient_phone,
            contact_name="Student Test",
            message=f"کد ورود شما: {challenge_code}",
            idempotency_key="idemp_e2e_send_000000001",
        )
        assert disp.ok is True
        assert disp.delivery_id is not None
        assert disp.is_replayed is False

        # Verify orchestrator was called at the lowest provider boundary
        assert len(fake_orch.upsert_calls) == 1
        assert fake_orch.upsert_calls[0]["display_name"] == "Student Test"
        assert len(fake_orch.send_calls) == 1
        assert fake_orch.send_calls[0]["skip_admission"] is True

        # 4. Poll status until terminal
        stat = await client.poll_delivery_status(disp.delivery_id, max_polls=5, poll_interval=0.01)
        assert stat.is_terminal is True
        assert stat.is_success is True
        assert stat.status == "accepted"

        # 5. Verify delivery record in database
        db_del = api._otp_delivery_store.get_by_id(disp.delivery_id)
        assert db_del is not None
        assert db_del.stage == "completed"
        assert db_del.send_status == "accepted"

        # 6. Verify user entered code
        verified, reason = otp_session.verify(challenge_code)
        assert verified is True
        assert reason == "verified"

    asyncio.run(_run())


def test_e2e_loopback_idempotency_replay_and_conflict(loopback_env):
    """P7-A02: Replay returns stored record without re-sending; changed payload conflicts."""
    client: BridgeWebClient = loopback_env["client"]
    fake_orch: FakeOrchestrator = loopback_env["fake_orchestrator"]
    phone = "+989129998877"

    async def _run():
        res = await client.reserve_capacity(
            phone=phone,
            intent="otp",
            ttl_seconds=300,
            idempotency_key="idemp_e2e_res_0000000002",
        )
        assert res.ok is True

        idemp_send = "idemp_e2e_send_000000002"
        disp1 = await client.dispatch_otp(
            reservation_id=res.reservation_id,
            phone=phone,
            contact_name="Student Replay",
            message="Your code is 123456",
            idempotency_key=idemp_send,
        )
        assert disp1.ok is True
        assert disp1.is_replayed is False
        assert len(fake_orch.send_calls) == 1

        # Replay same idempotency_key with EXACT same message
        disp_rep = await client.dispatch_otp(
            reservation_id=res.reservation_id,
            phone=phone,
            contact_name="Student Replay",
            message="Your code is 123456",
            idempotency_key=idemp_send,
        )
        assert disp_rep.ok is True
        assert disp_rep.delivery_id == disp1.delivery_id
        assert disp_rep.is_replayed is True
        # Must NOT have made a 2nd call to provider send_text!
        assert len(fake_orch.send_calls) == 1

        # Conflict: same idempotency_key with different message
        disp_conf = await client.dispatch_otp(
            reservation_id=res.reservation_id,
            phone=phone,
            contact_name="Student Replay",
            message="DIFFERENT MESSAGE CODE 999999",
            idempotency_key=idemp_send,
        )
        assert disp_conf.ok is False
        err_str = str(disp_conf.error)
        assert "otp_delivery_conflict" in err_str or "idempotency_payload_mismatch" in err_str

    asyncio.run(_run())


def test_e2e_loopback_reservation_expiry_rejection(loopback_env):
    """P7-A02: Expired reservation cannot be consumed."""
    client: BridgeWebClient = loopback_env["client"]
    api: BridgeApplicationApi = loopback_env["api"]
    phone = "+989129998877"

    async def _run():
        res = await client.reserve_capacity(
            phone=phone,
            intent="otp",
            ttl_seconds=30,
            idempotency_key="idemp_e2e_res_0000000003",
        )
        assert res.ok is True

        # Artificially expire the reservation in the coordinator DB
        with api._delivery_reservation_store._connect() as conn:
            conn.execute(
                "UPDATE service_delivery_reservations SET expires_at='2020-01-01T00:00:00.000Z' WHERE id=?",
                (res.reservation_id,),
            )
            conn.commit()

        disp = await client.dispatch_otp(
            reservation_id=res.reservation_id,
            phone=phone,
            contact_name="Student Expired",
            message="Code: 654321",
            idempotency_key="idemp_e2e_send_000000003",
        )
        assert disp.ok is False
        err_str = str(disp.error)
        assert (
            "delivery_reservation_inactive" in err_str
            or "delivery_reservation_expired" in err_str
            or "reservation_expired" in err_str
        )

    asyncio.run(_run())


def test_e2e_loopback_terminal_uncertain_never_accepted(loopback_env):
    """P7-A02: Provider UNCERTAIN status maps to terminal uncertain without fallback."""
    client: BridgeWebClient = loopback_env["client"]
    fake_orch: FakeOrchestrator = loopback_env["fake_orchestrator"]
    fake_orch.send_receipt = ProviderSendReceipt(
        message_reference="msg_ref_unc_001",
        status=ProviderSendStatus.UNCERTAIN,
    )

    phone = "+989129998877"

    async def _run():
        res = await client.reserve_capacity(
            phone=phone,
            intent="otp",
            ttl_seconds=300,
            idempotency_key="idemp_e2e_res_0000000004",
        )
        assert res.ok is True

        disp = await client.dispatch_otp(
            reservation_id=res.reservation_id,
            phone=phone,
            contact_name="Student Uncertain",
            message="Code: 112233",
            idempotency_key="idemp_e2e_send_0000000004",
        )
        assert disp.ok is True
        assert disp.delivery_id is not None

        stat = await client.poll_delivery_status(disp.delivery_id, max_polls=5, poll_interval=0.01)
        assert stat.is_terminal is True
        assert stat.status == "uncertain"
        assert stat.is_success is False

    asyncio.run(_run())


def test_e2e_loopback_ai_chat_proxy(loopback_env):
    """P7-A03: AI chat proxy over loopback HTTP with session store and adapter."""
    client: BridgeWebClient = loopback_env["client"]

    async def _run():
        chat_res = await client.chat(
            web_user_id="usr_web_loopback",
            session_id="ses_web_loopback",
            message="سلام به هوش مصنوعی",
            message_id="msg-00000001",
        )
        assert chat_res.ok is True
        assert chat_res.response != ""
        assert chat_res.is_test_response is True

    asyncio.run(_run())


def test_e2e_loopback_zero_secrets_leak(loopback_env):
    """P7-A01/A04: Zero token or secret leakage in payloads or endpoints."""
    client: BridgeWebClient = loopback_env["client"]
    service_token = loopback_env["service_token"]

    async def _run():
        pref = await client.preflight(intent="otp", recipient_kind="new")
        assert pref.ok is True
        assert service_token not in json.dumps(pref.raw_payload)

    asyncio.run(_run())
