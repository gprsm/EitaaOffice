from __future__ import annotations

import ast
import asyncio
import base64
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import threading
import time
from types import SimpleNamespace
from uuid import uuid4

import pytest

from eitaa_core import MediaReference, MediaType, Message, Peer, PeerType, save_peer_file

from eitaa_bridge.application.api import ApiResponse, BridgeApplicationApi
from eitaa_bridge.application.eitaa_provider_runtime_operations import (
    EitaaProviderRuntimeOperations,
)
from eitaa_bridge.application.eitaa_provider_worker import EitaaProviderProcessWorker
from eitaa_bridge.application.process_runtime import EitaaProcessRuntime
from eitaa_bridge.application.provider_orchestration import (
    ProviderApplicationOrchestrator,
    ProviderOperationActor,
)
from eitaa_bridge.errors import (
    CompositionValidationError,
    EitaaRuntimeError,
    ProviderExtensionError,
    WorkerIpcError,
)
from eitaa_bridge.infrastructure.config import BridgeConfigLoader
from eitaa_bridge.infrastructure.diagnostics import EVENT_CATALOG, RuntimeLogger
from eitaa_bridge.infrastructure.coordinator import (
    AppPrincipal,
    AuthorizedAppSession,
    CoordinatorDatabase,
    ProtectedPhone,
    ProviderOperationReceiptStore,
)
from eitaa_bridge.infrastructure.worker_ipc import IpcEnvelope
from eitaa_bridge.providers.contracts import (
    ProviderAccountContext,
    ProviderCapability,
    ProviderContactMutationReceipt,
    ProviderContactPage,
    ProviderContactSummary,
    ProviderContactUpsertRequest,
    ProviderDialogPage,
    ProviderDialogSummary,
    ProviderMessagePage,
    ProviderMessageSummary,
    ProviderMediaReadReceipt,
    ProviderMediaReadRequest,
    ProviderOperationContext,
    ProviderPeerReference,
    ProviderSendReceipt,
    ProviderSendStatus,
    ProviderSendTextRequest,
    SensitiveProviderValue,
)
from eitaa_bridge.providers.eitaa import (
    EitaaCompatibilityOperations,
    EitaaProviderApplicationAdapter,
)
from eitaa_bridge.providers.fake import fake_provider_manifest
from eitaa_bridge.providers.registry import default_provider_registry
from eitaa_bridge.providers.testing import InMemoryProviderSessionStore


def _account(provider: str = "fake") -> ProviderAccountContext:
    return ProviderAccountContext(
        messenger_account_id=str(uuid4()),
        phone_account_id=str(uuid4()),
        provider=provider,
        storage_revision=1,
        session_generation=1,
    )


def _actor() -> ProviderOperationActor:
    return ProviderOperationActor(str(uuid4()), "user")


def _deadline() -> int:
    return int(time.time() * 1000) + 30_000


def _correlation(character: str = "a") -> str:
    return character * 32


def _request(key: str = "request-key-0001") -> ProviderSendTextRequest:
    return ProviderSendTextRequest(
        peer=ProviderPeerReference("fake:dialog:1", "private"),
        text="private test text",
        idempotency_key=key,
    )


class _Harness:
    def __init__(self, tmp_path: Path, account: ProviderAccountContext) -> None:
        self.account = account
        self.events: list[str] = []
        self.logger = RuntimeLogger(tmp_path / "provider-orchestration.jsonl")
        self.registry = default_provider_registry()
        self.sessions = InMemoryProviderSessionStore()
        self.adapter_calls = 0

    def authorize(
        self,
        actor: ProviderOperationActor,
        messenger_account_id: str,
        operation: str,
    ) -> None:
        assert actor.app_user_id and operation == "operate"
        self.events.append("authorize")
        if messenger_account_id != self.account.messenger_account_id:
            raise ProviderExtensionError(
                "Access denied.", code="messenger_account_access_denied"
            )

    def context(self, messenger_account_id: str) -> ProviderAccountContext:
        self.events.append("context")
        assert messenger_account_id == self.account.messenger_account_id
        return self.account

    def capability(
        self,
        messenger_account_id: str,
        capability: ProviderCapability,
    ) -> None:
        self.events.append("capability")
        assert messenger_account_id == self.account.messenger_account_id
        manifest = default_provider_registry().registration(self.account.provider).manifest
        assert capability in manifest.capabilities

    def adapter(self, account: ProviderAccountContext):
        self.events.append("adapter")
        self.adapter_calls += 1
        return self.registry.create_adapter("fake", account, self.sessions)

    def orchestrator(self) -> ProviderApplicationOrchestrator:
        return ProviderApplicationOrchestrator(
            authorize_account=self.authorize,
            resolve_account_context=self.context,
            require_capability=self.capability,
            resolve_adapter=self.adapter,
            logger=self.logger,
        )

    def close(self) -> None:
        self.logger.close()


def test_fake_dialog_history_and_send_share_one_ordered_orchestrator(tmp_path):
    harness = _Harness(tmp_path, _account())
    orchestrator = harness.orchestrator()
    actor = _actor()
    peer = ProviderPeerReference("fake:dialog:1", "private")
    try:
        dialogs = asyncio.run(
            orchestrator.list_dialogs(
                actor=actor,
                messenger_account_id=harness.account.messenger_account_id,
                correlation_id=_correlation("a"),
                deadline_unix_ms=_deadline(),
            )
        )
        assert dialogs.dialogs[0].peer == peer
        assert harness.events == ["authorize", "context", "capability", "adapter", "context"]

        harness.events.clear()
        history = asyncio.run(
            orchestrator.load_history(
                actor=actor,
                messenger_account_id=harness.account.messenger_account_id,
                correlation_id=_correlation("b"),
                deadline_unix_ms=_deadline(),
                peer=peer,
            )
        )
        assert history.messages[0].peer == peer
        assert harness.events == ["authorize", "context", "capability", "adapter", "context"]

        harness.events.clear()
        receipt = asyncio.run(
            orchestrator.send_text(
                actor=actor,
                messenger_account_id=harness.account.messenger_account_id,
                correlation_id=_correlation("c"),
                deadline_unix_ms=_deadline(),
                request=_request(),
            )
        )
        assert receipt.status is ProviderSendStatus.SUCCEEDED
        assert harness.events == ["authorize", "context", "capability", "adapter", "context"]
    finally:
        harness.close()


def test_access_and_capability_rejections_happen_before_adapter_resolution(tmp_path):
    account = _account()
    harness = _Harness(tmp_path, account)
    orchestrator = harness.orchestrator()
    try:
        with pytest.raises(ProviderExtensionError) as denied:
            asyncio.run(
                orchestrator.list_dialogs(
                    actor=_actor(),
                    messenger_account_id=str(uuid4()),
                    correlation_id=_correlation("d"),
                    deadline_unix_ms=_deadline(),
                )
            )
        assert denied.value.code == "messenger_account_access_denied"
        assert harness.adapter_calls == 0

        harness.events.clear()

        def reject_capability(account_id: str, capability: ProviderCapability) -> None:
            del account_id, capability
            harness.events.append("capability")
            raise ProviderExtensionError(
                "Unsupported.", code="provider_capability_unavailable"
            )

        blocked = ProviderApplicationOrchestrator(
            authorize_account=harness.authorize,
            resolve_account_context=harness.context,
            require_capability=reject_capability,
            resolve_adapter=harness.adapter,
            logger=harness.logger,
        )
        with pytest.raises(ProviderExtensionError) as unsupported:
            asyncio.run(
                blocked.list_dialogs(
                    actor=_actor(),
                    messenger_account_id=account.messenger_account_id,
                    correlation_id=_correlation("e"),
                    deadline_unix_ms=_deadline(),
                )
            )
        assert unsupported.value.code == "provider_capability_unavailable"
        assert harness.events == ["authorize", "context", "capability"]
        assert harness.adapter_calls == 0
    finally:
        harness.close()


def test_expired_deadline_stops_before_adapter_and_logs_safe_reason(tmp_path):
    harness = _Harness(tmp_path, _account())
    orchestrator = harness.orchestrator()
    try:
        with pytest.raises(ProviderExtensionError) as expired:
            asyncio.run(
                orchestrator.list_dialogs(
                    actor=_actor(),
                    messenger_account_id=harness.account.messenger_account_id,
                    correlation_id=_correlation("f"),
                    deadline_unix_ms=int(time.time() * 1000) - 1,
                )
            )
        assert expired.value.code == "provider_operation_deadline_expired"
        assert harness.adapter_calls == 0
    finally:
        harness.close()
    records = [
        json.loads(line)
        for line in (tmp_path / "provider-orchestration.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    assert records[-1]["event"] == "provider_operation_rejected"
    assert records[-1]["reason_code"] == "provider_operation_deadline_expired"


class _UncertainAdapter:
    def __init__(self, account: ProviderAccountContext) -> None:
        self.account = account
        self.manifest = fake_provider_manifest()
        self.calls = 0

    async def request_challenge(self, context, identity):
        raise AssertionError("not used")

    async def submit_challenge(self, context, challenge_state, response):
        raise AssertionError("not used")

    async def submit_second_factor(self, context, challenge_state, response):
        raise AssertionError("not used")

    async def validate_session(self, context, sealed_session):
        raise AssertionError("not used")

    async def list_dialogs(self, context, *, cursor, limit):
        return ProviderDialogPage(())

    async def load_history(self, context, *, peer, cursor, limit):
        return ProviderMessagePage(())

    async def send_text(self, context, request):
        self.calls += 1
        return ProviderSendReceipt(
            ProviderSendStatus.UNCERTAIN,
            safe_reason_code="fake_delivery_uncertain",
        )

    async def close(self):
        return None


class _RacingAdapter(_UncertainAdapter):
    def __init__(self, account: ProviderAccountContext) -> None:
        super().__init__(account)
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def send_text(self, context, request):
        del context, request
        self.calls += 1
        self.entered.set()
        await self.release.wait()
        return ProviderSendReceipt(
            ProviderSendStatus.SUCCEEDED,
            message_reference="message:race-complete",
        )


class _OversizedMediaAdapter(_UncertainAdapter):
    def __init__(self, account: ProviderAccountContext) -> None:
        super().__init__(account)
        self.manifest = replace(
            fake_provider_manifest(),
            capabilities=frozenset(
                {*fake_provider_manifest().capabilities, ProviderCapability.MEDIA_READ}
            ),
        )

    async def read_media(self, context, request):
        del context
        return ProviderMediaReadReceipt(
            media_reference=request.media_reference,
            content_reference="cache:bounded-test-object",
            mime_type="image/jpeg",
            byte_count=request.max_bytes + 1,
        )


class _MalformedResultAdapter(_UncertainAdapter):
    def __init__(self, account: ProviderAccountContext) -> None:
        super().__init__(account)
        self.dialog_calls = 0

    async def list_dialogs(self, context, *, cursor, limit):
        del context, cursor, limit
        self.dialog_calls += 1
        return {"raw_provider_response": object()}


class _ScopedAdapter(_UncertainAdapter):
    def __init__(self, account: ProviderAccountContext, manifest) -> None:
        super().__init__(account)
        self.manifest = manifest

    async def list_dialogs(self, context, *, cursor, limit):
        del cursor, limit
        assert context.account == self.account
        return ProviderDialogPage(
            (
                ProviderDialogSummary(
                    ProviderPeerReference(
                        f"scope:{self.account.messenger_account_id}", "private"
                    ),
                    f"Scoped {self.account.provider}",
                ),
            )
        )


def test_uncertain_send_is_terminal_and_idempotent_without_retry(tmp_path):
    account = _account()
    harness = _Harness(tmp_path, account)
    adapter = _UncertainAdapter(account)
    orchestrator = ProviderApplicationOrchestrator(
        authorize_account=harness.authorize,
        resolve_account_context=harness.context,
        require_capability=harness.capability,
        resolve_adapter=lambda selected: adapter,
        logger=harness.logger,
    )
    request = _request("uncertain-key-0001")
    actor = _actor()
    try:
        first = asyncio.run(
            orchestrator.send_text(
                actor=actor,
                messenger_account_id=account.messenger_account_id,
                correlation_id=_correlation("1"),
                deadline_unix_ms=_deadline(),
                request=request,
            )
        )
        second = asyncio.run(
            orchestrator.send_text(
                actor=actor,
                messenger_account_id=account.messenger_account_id,
                correlation_id=_correlation("2"),
                deadline_unix_ms=_deadline(),
                request=request,
            )
        )
        assert first is second
        assert first.status is ProviderSendStatus.UNCERTAIN
        assert adapter.calls == 1
    finally:
        harness.close()


def test_idempotent_replay_rechecks_account_authorization(tmp_path):
    account = _account()
    harness = _Harness(tmp_path, account)
    adapter = _UncertainAdapter(account)
    access_allowed = True

    def authorize(actor, account_id, operation):
        del actor, account_id, operation
        if not access_allowed:
            raise ProviderExtensionError(
                "Access denied.", code="messenger_account_access_denied"
            )

    orchestrator = ProviderApplicationOrchestrator(
        authorize_account=authorize,
        resolve_account_context=harness.context,
        require_capability=harness.capability,
        resolve_adapter=lambda selected: adapter,
        logger=harness.logger,
    )
    request = _request("authorization-replay-key-0001")
    actor = _actor()
    try:
        first = asyncio.run(
            orchestrator.send_text(
                actor=actor,
                messenger_account_id=account.messenger_account_id,
                correlation_id=_correlation("0"),
                deadline_unix_ms=_deadline(),
                request=request,
            )
        )
        assert first.status is ProviderSendStatus.UNCERTAIN
        access_allowed = False
        with pytest.raises(ProviderExtensionError) as denied:
            asyncio.run(
                orchestrator.send_text(
                    actor=actor,
                    messenger_account_id=account.messenger_account_id,
                    correlation_id=_correlation("f"),
                    deadline_unix_ms=_deadline(),
                    request=request,
                )
            )
        assert denied.value.code == "messenger_account_access_denied"
        assert adapter.calls == 1
    finally:
        harness.close()


def test_duplicate_send_race_is_rejected_without_second_provider_call(tmp_path):
    account = _account()
    harness = _Harness(tmp_path, account)
    adapter = _RacingAdapter(account)
    orchestrator = ProviderApplicationOrchestrator(
        authorize_account=harness.authorize,
        resolve_account_context=harness.context,
        require_capability=harness.capability,
        resolve_adapter=lambda selected: adapter,
        logger=harness.logger,
    )

    async def race() -> None:
        request = _request("concurrent-request-key-0001")
        actor = _actor()
        first = asyncio.create_task(
            orchestrator.send_text(
                actor=actor,
                messenger_account_id=account.messenger_account_id,
                correlation_id=_correlation("1"),
                deadline_unix_ms=_deadline(),
                request=request,
            )
        )
        await adapter.entered.wait()
        with pytest.raises(ProviderExtensionError) as duplicate:
            await orchestrator.send_text(
                actor=actor,
                messenger_account_id=account.messenger_account_id,
                correlation_id=_correlation("2"),
                deadline_unix_ms=_deadline(),
                request=request,
            )
        assert duplicate.value.code == "provider_operation_duplicate_in_progress"
        adapter.release.set()
        assert (await first).status is ProviderSendStatus.SUCCEEDED

    try:
        asyncio.run(race())
        assert adapter.calls == 1
    finally:
        harness.close()


class _PersistentMutationAdapter(_UncertainAdapter):
    def __init__(self, account: ProviderAccountContext, *, fail_send: bool = False):
        super().__init__(account)
        self.manifest = default_provider_registry().registration("eitaa").manifest
        self.fail_send = fail_send
        self.contact_calls = 0

    async def send_text(self, context, request):
        del context, request
        self.calls += 1
        if self.fail_send:
            raise ProviderExtensionError(
                "Synthetic failure before a verifiable receipt.",
                code="synthetic_provider_failure",
            )
        return ProviderSendReceipt(
            ProviderSendStatus.SUCCEEDED,
            message_reference="message:persistent-42",
        )

    async def list_contacts(self, context, *, cursor, limit):
        del context, cursor, limit
        return ProviderContactPage(())

    async def upsert_contact(self, context, request):
        del context, request
        self.contact_calls += 1
        return ProviderContactMutationReceipt("contact:persistent-42", True)


def _persistent_receipt_fixture(tmp_path):
    database = CoordinatorDatabase(tmp_path / "coordinator.sqlite3")
    bootstrap = database.bootstrap_legacy_account(
        protected_phone=ProtectedPhone(
            ciphertext=b"phase11b2-protected",
            key_version=1,
            fingerprint="5" * 64,
            display_hint="+â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢42",
        ),
        display_name="Phase 11-B2 owner",
        backup_name="verified.zip",
        source_manifest_sha256="4" * 64,
        source_file_count=1,
        source_total_bytes=1,
    )
    account = ProviderAccountContext(
        messenger_account_id=bootstrap.messenger_account_id,
        phone_account_id=bootstrap.phone_account_id,
        provider="eitaa",
        storage_revision=1,
        session_generation=1,
    )
    return (
        database,
        bootstrap,
        account,
        ProviderOperationReceiptStore(database),
    )


def test_mutation_receipts_survive_restart_and_bind_owner_and_payload(tmp_path):
    database, bootstrap, account, store = _persistent_receipt_fixture(tmp_path)
    harness = _Harness(tmp_path, account)
    actor = ProviderOperationActor(bootstrap.app_user_id, "admin")
    private_text = "private-persistent-text"
    request = ProviderSendTextRequest(
        ProviderPeerReference("channel:42", "channel"),
        private_text,
        "persistent-send-key-0001",
    )
    first_adapter = _PersistentMutationAdapter(account)
    first = ProviderApplicationOrchestrator(
        authorize_account=harness.authorize,
        resolve_account_context=harness.context,
        require_capability=harness.capability,
        resolve_adapter=lambda selected: first_adapter,
        logger=harness.logger,
        receipt_store=store,
    )
    try:
        receipt = asyncio.run(
            first.send_text(
                actor=actor,
                messenger_account_id=account.messenger_account_id,
                correlation_id=_correlation("9"),
                deadline_unix_ms=_deadline(),
                request=request,
            )
        )
        assert receipt.message_reference == "message:persistent-42"
        assert first_adapter.calls == 1

        restarted_adapter = _PersistentMutationAdapter(account)
        restarted = ProviderApplicationOrchestrator(
            authorize_account=harness.authorize,
            resolve_account_context=harness.context,
            require_capability=harness.capability,
            resolve_adapter=lambda selected: restarted_adapter,
            logger=harness.logger,
            receipt_store=ProviderOperationReceiptStore(database),
        )
        replay = asyncio.run(
            restarted.send_text(
                actor=actor,
                messenger_account_id=account.messenger_account_id,
                correlation_id=_correlation("8"),
                deadline_unix_ms=_deadline(),
                request=request,
            )
        )
        assert replay == receipt
        assert restarted_adapter.calls == 0

        with pytest.raises(ProviderExtensionError) as payload_mismatch:
            asyncio.run(
                restarted.send_text(
                    actor=actor,
                    messenger_account_id=account.messenger_account_id,
                    correlation_id=_correlation("7"),
                    deadline_unix_ms=_deadline(),
                    request=ProviderSendTextRequest(
                        request.peer,
                        "different-private-text",
                        request.idempotency_key,
                    ),
                )
            )
        assert payload_mismatch.value.code == "provider_idempotency_payload_mismatch"

        with pytest.raises(ProviderExtensionError) as owner_mismatch:
            asyncio.run(
                restarted.send_text(
                    actor=ProviderOperationActor(str(uuid4()), "user"),
                    messenger_account_id=account.messenger_account_id,
                    correlation_id=_correlation("6"),
                    deadline_unix_ms=_deadline(),
                    request=request,
                )
            )
        assert owner_mismatch.value.code == "provider_idempotency_owner_mismatch"

        private_identity = "private-persistent-identity"
        contact_request = ProviderContactUpsertRequest(
            SensitiveProviderValue.from_text(private_identity),
            "Persistent contact",
            "persistent-contact-key-0001",
        )
        contact = asyncio.run(
            restarted.upsert_contact(
                actor=actor,
                messenger_account_id=account.messenger_account_id,
                correlation_id=_correlation("5"),
                deadline_unix_ms=_deadline(),
                request=contact_request,
            )
        )
        assert contact.contact_reference == "contact:persistent-42"
        contact_restarted_adapter = _PersistentMutationAdapter(account)
        contact_restarted = ProviderApplicationOrchestrator(
            authorize_account=harness.authorize,
            resolve_account_context=harness.context,
            require_capability=harness.capability,
            resolve_adapter=lambda selected: contact_restarted_adapter,
            logger=harness.logger,
            receipt_store=ProviderOperationReceiptStore(database),
        )
        assert asyncio.run(
            contact_restarted.upsert_contact(
                actor=actor,
                messenger_account_id=account.messenger_account_id,
                correlation_id=_correlation("4"),
                deadline_unix_ms=_deadline(),
                request=contact_request,
            )
        ) == contact
        assert contact_restarted_adapter.contact_calls == 0

        database_bytes = database.path.read_bytes()
        assert private_text.encode("utf-8") not in database_bytes
        assert private_identity.encode("utf-8") not in database_bytes
    finally:
        harness.close()
    log_text = (tmp_path / "provider-orchestration.jsonl").read_text(
        encoding="utf-8"
    )
    log_records = [json.loads(line) for line in log_text.splitlines() if line]
    assert sum(
        record["event"] == "provider_operation_idempotency_replayed"
        for record in log_records
    ) == 2
    assert private_text not in log_text
    assert private_identity not in log_text
    assert request.idempotency_key not in log_text


def test_expired_persistent_send_claim_becomes_terminal_uncertain(tmp_path):
    database, bootstrap, account, store = _persistent_receipt_fixture(tmp_path)
    harness = _Harness(tmp_path, account)
    actor = ProviderOperationActor(bootstrap.app_user_id, "admin")
    request = ProviderSendTextRequest(
        ProviderPeerReference("channel:42", "channel"),
        "bounded interrupted send",
        "interrupted-send-key-0001",
    )
    failing_adapter = _PersistentMutationAdapter(account, fail_send=True)
    failing = ProviderApplicationOrchestrator(
        authorize_account=harness.authorize,
        resolve_account_context=harness.context,
        require_capability=harness.capability,
        resolve_adapter=lambda selected: failing_adapter,
        logger=harness.logger,
        receipt_store=store,
    )
    try:
        with pytest.raises(ProviderExtensionError) as failed:
            asyncio.run(
                failing.send_text(
                    actor=actor,
                    messenger_account_id=account.messenger_account_id,
                    correlation_id=_correlation("3"),
                    deadline_unix_ms=_deadline(),
                    request=request,
                )
            )
        assert failed.value.code == "synthetic_provider_failure"
        with sqlite3.connect(database.path) as connection:
            connection.execute(
                """
                UPDATE provider_operation_receipts
                SET claim_deadline_unix_ms=1
                WHERE messenger_account_id=? AND operation='messages.send_text'
                  AND idempotency_key=?
                """,
                (account.messenger_account_id, request.idempotency_key),
            )

        restarted_adapter = _PersistentMutationAdapter(account)
        restarted = ProviderApplicationOrchestrator(
            authorize_account=harness.authorize,
            resolve_account_context=harness.context,
            require_capability=harness.capability,
            resolve_adapter=lambda selected: restarted_adapter,
            logger=harness.logger,
            receipt_store=ProviderOperationReceiptStore(database),
        )
        recovered = asyncio.run(
            restarted.send_text(
                actor=actor,
                messenger_account_id=account.messenger_account_id,
                correlation_id=_correlation("2"),
                deadline_unix_ms=_deadline(),
                request=request,
            )
        )
        assert recovered.status is ProviderSendStatus.UNCERTAIN
        assert (
            recovered.safe_reason_code
            == "provider_send_previous_attempt_incomplete"
        )
        assert restarted_adapter.calls == 0
        with sqlite3.connect(database.path) as connection:
            assert connection.execute(
                """
                SELECT outcome FROM provider_operation_receipts
                WHERE messenger_account_id=? AND operation='messages.send_text'
                  AND idempotency_key=?
                """,
                (account.messenger_account_id, request.idempotency_key),
            ).fetchone()[0] == "uncertain"
    finally:
        harness.close()
    log_text = (tmp_path / "provider-orchestration.jsonl").read_text(
        encoding="utf-8"
    )
    log_events = {
        json.loads(line)["event"] for line in log_text.splitlines() if line
    }
    assert "provider_operation_idempotency_interrupted" in log_events
    assert "provider_operation_idempotency_replayed" in log_events
    assert request.idempotency_key not in log_text


def test_manifest_is_capability_ceiling_even_if_decision_service_allows(tmp_path):
    account = _account()
    harness = _Harness(tmp_path, account)
    adapter = _MalformedResultAdapter(account)
    adapter.manifest = replace(
        fake_provider_manifest(),
        capabilities=frozenset(
            {ProviderCapability.HISTORY_READ, ProviderCapability.MESSAGES_SEND}
        ),
    )
    orchestrator = ProviderApplicationOrchestrator(
        authorize_account=harness.authorize,
        resolve_account_context=harness.context,
        require_capability=lambda account_id, capability: None,
        resolve_adapter=lambda selected: adapter,
        logger=harness.logger,
    )
    try:
        with pytest.raises(ProviderExtensionError) as unavailable:
            asyncio.run(
                orchestrator.list_dialogs(
                    actor=_actor(),
                    messenger_account_id=account.messenger_account_id,
                    correlation_id=_correlation("3"),
                    deadline_unix_ms=_deadline(),
                )
            )
        assert unavailable.value.code == "provider_capability_unavailable"
        assert adapter.dialog_calls == 0
    finally:
        harness.close()


def test_invalid_correlation_and_oversized_or_malformed_results_fail_closed(tmp_path):
    account = _account()
    harness = _Harness(tmp_path, account)
    malformed = _MalformedResultAdapter(account)
    selected_adapter = malformed
    orchestrator = ProviderApplicationOrchestrator(
        authorize_account=harness.authorize,
        resolve_account_context=harness.context,
        require_capability=lambda account_id, capability: None,
        resolve_adapter=lambda selected: selected_adapter,
        logger=harness.logger,
    )
    try:
        with pytest.raises(ProviderExtensionError) as invalid_context:
            asyncio.run(
                orchestrator.list_dialogs(
                    actor=_actor(),
                    messenger_account_id=account.messenger_account_id,
                    correlation_id="not-a-correlation",
                    deadline_unix_ms=_deadline(),
                )
            )
        assert invalid_context.value.code == "provider_operation_context_invalid"
        assert malformed.dialog_calls == 0

        with pytest.raises(ProviderExtensionError) as invalid_result:
            asyncio.run(
                orchestrator.list_dialogs(
                    actor=_actor(),
                    messenger_account_id=account.messenger_account_id,
                    correlation_id=_correlation("4"),
                    deadline_unix_ms=_deadline(),
                )
            )
        assert invalid_result.value.code == "provider_operation_result_invalid"

        oversized = _OversizedMediaAdapter(account)
        selected_adapter = oversized
        with pytest.raises(ProviderExtensionError) as too_large:
            asyncio.run(
                orchestrator.read_media(
                    actor=_actor(),
                    messenger_account_id=account.messenger_account_id,
                    correlation_id=_correlation("5"),
                    deadline_unix_ms=_deadline(),
                    request=ProviderMediaReadRequest(
                        peer=ProviderPeerReference("fake:dialog:1", "private"),
                        message_reference="message:1",
                        media_reference="media:1",
                        max_bytes=32 * 1024,
                    ),
                )
            )
        assert too_large.value.code == "provider_media_limit_exceeded"
    finally:
        harness.close()


def test_two_users_multiple_accounts_and_providers_remain_server_scoped(tmp_path):
    fake_one = _account()
    fake_two = _account()
    eitaa_one = _account("eitaa")
    accounts = {
        item.messenger_account_id: item for item in (fake_one, fake_two, eitaa_one)
    }
    first_actor = _actor()
    second_actor = _actor()
    memberships = {
        first_actor.app_user_id: {
            fake_one.messenger_account_id,
            eitaa_one.messenger_account_id,
        },
        second_actor.app_user_id: {fake_two.messenger_account_id},
    }
    registry = default_provider_registry()
    adapters = {
        fake_one.messenger_account_id: _ScopedAdapter(
            fake_one, fake_provider_manifest()
        ),
        fake_two.messenger_account_id: _ScopedAdapter(
            fake_two, fake_provider_manifest()
        ),
        eitaa_one.messenger_account_id: _ScopedAdapter(
            eitaa_one, registry.registration("eitaa").manifest
        ),
    }
    resolutions: list[str] = []
    logger = RuntimeLogger(tmp_path / "provider-multi-scope.jsonl")

    def authorize(actor, account_id, operation):
        assert operation == "operate"
        if account_id not in memberships.get(actor.app_user_id, set()):
            raise ProviderExtensionError(
                "Access denied.", code="messenger_account_access_denied"
            )

    def resolve(account_id):
        return accounts[account_id]

    def capability(account_id, selected):
        assert selected in adapters[account_id].manifest.capabilities

    def adapter(account):
        resolutions.append(account.messenger_account_id)
        return adapters[account.messenger_account_id]

    orchestrator = ProviderApplicationOrchestrator(
        authorize_account=authorize,
        resolve_account_context=resolve,
        require_capability=capability,
        resolve_adapter=adapter,
        logger=logger,
    )
    try:
        for actor, account in (
            (first_actor, fake_one),
            (first_actor, eitaa_one),
            (second_actor, fake_two),
        ):
            page = asyncio.run(
                orchestrator.list_dialogs(
                    actor=actor,
                    messenger_account_id=account.messenger_account_id,
                    correlation_id=_correlation("6"),
                    deadline_unix_ms=_deadline(),
                )
            )
            assert page.dialogs[0].peer.opaque_reference.endswith(
                account.messenger_account_id
            )
        before_denial = list(resolutions)
        with pytest.raises(ProviderExtensionError) as denied:
            asyncio.run(
                orchestrator.list_dialogs(
                    actor=first_actor,
                    messenger_account_id=fake_two.messenger_account_id,
                    correlation_id=_correlation("7"),
                    deadline_unix_ms=_deadline(),
                )
            )
        assert denied.value.code == "messenger_account_access_denied"
        assert resolutions == before_denial
        assert resolutions == [
            fake_one.messenger_account_id,
            eitaa_one.messenger_account_id,
            fake_two.messenger_account_id,
        ]
    finally:
        logger.close()


def test_eitaa_compatibility_adapter_uses_the_same_orchestrator_contract(tmp_path):
    account = _account("eitaa")
    registry = default_provider_registry()
    calls: list[str] = []
    peer = ProviderPeerReference("channel:42", "channel")

    async def dialogs(context: ProviderOperationContext, cursor: str | None, limit: int):
        del context, cursor, limit
        calls.append("dialogs")
        return ProviderDialogPage((ProviderDialogSummary(peer, "Eitaa dialog", 2),))

    async def history(
        context: ProviderOperationContext,
        selected_peer: ProviderPeerReference,
        cursor: str | None,
        limit: int,
    ):
        del context, cursor, limit
        calls.append("history")
        return ProviderMessagePage(
            (
                ProviderMessageSummary(
                    "message:42",
                    selected_peer,
                    "sender:42",
                    1,
                    "bounded text",
                ),
            )
        )

    async def send(context: ProviderOperationContext, request: ProviderSendTextRequest):
        del context, request
        calls.append("send")
        return ProviderSendReceipt(
            ProviderSendStatus.SUCCEEDED,
            message_reference="message:43",
        )

    async def media(context: ProviderOperationContext, request: ProviderMediaReadRequest):
        del context
        calls.append("media")
        return ProviderMediaReadReceipt(
            request.media_reference,
            "cache:eitaa-bounded-media",
            "image/jpeg",
            1024,
        )

    async def contacts(context: ProviderOperationContext, cursor: str | None, limit: int):
        del context, cursor, limit
        calls.append("contacts")
        return ProviderContactPage(
            (ProviderContactSummary("contact:42", "Synthetic Eitaa contact", "+â€¢â€¢â€¢42"),)
        )

    async def upsert(
        context: ProviderOperationContext,
        request: ProviderContactUpsertRequest,
    ):
        del context
        assert "private-synthetic-identity" not in repr(request)
        calls.append("upsert")
        return ProviderContactMutationReceipt("contact:43", True)

    operations = EitaaCompatibilityOperations(
        dialogs,
        history,
        send,
        read_media=media,
        list_contacts=contacts,
        upsert_contact=upsert,
    )
    logger = RuntimeLogger(tmp_path / "eitaa-orchestration.jsonl")
    orchestrator = ProviderApplicationOrchestrator(
        authorize_account=lambda actor, account_id, operation: None,
        resolve_account_context=lambda account_id: account,
        require_capability=lambda account_id, capability: None,
        resolve_adapter=lambda selected: EitaaProviderApplicationAdapter(
            selected,
            registry.registration("eitaa").manifest,
            operations,
        ),
        logger=logger,
    )
    try:
        actor = _actor()
        assert asyncio.run(
            orchestrator.list_dialogs(
                actor=actor,
                messenger_account_id=account.messenger_account_id,
                correlation_id=_correlation("3"),
                deadline_unix_ms=_deadline(),
            )
        ).dialogs[0].peer == peer
        assert asyncio.run(
            orchestrator.load_history(
                actor=actor,
                messenger_account_id=account.messenger_account_id,
                correlation_id=_correlation("4"),
                deadline_unix_ms=_deadline(),
                peer=peer,
            )
        ).messages[0].message_reference == "message:42"
        assert asyncio.run(
            orchestrator.send_text(
                actor=actor,
                messenger_account_id=account.messenger_account_id,
                correlation_id=_correlation("5"),
                deadline_unix_ms=_deadline(),
                request=ProviderSendTextRequest(
                    peer,
                    "bounded text",
                    "eitaa-request-key-0001",
                ),
            )
        ).message_reference == "message:43"
        assert asyncio.run(
            orchestrator.read_media(
                actor=actor,
                messenger_account_id=account.messenger_account_id,
                correlation_id=_correlation("6"),
                deadline_unix_ms=_deadline(),
                request=ProviderMediaReadRequest(
                    peer=peer,
                    message_reference="message:42",
                    media_reference="media:42",
                    max_bytes=32 * 1024,
                ),
            )
        ).content_reference == "cache:eitaa-bounded-media"
        assert asyncio.run(
            orchestrator.list_contacts(
                actor=actor,
                messenger_account_id=account.messenger_account_id,
                correlation_id=_correlation("7"),
                deadline_unix_ms=_deadline(),
            )
        ).contacts[0].contact_reference == "contact:42"
        assert asyncio.run(
            orchestrator.upsert_contact(
                actor=actor,
                messenger_account_id=account.messenger_account_id,
                correlation_id=_correlation("8"),
                deadline_unix_ms=_deadline(),
                request=ProviderContactUpsertRequest(
                    SensitiveProviderValue.from_text("private-synthetic-identity"),
                    "Synthetic Eitaa contact",
                    "eitaa-contact-key-0001",
                ),
            )
        ).contact_reference == "contact:43"
        assert calls == ["dialogs", "history", "send", "media", "contacts", "upsert"]
    finally:
        logger.close()


def test_unknown_adapter_exception_is_sanitized_and_private_text_is_not_logged(tmp_path):
    account = _account()
    harness = _Harness(tmp_path, account)

    def explode(selected: ProviderAccountContext):
        del selected
        raise RuntimeError("private test text token=should-not-leak")

    orchestrator = ProviderApplicationOrchestrator(
        authorize_account=harness.authorize,
        resolve_account_context=harness.context,
        require_capability=harness.capability,
        resolve_adapter=explode,
        logger=harness.logger,
    )
    try:
        with pytest.raises(ProviderExtensionError) as failed:
            asyncio.run(
                orchestrator.list_dialogs(
                    actor=_actor(),
                    messenger_account_id=account.messenger_account_id,
                    correlation_id=_correlation("6"),
                    deadline_unix_ms=_deadline(),
                )
            )
        assert failed.value.code == "provider_operation_failed"
        assert "private test text" not in str(failed.value)
    finally:
        harness.close()
    log_text = (tmp_path / "provider-orchestration.jsonl").read_text(encoding="utf-8")
    assert "private test text" not in log_text
    assert "should-not-leak" not in log_text
    assert "RuntimeError" in log_text


def test_orchestrator_has_no_provider_name_branch_and_events_are_cataloged():
    source_path = (
        Path(__file__).parents[1]
        / "src"
        / "eitaa_bridge"
        / "application"
        / "provider_orchestration.py"
    )
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    string_values = {
        node.value.lower()
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert not ({"eitaa", "bale", "fake"} & string_values)
    assert {
        "provider_operation_started",
        "provider_operation_succeeded",
        "provider_operation_rejected",
        "provider_operation_failed",
        "provider_operation_uncertain",
        "provider_operation_idempotency_replayed",
        "provider_operation_idempotency_interrupted",
        "provider_operation_adapter_close_failed",
    } <= set(EVENT_CATALOG)


def test_media_and_contact_contracts_are_bounded_and_capability_gated(tmp_path):
    peer = ProviderPeerReference("fake:dialog:1", "private")
    media = ProviderMediaReadRequest(
        peer=peer,
        message_reference="message:1",
        media_reference="media:1",
        variant="thumbnail",
        max_bytes=64 * 1024,
    )
    contact = ProviderContactUpsertRequest(
        identity=SensitiveProviderValue.from_text("private-test-identity"),
        display_name="Synthetic contact",
        idempotency_key="contact-request-0001",
    )
    assert "private-test-identity" not in repr(contact)
    assert media.max_bytes == 64 * 1024
    with pytest.raises(ProviderExtensionError) as path_rejected:
        ProviderMediaReadRequest(
            peer=peer,
            message_reference="message:1",
            media_reference="../../private.file",
        )
    assert path_rejected.value.code == "provider_media_reference_invalid"
    

    account = _account()
    harness = _Harness(tmp_path, account)

    def reject(account_id: str, capability: ProviderCapability) -> None:
        del account_id
        raise ProviderExtensionError(
            "Unsupported.",
            safe_context={"capability": capability.value},
            code="provider_capability_unavailable",
        )

    orchestrator = ProviderApplicationOrchestrator(
        authorize_account=harness.authorize,
        resolve_account_context=harness.context,
        require_capability=reject,
        resolve_adapter=harness.adapter,
        logger=harness.logger,
    )
    try:
        with pytest.raises(ProviderExtensionError) as media_rejected:
            asyncio.run(
                orchestrator.read_media(
                    actor=_actor(),
                    messenger_account_id=account.messenger_account_id,
                    correlation_id=_correlation("7"),
                    deadline_unix_ms=_deadline(),
                    request=media,
                )
            )
        assert media_rejected.value.code == "provider_capability_unavailable"
        with pytest.raises(ProviderExtensionError) as contacts_rejected:
            asyncio.run(
                orchestrator.list_contacts(
                    actor=_actor(),
                    messenger_account_id=account.messenger_account_id,
                    correlation_id=_correlation("8"),
                    deadline_unix_ms=_deadline(),
                )
            )
        assert contacts_rejected.value.code == "provider_capability_unavailable"
        with pytest.raises(ProviderExtensionError) as mutation_rejected:
            asyncio.run(
                orchestrator.upsert_contact(
                    actor=_actor(),
                    messenger_account_id=account.messenger_account_id,
                    correlation_id=_correlation("9"),
                    deadline_unix_ms=_deadline(),
                    request=contact,
                )
            )
        assert mutation_rejected.value.code == "provider_capability_unavailable"
        assert harness.adapter_calls == 0
    finally:
        harness.close()


def test_provider_neutral_api_routes_and_payload_mapping(config_file):
    account = _account("eitaa")
    peer = ProviderPeerReference("channel:42", "channel")

    class StubOrchestrator:
        async def list_dialogs(self, **kwargs):
            assert kwargs["messenger_account_id"] == account.messenger_account_id
            return ProviderDialogPage(
                (ProviderDialogSummary(peer, "Mapped dialog", 3),),
                next_cursor="offset:1",
            )

        async def load_history(self, **kwargs):
            assert kwargs["peer"] == peer
            return ProviderMessagePage(
                (
                    ProviderMessageSummary(
                        "message:42",
                        peer,
                        "sender:42",
                        1000,
                        "Mapped text",
                    ),
                ),
                next_cursor="before:42",
            )

        async def send_text(self, **kwargs):
            assert kwargs["request"].peer == peer
            return ProviderSendReceipt(
                ProviderSendStatus.SUCCEEDED,
                message_reference="message:43",
            )

        async def read_media(self, **kwargs):
            assert kwargs["request"].media_reference == "media:42"
            return ProviderMediaReadReceipt(
                "media:42",
                "cache:mapped-media",
                "image/jpeg",
                2048,
            )

        async def list_contacts(self, **kwargs):
            assert kwargs["limit"] == 10
            return ProviderContactPage(
                (ProviderContactSummary("contact:42", "Mapped contact", "+â€¢â€¢â€¢42"),),
                next_cursor="offset:1",
            )

        async def upsert_contact(self, **kwargs):
            assert "synthetic-private-identity" not in repr(kwargs["request"])
            return ProviderContactMutationReceipt("contact:43", True)

    session = AuthorizedAppSession(
        principal=AppPrincipal(
            app_user_id=str(uuid4()),
            display_name="Phase 11-B2 actor",
            global_role="admin",
            session_id=str(uuid4()),
            client_kind="test",
        ),
        csrf_token="csrf",
        idle_expires_at="2026-08-20T00:00:00+00:00",
        absolute_expires_at="2026-08-20T01:00:00+00:00",
    )
    api = BridgeApplicationApi(config_file)
    api._provider_orchestrator = StubOrchestrator()
    api._provider_operation_account_context = lambda selected: account
    try:
        dialogs = api._provider_dialog_query(
            session,
            account.messenger_account_id,
            {"limit": 10},
            request_id=_correlation("a"),
        )
        assert dialogs.status == 200
        assert dialogs.payload["dialogs"] == [
            {
                "peer_reference": "channel:42",
                "peer_kind": "channel",
                "title": "Mapped dialog",
                "unread_count": 3,
            }
        ]

        history = api._provider_history_query(
            session,
            account.messenger_account_id,
            {
                "peer_reference": peer.opaque_reference,
                "peer_kind": peer.kind,
                "limit": 10,
            },
            request_id=_correlation("b"),
        )
        assert history.status == 200
        assert history.payload["messages"][0]["message_reference"] == "message:42"

        sent = api._provider_send_text(
            session,
            account.messenger_account_id,
            {
                "peer_reference": peer.opaque_reference,
                "peer_kind": peer.kind,
                "text": "private request text",
                "idempotency_key": "api-request-key-0001",
                "confirm": True,
            },
            request_id=_correlation("c"),
        )
        assert sent.status == 201
        assert sent.payload["message_reference"] == "message:43"

        media = api._provider_media_read(
            session,
            account.messenger_account_id,
            {
                "peer_reference": peer.opaque_reference,
                "peer_kind": peer.kind,
                "message_reference": "message:42",
                "media_reference": "media:42",
                "max_bytes": 32 * 1024,
            },
            request_id=_correlation("d"),
        )
        assert media.status == 200
        assert media.payload["content_reference"] == "cache:mapped-media"

        contacts = api._provider_contact_query(
            session,
            account.messenger_account_id,
            {"limit": 10},
            request_id=_correlation("e"),
        )
        assert contacts.status == 200
        assert contacts.payload["contacts"][0]["identity_hint"] == "+â€¢â€¢â€¢42"

        upserted = api._provider_contact_upsert(
            session,
            account.messenger_account_id,
            {
                "identity": "synthetic-private-identity",
                "display_name": "Mapped contact",
                "idempotency_key": "api-contact-key-0001",
                "confirm": True,
            },
            request_id=_correlation("f"),
        )
        assert upserted.status == 201
        assert upserted.payload["contact_reference"] == "contact:43"
        assert "identity" not in upserted.payload

        with pytest.raises(CompositionValidationError) as forged_scope:
            api._provider_dialog_query(
                session,
                account.messenger_account_id,
                {
                    "messenger_account_id": str(uuid4()),
                    "capability": "messages.send",
                },
                request_id=_correlation("1"),
            )
        assert forged_scope.value.code == "provider_operation_fields_rejected"

        with pytest.raises(CompositionValidationError) as missing_idempotency:
            api._provider_send_text(
                session,
                account.messenger_account_id,
                {
                    "peer_reference": peer.opaque_reference,
                    "peer_kind": peer.kind,
                    "text": "bounded synthetic text",
                },
                request_id=_correlation("2"),
            )
        assert missing_idempotency.value.code == "provider_idempotency_key_required"

        with pytest.raises(CompositionValidationError) as missing_send_confirmation:
            api._provider_send_text(
                session,
                account.messenger_account_id,
                {
                    "peer_reference": peer.opaque_reference,
                    "peer_kind": peer.kind,
                    "text": "bounded synthetic text",
                    "idempotency_key": "api-request-key-0002",
                },
                request_id=_correlation("4"),
            )
        assert (
            missing_send_confirmation.value.code
            == "provider_message_send_confirmation_required"
        )

        with pytest.raises(CompositionValidationError) as missing_contact_confirmation:
            api._provider_contact_upsert(
                session,
                account.messenger_account_id,
                {
                    "identity": "synthetic-private-identity",
                    "display_name": "Mapped contact",
                    "idempotency_key": "api-contact-key-0002",
                },
                request_id=_correlation("3"),
            )
        assert (
            missing_contact_confirmation.value.code
            == "provider_contact_mutation_confirmation_required"
        )

        calls: list[str] = []

        def route_stub(session_arg, account_id, payload, *, request_id):
            del session_arg, payload, request_id
            calls.append(account_id)
            return ApiResponse(200, {"ok": True})

        routes = (
            ("_provider_dialog_query", "dialogs/query"),
            ("_provider_history_query", "history/query"),
            ("_provider_send_text", "messages/send-text"),
            ("_provider_media_read", "media/read"),
            ("_provider_contact_query", "contacts/query"),
            ("_provider_contact_upsert", "contacts/upsert"),
        )
        for attribute, suffix in routes:
            setattr(api, attribute, route_stub)
            routed = api.dispatch(
                "POST",
                f"/api/v2/messenger-accounts/{account.messenger_account_id}/{suffix}",
                body={},
            )
            assert routed.status == 200
        assert calls == [account.messenger_account_id] * len(routes)
    finally:
        api.close()


def test_eitaa_media_and_contact_mapping_is_bounded_without_network(config_file):
    account = _account("eitaa")
    context = ProviderOperationContext(account, _correlation("a"), _deadline())
    peer = ProviderPeerReference("channel:42", "channel")
    canonical_phone = "+" + "1" + "0" * 7
    api = BridgeApplicationApi(config_file)

    class DialogCatalogStub:
        @staticmethod
        def get(peer_reference):
            assert peer_reference == peer.opaque_reference
            return {"peer_file": "server-owned-peer-reference"}

    api.dialog_catalog = DialogCatalogStub()
    api._eitaa_provider_runtime_scope = lambda selected: nullcontext()
    api._eitaa_process_provider_request = lambda *args, **kwargs: None
    api._media_preview = lambda payload: {
        "media_present": True,
        "preview_available": True,
        "media_url": "/api/v1/media-cache/synthetic-cache-token",
        "mime_type": "image/jpeg",
        "bytes": 1024,
    }
    api._eitaa_contacts_list = lambda payload: {
        "contacts": [
            {
                "user_id": 42,
                "display_name": "Synthetic contact",
                "phone": canonical_phone,
            }
        ],
        "has_more": False,
    }

    def add_contact(payload):
        assert payload["phone"] == canonical_phone
        assert payload["save_local"] is False
        return {"contact": {"user_id": 43}, "contact_added": True}

    api._eitaa_contacts_add = add_contact
    try:
        media = asyncio.run(
            api._eitaa_provider_media(
                context,
                ProviderMediaReadRequest(
                    peer,
                    "message:42",
                    "media:42",
                    max_bytes=32 * 1024,
                ),
            )
        )
        assert media.content_reference == "cache:synthetic-cache-token"
        assert media.byte_count == 1024

        contacts = asyncio.run(api._eitaa_provider_contacts(context, None, 10))
        assert contacts.contacts[0].contact_reference == "contact:42"
        pass

        receipt = asyncio.run(
            api._eitaa_provider_contact_upsert(
                context,
                ProviderContactUpsertRequest(
                    SensitiveProviderValue.from_text(canonical_phone),
                    "Synthetic contact",
                    "mapping-contact-key-0001",
                ),
            )
        )
        assert receipt == ProviderContactMutationReceipt("contact:43", True)
    finally:
        api.close()


def test_eitaa_process_runtime_maps_all_provider_operations_without_provider_state(
    config_file,
):
    account = _account("eitaa")
    context = ProviderOperationContext(account, _correlation("b"), _deadline())
    peer = ProviderPeerReference("channel:42", "channel")
    cache_reference = "a" * 32
    calls: list[tuple[str, dict[str, object]]] = []

    runtime = object.__new__(EitaaProcessRuntime)
    runtime.runtime_record = SimpleNamespace(
        messenger_account_id=account.messenger_account_id
    )
    runtime._closed = False

    def provider_request(method, payload, *, timeout_seconds):
        assert timeout_seconds > 0
        selected = dict(payload)
        calls.append((method, selected))
        if method == "eitaa.provider.dialogs.query":
            return {
                "dialogs": [
                    {
                        "peer_reference": peer.opaque_reference,
                        "peer_kind": peer.kind,
                        "title": "Process dialog",
                        "unread_count": 2,
                    }
                ],
                "next_cursor": None,
            }
        if method == "eitaa.provider.history.query":
            return {
                "messages": [
                    {
                        "message_reference": "message:42",
                        "peer_reference": peer.opaque_reference,
                        "peer_kind": peer.kind,
                        "sender_reference": "user:7",
                        "sent_at_unix_ms": 1_700_000_000_000,
                        "text": "bounded process text",
                    }
                ],
                "next_cursor": None,
                "transport_truncated": False,
            }
        if method == "eitaa.provider.messages.send_text":
            return {"status": "succeeded", "message_reference": "message:43"}
        if method == "eitaa.provider.media.read":
            return {
                "media_reference": "media:42",
                "content_reference": f"cache:{cache_reference}",
                "mime_type": "image/jpeg",
                "byte_count": 3,
            }
        if method == "eitaa.provider.contacts.query":
            return {
                "contacts": [
                    {
                        "contact_reference": "contact:42",
                        "display_name": "Process contact",
                        "identity_hint": "+â€¢â€¢â€¢00",
                    }
                ],
                "next_cursor": None,
            }
        if method == "eitaa.provider.contacts.upsert":
            return {"contact_reference": "contact:43", "created": True}
        if method == "eitaa.provider.media.read_chunk":
            data = b"abc"
            return {
                "content_reference": f"cache:{cache_reference}",
                "mime_type": "image/jpeg",
                "total_bytes": len(data),
                "offset": 0,
                "next_offset": len(data),
                "eof": True,
                "data_base64": base64.b64encode(data).decode("ascii"),
            }
        raise AssertionError(method)

    runtime.provider_operation_request = provider_request
    api = BridgeApplicationApi(config_file)
    api._runtime_registry.runtime_for_account = lambda selected: (
        runtime
        if selected == account.messenger_account_id
        else (_ for _ in ()).throw(AssertionError(selected))
    )
    try:
        assert asyncio.run(
            api._eitaa_provider_dialogs(context, None, 20)
        ).dialogs[0].peer == peer
        assert asyncio.run(
            api._eitaa_provider_history(context, peer, None, 20)
        ).messages[0].message_reference == "message:42"
        assert asyncio.run(
            api._eitaa_provider_send_text(
                context,
                ProviderSendTextRequest(
                    peer,
                    "bounded process send",
                    "process-send-key-0001",
                ),
            )
        ).message_reference == "message:43"
        media = asyncio.run(
            api._eitaa_provider_media(
                context,
                ProviderMediaReadRequest(
                    peer,
                    "message:42",
                    "media:42",
                    max_bytes=32 * 1024,
                ),
            )
        )
        assert media.content_reference == f"cache:{cache_reference}"
        assert asyncio.run(
            api._eitaa_provider_contacts(context, None, 20)
        ).contacts[0].contact_reference == "contact:42"
        identity = "+" + "1" + "0" * 7
        assert asyncio.run(
            api._eitaa_provider_contact_upsert(
                context,
                ProviderContactUpsertRequest(
                    SensitiveProviderValue.from_text(identity),
                    "Process contact",
                    "process-contact-key-0001",
                ),
            )
        ).contact_reference == "contact:43"
        assert api.read_remote_media_cache_chunk(
            cache_reference,
            messenger_account_id=account.messenger_account_id,
            offset=0,
        ) == (b"abc", "image/jpeg", 3, 3, True)
        assert [method for method, _ in calls] == [
            "eitaa.provider.dialogs.query",
            "eitaa.provider.history.query",
            "eitaa.provider.messages.send_text",
            "eitaa.provider.media.read",
            "eitaa.provider.contacts.query",
            "eitaa.provider.contacts.upsert",
            "eitaa.provider.media.read_chunk",
        ]
        assert identity not in json.dumps(api._application_logger.path.read_text())
    finally:
        api.close()


def test_eitaa_process_worker_dispatch_is_strict_typed_and_chunk_bounded():
    account_id = str(uuid4())
    worker_id = str(uuid4())
    calls: list[str] = []

    class OperationsStub:
        core_opened = False

        def list_dialogs(self, **kwargs):
            calls.append("dialogs")
            return {"dialogs": [], "next_cursor": None}

        def load_history(self, **kwargs):
            calls.append("history")
            return {"messages": [], "next_cursor": None}

        def send_text(self, **kwargs):
            calls.append("send")
            return {"status": "succeeded", "message_reference": "message:1"}

        def read_media(self, **kwargs):
            calls.append("media")
            return {
                "media_reference": "media:1",
                "content_reference": f"cache:{'b' * 32}",
                "mime_type": "image/jpeg",
                "byte_count": 3,
            }

        def read_media_chunk(self, **kwargs):
            calls.append("chunk")
            return (
                {
                    "content_reference": f"cache:{'b' * 32}",
                    "mime_type": "image/jpeg",
                    "total_bytes": 3,
                    "offset": 0,
                    "next_offset": 3,
                    "eof": True,
                },
                b"abc",
            )

        def list_contacts(self, **kwargs):
            calls.append("contacts")
            return {"contacts": [], "next_cursor": None}

        def upsert_contact(self, **kwargs):
            calls.append("upsert")
            return {"contact_reference": "contact:1", "created": True}

    worker = object.__new__(EitaaProviderProcessWorker)
    worker.messenger_account_id = account_id
    worker.runtime = object()
    worker.worker_instance_id = worker_id
    worker.worker_generation = 1
    worker._provider_operations = OperationsStub()
    worker._core_opened = False

    base = {
        "worker_instance_id": worker_id,
        "worker_generation": 1,
    }
    payloads = {
        "eitaa.provider.dialogs.query": {
            **base,
            "site_key": "medical-site",
            "cursor": None,
            "limit": 10,
        },
        "eitaa.provider.history.query": {
            **base,
            "site_key": "medical-site",
            "peer_reference": "channel:1",
            "peer_kind": "channel",
            "cursor": None,
            "limit": 10,
        },
        "eitaa.provider.messages.send_text": {
            **base,
            "site_key": "medical-site",
            "peer_reference": "channel:1",
            "peer_kind": "channel",
            "text": "bounded",
            "idempotency_key": "worker-send-key-0001",
        },
        "eitaa.provider.media.read": {
            **base,
            "site_key": "medical-site",
            "peer_reference": "channel:1",
            "message_reference": "message:1",
            "media_reference": "media:1",
            "variant": "thumbnail",
            "max_bytes": 32 * 1024,
        },
        "eitaa.provider.media.read_chunk": {
            **base,
            "cache_reference": f"cache:{'b' * 32}",
            "offset": 0,
            "max_bytes": 1024,
        },
        "eitaa.provider.contacts.query": {
            **base,
            "site_key": "medical-site",
            "cursor": None,
            "limit": 10,
        },
        "eitaa.provider.contacts.upsert": {
            **base,
            "site_key": "medical-site",
            "identity": "+10000000",
            "display_name": "Bounded",
            "idempotency_key": "worker-contact-key-0001",
        },
    }

    def envelope(method, payload):
        return IpcEnvelope(
            kind="request",
            correlation_id=str(uuid4()),
            messenger_account_id=account_id,
            provider="eitaa",
            method=method,
            deadline_unix_ms=_deadline(),
            nonce=uuid4().hex,
            payload=payload,
            key_id="synthetic",
            signature="0" * 64,
        )

    for method, payload in payloads.items():
        result = worker.dispatch(envelope(method, payload))
        if method == "eitaa.provider.media.read_chunk":
            assert base64.b64decode(result.payload["data_base64"]) == b"abc"
    assert calls == [
        "dialogs",
        "history",
        "send",
        "media",
        "chunk",
        "contacts",
        "upsert",
    ]

    forged = dict(payloads["eitaa.provider.dialogs.query"])
    forged["raw_peer"] = "forbidden"
    with pytest.raises(WorkerIpcError) as rejected:
        worker.dispatch(envelope("eitaa.provider.dialogs.query", forged))
    assert rejected.value.code == "ipc_payload_invalid"


def test_child_owned_media_broker_never_returns_a_path(config_file, tmp_path):
    media_root = tmp_path / "account" / "provider" / "media"
    media_root.mkdir(parents=True)
    cached = media_root / "bounded.bin"
    cached.write_bytes(b"abcdef")
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")
    runtime = SimpleNamespace(
        is_account_scoped=True,
        ownership=SimpleNamespace(
            core=SimpleNamespace(media_directory=media_root),
        ),
        data_scope=SimpleNamespace(scope_key="account:synthetic"),
        media_cache_lock=threading.RLock(),
        media_cache_files={},
    )
    operations = EitaaProviderRuntimeOperations(
        runtime,
        BridgeConfigLoader.load(config_file),
    )
    reference = operations._register_media_file(
        cached,
        "application/octet-stream",
    )
    metadata, data = operations.read_media_chunk(
        cache_reference=f"cache:{reference}",
        offset=1,
        max_bytes=3,
    )
    assert data == b"bcd"
    assert metadata == {
        "content_reference": f"cache:{reference}",
        "mime_type": "application/octet-stream",
        "total_bytes": 6,
        "offset": 1,
        "next_offset": 4,
        "eof": False,
    }
    assert str(media_root) not in json.dumps(metadata)
    with pytest.raises(CompositionValidationError) as escaped:
        operations._register_media_file(outside, "application/octet-stream")
    assert escaped.value.code == "api_media_cache_account_boundary"


def test_child_owned_media_broker_downloads_playable_media_only_as_full_variant(
    config_file, tmp_path
):
    account_root = tmp_path / "account"
    media_root = account_root / "provider" / "media"
    peer_file = account_root / "peers" / "channel.json"
    media_root.mkdir(parents=True)
    peer_file.parent.mkdir(parents=True)
    peer = Peer(id=77, type=PeerType.CHANNEL, access_hash=123)
    save_peer_file(peer_file, peer)
    media = MediaReference(
        MediaType.AUDIO,
        remote_id=77,
        mime_type="audio/ogg",
        file_name="voice.ogg",
    )
    message = Message(
        id=77,
        peer=peer,
        date=datetime.now(timezone.utc),
        media=media,
    )
    download_count = 0

    class Media:
        def download(self, selected, options):
            nonlocal download_count
            download_count += 1
            assert selected is media
            assert options.photo_thumb_type is None
            output = options.output_directory / f"{options.file_name}.ogg"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"synthetic-audio")
            return SimpleNamespace(path=output)

    bridge = SimpleNamespace(
        core=SimpleNamespace(
            messages=SimpleNamespace(get=lambda selected_peer, message_id: message),
            media=Media(),
        ),
        config=SimpleNamespace(core=SimpleNamespace(media_directory=media_root)),
    )
    runtime = SimpleNamespace(
        is_account_scoped=True,
        ownership=SimpleNamespace(
            installation_root=tmp_path,
            account_data_directory=account_root,
            core=SimpleNamespace(media_directory=media_root),
        ),
        data_scope=SimpleNamespace(scope_key="account:synthetic"),
        dialog_catalog=SimpleNamespace(
            get=lambda reference: {"peer_file": str(peer_file)}
        ),
        media_cache_lock=threading.RLock(),
        media_cache_files={},
        run_sync=lambda **kwargs: kwargs["callback"](),
    )
    operations = EitaaProviderRuntimeOperations(
        runtime,
        BridgeConfigLoader.load(config_file),
    )

    @contextmanager
    def open_bridge(site_key):
        assert site_key == "medical-site"
        yield bridge

    operations._open_bridge = open_bridge
    receipt = operations.read_media(
        site_key="medical-site",
        peer_reference="channel:77",
        message_reference="message:77",
        media_reference="media:77",
        variant="full",
        max_bytes=512 * 1024 * 1024,
    )
    assert receipt["mime_type"] == "audio/ogg"
    assert receipt["byte_count"] == len(b"synthetic-audio")
    assert str(receipt["content_reference"]).startswith("cache:")
    assert download_count == 1

    with pytest.raises(CompositionValidationError) as rejected:
        operations.read_media(
            site_key="medical-site",
            peer_reference="channel:77",
            message_reference="message:77",
            media_reference="media:77",
            variant="thumbnail",
            max_bytes=16 * 1024 * 1024,
        )
    assert rejected.value.code == "provider_media_not_found"
    assert download_count == 1
