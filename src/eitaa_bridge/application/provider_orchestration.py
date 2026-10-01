"""Provider-neutral application orchestration for bounded messaging operations.

The orchestrator owns the security-sensitive order of execution.  Provider
translation and transport remain behind ``ProviderAdapter`` implementations;
the application layer never selects behavior by comparing provider names.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import hashlib
import threading
import time
from typing import Any, Protocol, TypeVar

from ..errors import BridgeError, ProviderExtensionError
from ..infrastructure.coordinator.rate_policy import (
    ClassifiedFailure,
    ExecutionErrorClass,
    classify_failure,
)
from ..infrastructure.diagnostics import RuntimeLogger
from ..providers.contracts import (
    ProviderAccountContext,
    ProviderAdapter,
    ProviderCapability,
    ProviderContactAdapter,
    ProviderContactMutationReceipt,
    ProviderContactPage,
    ProviderContactUpsertRequest,
    ProviderContactRemoveRequest,
    ProviderContactRemovalAdapter,
    ProviderDialogPage,
    ProviderMessagePage,
    ProviderMediaAdapter,
    ProviderMediaReadReceipt,
    ProviderMediaReadRequest,
    ProviderOperationContext,
    ProviderPeerReference,
    ProviderSendReceipt,
    ProviderSendStatus,
    ProviderSendTextRequest,
    ProviderSendMediaRequest,
    ProviderMediaSendAdapter,
)


@dataclass(frozen=True, slots=True)
class ProviderOperationActor:
    """Server-authenticated actor metadata; never constructed from request bodies."""

    app_user_id: str
    global_role: str
    service_credential_id: str | None = None

    def __post_init__(self) -> None:
        if not str(self.app_user_id or "").strip():
            raise ProviderExtensionError(
                "The provider operation actor is unavailable.",
                code="provider_operation_actor_required",
            )
        if str(self.global_role or "").strip().lower() not in {"admin", "user"}:
            raise ProviderExtensionError(
                "The provider operation actor role is invalid.",
                code="provider_operation_actor_invalid",
            )
        if self.service_credential_id is not None and not str(self.service_credential_id).strip():
            raise ProviderExtensionError(
                "The provider operation actor service binding is invalid.",
                code="provider_operation_actor_invalid",
            )


class ProviderAccountAuthorizer(Protocol):
    def __call__(
        self,
        actor: ProviderOperationActor,
        messenger_account_id: str,
        operation: str,
    ) -> None: ...


class ProviderAccountContextResolver(Protocol):
    def __call__(self, messenger_account_id: str) -> ProviderAccountContext: ...


class ProviderCapabilityAuthorizer(Protocol):
    def __call__(
        self,
        messenger_account_id: str,
        capability: ProviderCapability,
    ) -> object: ...


class ProviderOperationAdapterResolver(Protocol):
    def __call__(self, account: ProviderAccountContext) -> ProviderAdapter: ...


class ProviderOperationReceiptRecord(Protocol):
    actor_app_user_id: str
    request_fingerprint: str
    outcome: str
    result_reference: str | None
    contact_created: bool | None
    safe_reason_code: str | None
    claim_deadline_unix_ms: int


class ProviderOperationClaim(Protocol):
    receipt: ProviderOperationReceiptRecord
    claimed: bool


class ProviderOperationReceiptBackend(Protocol):
    def claim(
        self,
        *,
        messenger_account_id: str,
        actor_app_user_id: str,
        actor_global_role: str,
        operation: str,
        idempotency_key: str,
        request_fingerprint: str,
        claim_deadline_unix_ms: int,
    ) -> ProviderOperationClaim: ...

    def complete(
        self,
        *,
        messenger_account_id: str,
        actor_app_user_id: str,
        operation: str,
        idempotency_key: str,
        request_fingerprint: str,
        outcome: str,
        result_reference: str | None,
        contact_created: bool | None,
        safe_reason_code: str | None,
    ) -> ProviderOperationReceiptRecord: ...


@dataclass(frozen=True, slots=True)
class _CachedMutationReceipt:
    actor_app_user_id: str
    request_fingerprint: str
    receipt: ProviderSendReceipt | ProviderContactMutationReceipt
    service_credential_id: str | None = None


def _request_fingerprint(*parts: bytes) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(len(part).to_bytes(8, "big"))
        digest.update(part)
    return digest.hexdigest()


_ResultT = TypeVar("_ResultT")


class ProviderApplicationOrchestrator:
    """Execute public provider operations in one fail-closed application path."""

    def __init__(
        self,
        *,
        authorize_account: ProviderAccountAuthorizer,
        resolve_account_context: ProviderAccountContextResolver,
        require_capability: ProviderCapabilityAuthorizer,
        resolve_adapter: ProviderOperationAdapterResolver,
        logger: RuntimeLogger,
        receipt_store: ProviderOperationReceiptBackend | None = None,
        execution_policy: Any | None = None,
    ) -> None:
        self._authorize_account = authorize_account
        self._resolve_account_context = resolve_account_context
        self._require_capability = require_capability
        self._resolve_adapter = resolve_adapter
        self._logger = logger
        self._receipt_store = receipt_store
        # Optional local execution policy (P2): the single owner of the
        # account token bucket. Admission happens only for fresh mutation
        # attempts — a replay returns before this point and never consumes
        # a token; the caller (composition root) wires the concrete service.
        self._execution_policy = execution_policy
        self._send_lock = threading.RLock()
        self._send_receipts: dict[
            tuple[str, str], _CachedMutationReceipt
        ] = {}
        self._send_in_progress: dict[tuple[str, str], tuple[str, str]] = {}
        self._contact_receipts: dict[
            tuple[str, str], _CachedMutationReceipt
        ] = {}
        self._contact_in_progress: dict[
            tuple[str, str], tuple[str, str]
        ] = {}

    def _emit_idempotency_interrupted(
        self,
        *,
        context: ProviderOperationContext,
        operation: str,
        reason_code: str,
    ) -> None:
        self._logger.emit(
            "provider_operation_idempotency_interrupted",
            level="warning",
            result="uncertain",
            reason_code=reason_code,
            correlation_id=context.correlation_id,
            operation=operation,
            fields={
                "messenger_account_id": context.account.messenger_account_id,
                "provider": context.account.provider,
            },
        )

    def _admit_execution(
        self,
        *,
        messenger_account_id: str,
        operation: str,
    ) -> Any | None:
        """Acquire one local execution token for a fresh mutation attempt.

        Called only after the idempotency decision proved this request owns
        the first attempt; replays return earlier and never consume a token.
        Local admission is not a provider or capacity guarantee — the
        provider can still refuse later.
        """
        if self._execution_policy is None:
            return None
        permit = self._execution_policy.acquire(
            messenger_account_id=str(messenger_account_id),
            operation_scope=operation,
        )
        if permit.allowed:
            return permit
        retry_after_seconds = (
            max(1, -(-int(permit.retry_after_ms) // 1000))
            if permit.retry_after_ms
            else None
        )
        raise ProviderExtensionError(
            "Local execution policy denied the provider operation.",
            safe_context={
                "messenger_account_id": str(messenger_account_id),
                "operation_scope": operation,
                "blocked_reason": permit.blocked_reason,
                "retry_after_seconds": retry_after_seconds,
            },
            code=(
                "provider_operation_circuit_open"
                if permit.blocked_reason == "circuit_manual_reset_required"
                else "provider_operation_rate_limited"
            ),
        )

    def _record_execution_success(
        self,
        *,
        messenger_account_id: str,
        operation: str,
        permit: Any | None,
        outcome: str,
    ) -> None:
        if self._execution_policy is None or permit is None:
            return
        try:
            if outcome == "succeeded":
                self._execution_policy.record_success(
                    messenger_account_id=str(messenger_account_id),
                    operation_scope=operation,
                    claim_id=permit.claim_id,
                )
            else:
                self._execution_policy.record_failure(
                    messenger_account_id=str(messenger_account_id),
                    operation_scope=operation,
                    claim_id=permit.claim_id,
                failure=ClassifiedFailure(
                    ExecutionErrorClass.UNCERTAIN,
                    "provider_send_uncertain",
                    None,
                ),
                )
        except Exception:
            # Policy bookkeeping must never mask the operation result or the
            # durable receipt; the next acquire recomputes from persisted state.
            self._logger.emit(
                "provider_operation_failed",
                level="warning",
                result="failed",
                reason_code="execution_policy_record_failed",
                fields={
                    "messenger_account_id": str(messenger_account_id),
                    "operation_scope": operation,
                },
            )

    def _record_execution_exception(
        self,
        *,
        messenger_account_id: str,
        operation: str,
        permit: Any | None,
        error: BaseException,
    ) -> None:
        policy = self._execution_policy
        if policy is None or permit is None:
            return
        code = str(getattr(error, "code", "") or "provider_send_failed")
        try:
            policy.record_failure(
                messenger_account_id=str(messenger_account_id),
                operation_scope=operation,
                claim_id=permit.claim_id,
                failure=classify_failure(code, effect_may_have_occurred=True),
            )
        except Exception:
            # Never mask the real operation failure with a bookkeeping error.
            self._logger.emit(
                "provider_operation_failed",
                level="warning",
                result="failed",
                reason_code="execution_policy_record_failed",
                operation=operation,
                fields={"messenger_account_id": str(messenger_account_id)},
            )

    def _release_claim_safely(
        self,
        *,
        actor: ProviderOperationActor,
        messenger_account_id: str,
        operation: str,
        idempotency_key: str,
        request_fingerprint: str,
        attempt_token: str | None = None,
    ) -> None:
        """Owner-fenced release of the durable claim of an attempt that
        certainly never started (admission denied). Bookkeeping failures are
        logged, never allowed to mask the denial itself."""
        if self._receipt_store is None:
            return
        try:
            self._receipt_store.release(
                messenger_account_id=str(messenger_account_id),
                actor_app_user_id=actor.app_user_id,
                operation=operation,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                service_credential_id=actor.service_credential_id,
                attempt_token=attempt_token,
            )
        except Exception:
            self._logger.emit(
                "provider_operation_failed",
                level="warning",
                result="failed",
                reason_code="provider_claim_release_failed",
                operation=operation,
                fields={"messenger_account_id": str(messenger_account_id)},
            )

    def _emit_idempotency_replayed(
        self,
        *,
        context: ProviderOperationContext,
        operation: str,
        outcome: str,
        source: str,
    ) -> None:
        self._logger.emit(
            "provider_operation_idempotency_replayed",
            result="succeeded",
            correlation_id=context.correlation_id,
            operation=operation,
            fields={
                "messenger_account_id": context.account.messenger_account_id,
                "provider": context.account.provider,
                "outcome": outcome,
                "receipt_source": source,
            },
        )

    def _emit_idempotency_interrupted(
        self,
        *,
        context: ProviderOperationContext,
        operation: str,
        reason_code: str,
    ) -> None:
        self._logger.emit(
            "provider_operation_idempotency_interrupted",
            level="warning",
            result="uncertain",
            reason_code=reason_code,
            correlation_id=context.correlation_id,
            operation=operation,
            fields={
                "messenger_account_id": context.account.messenger_account_id,
                "provider": context.account.provider,
            },
        )

    async def list_dialogs(
        self,
        *,
        actor: ProviderOperationActor,
        messenger_account_id: str,
        correlation_id: str,
        deadline_unix_ms: int,
        cursor: str | None = None,
        limit: int = 100,
    ) -> ProviderDialogPage:
        if isinstance(limit, bool) or not 1 <= int(limit) <= 200:
            raise ProviderExtensionError(
                "The provider dialog page limit is invalid.",
                code="provider_operation_limit_invalid",
            )

        async def invoke(
            adapter: ProviderAdapter,
            context: ProviderOperationContext,
        ) -> ProviderDialogPage:
            return await adapter.list_dialogs(context, cursor=cursor, limit=int(limit))

        return await self._execute(
            actor=actor,
            messenger_account_id=messenger_account_id,
            correlation_id=correlation_id,
            deadline_unix_ms=deadline_unix_ms,
            operation="dialogs.list",
            capability=ProviderCapability.DIALOGS_READ,
            expected_type=ProviderDialogPage,
            invoke=invoke,
        )

    @staticmethod
    def _require_idempotency_match(
        *,
        stored_actor: str,
        stored_fingerprint: str,
        actor: ProviderOperationActor,
        request_fingerprint: str,
        stored_service_credential_id: str | None = None,
    ) -> None:
        if stored_actor != actor.app_user_id:
            raise ProviderExtensionError(
                "The provider idempotency key belongs to another AppUser.",
                code="provider_idempotency_owner_mismatch",
            )
        if stored_fingerprint != request_fingerprint:
            raise ProviderExtensionError(
                "The provider idempotency key belongs to another request.",
                code="provider_idempotency_payload_mismatch",
            )
        if (stored_service_credential_id or None) != (actor.service_credential_id or None):
            # Another service (or a legacy owner-less receipt) must never be
            # replayed or completed under this service's credential.
            raise ProviderExtensionError(
                "The provider idempotency key belongs to another service.",
                code="provider_idempotency_owner_mismatch",
            )

    @staticmethod
    def _send_receipt_from_record(
        record: ProviderOperationReceiptRecord,
    ) -> ProviderSendReceipt:
        if record.outcome == "succeeded":
            return ProviderSendReceipt(
                ProviderSendStatus.SUCCEEDED,
                message_reference=record.result_reference,
                safe_reason_code=record.safe_reason_code,
            )
        if record.outcome == "uncertain":
            return ProviderSendReceipt(
                ProviderSendStatus.UNCERTAIN,
                message_reference=record.result_reference,
                safe_reason_code=record.safe_reason_code,
            )
        raise ProviderExtensionError(
            "The provider send has an incomplete previous attempt.",
            code="provider_operation_previous_attempt_incomplete",
        )

    @staticmethod
    def _contact_receipt_from_record(
        record: ProviderOperationReceiptRecord,
    ) -> ProviderContactMutationReceipt:
        if (
            record.outcome != "succeeded"
            or record.result_reference is None
            or not isinstance(record.contact_created, bool)
        ):
            raise ProviderExtensionError(
                "The provider contact mutation has an incomplete previous attempt.",
                code="provider_operation_previous_attempt_incomplete",
            )
        return ProviderContactMutationReceipt(
            record.result_reference,
            record.contact_created,
        )

    async def load_history(
        self,
        *,
        actor: ProviderOperationActor,
        messenger_account_id: str,
        correlation_id: str,
        deadline_unix_ms: int,
        peer: ProviderPeerReference,
        cursor: str | None = None,
        limit: int = 100,
    ) -> ProviderMessagePage:
        if isinstance(limit, bool) or not 1 <= int(limit) <= 500:
            raise ProviderExtensionError(
                "The provider message page limit is invalid.",
                code="provider_operation_limit_invalid",
            )

        async def invoke(
            adapter: ProviderAdapter,
            context: ProviderOperationContext,
        ) -> ProviderMessagePage:
            return await adapter.load_history(
                context,
                peer=peer,
                cursor=cursor,
                limit=int(limit),
            )

        return await self._execute(
            actor=actor,
            messenger_account_id=messenger_account_id,
            correlation_id=correlation_id,
            deadline_unix_ms=deadline_unix_ms,
            operation="history.list",
            capability=ProviderCapability.HISTORY_READ,
            expected_type=ProviderMessagePage,
            invoke=invoke,
        )

    async def send_text(
        self,
        *,
        actor: ProviderOperationActor,
        messenger_account_id: str,
        correlation_id: str,
        deadline_unix_ms: int,
        request: ProviderSendTextRequest,
        skip_admission: bool = False,
    ) -> ProviderSendReceipt:
        key = (str(messenger_account_id), request.idempotency_key)
        request_fingerprint = _request_fingerprint(
            b"messages.send_text",
            request.peer.opaque_reference.encode("utf-8"),
            request.peer.kind.encode("utf-8"),
            request.text.encode("utf-8"),
        )

        async def invoke(
            adapter: ProviderAdapter,
            context: ProviderOperationContext,
        ) -> ProviderSendReceipt:
            with self._send_lock:
                completed = self._send_receipts.get(key)
                if completed is not None:
                    self._require_idempotency_match(
                        stored_actor=completed.actor_app_user_id,
                        stored_fingerprint=completed.request_fingerprint,
                        stored_service_credential_id=completed.service_credential_id,
                        actor=actor,
                        request_fingerprint=request_fingerprint,
                    )
                    if not isinstance(completed.receipt, ProviderSendReceipt):
                        raise ProviderExtensionError(
                            "The provider send receipt cache is invalid.",
                            code="provider_operation_result_invalid",
                        )
                    self._emit_idempotency_replayed(
                        context=context,
                        operation="messages.send_text",
                        outcome=completed.receipt.status.value,
                        source="memory",
                    )
                    return completed.receipt
                in_progress = self._send_in_progress.get(key)
                if in_progress is not None:
                    self._require_idempotency_match(
                        stored_actor=in_progress[0],
                        stored_fingerprint=in_progress[1],
                        stored_service_credential_id=in_progress[2],
                        actor=actor,
                        request_fingerprint=request_fingerprint,
                    )
                    raise ProviderExtensionError(
                        "The provider send is already in progress.",
                        safe_context={
                            "messenger_account_id": str(messenger_account_id)
                        },
                        code="provider_operation_duplicate_in_progress",
                    )
                current_attempt_token: str | None = None
                if self._receipt_store is not None:
                    claim = self._receipt_store.claim(
                        messenger_account_id=str(messenger_account_id),
                        actor_app_user_id=actor.app_user_id,
                        actor_global_role=actor.global_role,
                        service_credential_id=actor.service_credential_id,
                        operation="messages.send_text",
                        idempotency_key=request.idempotency_key,
                        request_fingerprint=request_fingerprint,
                        claim_deadline_unix_ms=context.deadline_unix_ms,
                    )
                    current_attempt_token = claim.receipt.attempt_token
                    if not claim.claimed:
                        record = claim.receipt
                        self._require_idempotency_match(
                            stored_actor=record.actor_app_user_id,
                            stored_fingerprint=record.request_fingerprint,
                            stored_service_credential_id=record.service_credential_id,
                            actor=actor,
                            request_fingerprint=request_fingerprint,
                        )
                        if record.outcome == "in_progress":
                            if record.claim_deadline_unix_ms >= int(time.time() * 1000):
                                raise ProviderExtensionError(
                                    "The provider send is already in progress.",
                                    code="provider_operation_duplicate_in_progress",
                                )
                            record = self._receipt_store.complete(
                                messenger_account_id=str(messenger_account_id),
                                actor_app_user_id=actor.app_user_id,
                                operation="messages.send_text",
                                idempotency_key=request.idempotency_key,
                                request_fingerprint=request_fingerprint,
                                service_credential_id=actor.service_credential_id,
                                outcome="uncertain",
                                result_reference=None,
                                contact_created=None,
                                safe_reason_code=(
                                    "provider_send_previous_attempt_incomplete"
                                ),
                                attempt_token=record.attempt_token,
                            )
                            self._emit_idempotency_interrupted(
                                context=context,
                                operation="messages.send_text",
                                reason_code=(
                                    "provider_send_previous_attempt_incomplete"
                                ),
                            )
                        replay = self._send_receipt_from_record(record)
                        self._emit_idempotency_replayed(
                            context=context,
                            operation="messages.send_text",
                            outcome=record.outcome,
                            source="persistent",
                        )
                        self._send_receipts[key] = _CachedMutationReceipt(
                            actor.app_user_id,
                            request_fingerprint,
                            replay,
                            service_credential_id=actor.service_credential_id,
                        )
                        return replay
                self._send_in_progress[key] = (
                    actor.app_user_id,
                    request_fingerprint,
                    actor.service_credential_id,
                )
            # P2/P3-R1 admission: only this fresh attempt pays a local token;
            # the replay paths above returned before this point. Every
            # pre-adapter exit — admission denial, circuit denial, cancel —
            # resolves THIS attempt's ownership below: the in-memory entry
            # pops in the finally and the durable claim is released with the
            # owner fence, so no uncertain claim can linger for an operation
            # that certainly never started.
            send_permit = None
            admitted = False
            try:
                if not skip_admission:
                    send_permit = self._admit_execution(
                        messenger_account_id=str(messenger_account_id),
                        operation="messages.send_text",
                    )
                admitted = True
                receipt = await adapter.send_text(context, request)
                # Both succeeded and uncertain receipts are terminal.  In
                # particular, an uncertain external effect must never be retried.
                if self._receipt_store is not None:
                    self._receipt_store.complete(
                        messenger_account_id=str(messenger_account_id),
                        actor_app_user_id=actor.app_user_id,
                        operation="messages.send_text",
                        idempotency_key=request.idempotency_key,
                        request_fingerprint=request_fingerprint,
                        service_credential_id=actor.service_credential_id,
                        outcome=receipt.status.value,
                        result_reference=receipt.message_reference,
                        contact_created=None,
                        safe_reason_code=receipt.safe_reason_code,
                        attempt_token=current_attempt_token,
                    )
                with self._send_lock:
                    self._send_receipts[key] = _CachedMutationReceipt(
                        actor.app_user_id,
                        request_fingerprint,
                        receipt,
                        service_credential_id=actor.service_credential_id,
                    )
                    if len(self._send_receipts) > 2048:
                        self._send_receipts.pop(next(iter(self._send_receipts)))
                if send_permit is not None:
                    self._record_execution_success(
                        messenger_account_id=str(messenger_account_id),
                        operation="messages.send_text",
                        permit=send_permit,
                        outcome=receipt.status.value,
                    )
                return receipt
            except BaseException as exc:
                if not admitted:
                    self._release_claim_safely(
                        actor=actor,
                        messenger_account_id=str(messenger_account_id),
                        operation="messages.send_text",
                        idempotency_key=request.idempotency_key,
                        request_fingerprint=request_fingerprint,
                        attempt_token=current_attempt_token,
                    )
                else:
                    self._record_execution_exception(
                        messenger_account_id=str(messenger_account_id),
                        operation="messages.send_text",
                        permit=send_permit,
                        error=exc,
                    )
                raise
            finally:
                with self._send_lock:
                    self._send_in_progress.pop(key, None)

        return await self._execute(
            actor=actor,
            messenger_account_id=messenger_account_id,
            correlation_id=correlation_id,
            deadline_unix_ms=deadline_unix_ms,
            operation="messages.send_text",
            capability=ProviderCapability.MESSAGES_SEND,
            expected_type=ProviderSendReceipt,
            invoke=invoke,
        )

    async def read_media(
        self,
        *,
        actor: ProviderOperationActor,
        messenger_account_id: str,
        correlation_id: str,
        deadline_unix_ms: int,
        request: ProviderMediaReadRequest,
    ) -> ProviderMediaReadReceipt:
        async def invoke(
            adapter: ProviderAdapter,
            context: ProviderOperationContext,
        ) -> ProviderMediaReadReceipt:
            if not isinstance(adapter, ProviderMediaAdapter):
                raise ProviderExtensionError(
                    "The provider media operation is not implemented.",
                    code="provider_media_operation_not_implemented",
                )
            receipt = await adapter.read_media(context, request)
            if receipt.byte_count > request.max_bytes:
                raise ProviderExtensionError(
                    "The provider media result exceeds the requested byte limit.",
                    code="provider_media_limit_exceeded",
                )
            return receipt

        return await self._execute(
            actor=actor,
            messenger_account_id=messenger_account_id,
            correlation_id=correlation_id,
            deadline_unix_ms=deadline_unix_ms,
            operation="media.read",
            capability=ProviderCapability.MEDIA_READ,
            expected_type=ProviderMediaReadReceipt,
            invoke=invoke,
        )

    async def list_contacts(
        self,
        *,
        actor: ProviderOperationActor,
        messenger_account_id: str,
        correlation_id: str,
        deadline_unix_ms: int,
        cursor: str | None = None,
        limit: int = 100,
    ) -> ProviderContactPage:
        if isinstance(limit, bool) or not 1 <= int(limit) <= 500:
            raise ProviderExtensionError(
                "The provider contact page limit is invalid.",
                code="provider_operation_limit_invalid",
            )

        async def invoke(
            adapter: ProviderAdapter,
            context: ProviderOperationContext,
        ) -> ProviderContactPage:
            if not isinstance(adapter, ProviderContactAdapter):
                raise ProviderExtensionError(
                    "The provider contact operation is not implemented.",
                    code="provider_contact_operation_not_implemented",
                )
            return await adapter.list_contacts(
                context,
                cursor=cursor,
                limit=int(limit),
            )

        return await self._execute(
            actor=actor,
            messenger_account_id=messenger_account_id,
            correlation_id=correlation_id,
            deadline_unix_ms=deadline_unix_ms,
            operation="contacts.list",
            capability=ProviderCapability.CONTACTS_READ,
            expected_type=ProviderContactPage,
            invoke=invoke,
        )

    async def upsert_contact(
        self,
        *,
        actor: ProviderOperationActor,
        messenger_account_id: str,
        correlation_id: str,
        deadline_unix_ms: int,
        request: ProviderContactUpsertRequest,
    ) -> ProviderContactMutationReceipt:
        key = (str(messenger_account_id), request.idempotency_key)
        request_fingerprint = _request_fingerprint(
            b"contacts.upsert",
            request.identity.reveal_bytes(),
            request.display_name.encode("utf-8"),
        )

        async def invoke(
            adapter: ProviderAdapter,
            context: ProviderOperationContext,
        ) -> ProviderContactMutationReceipt:
            if not isinstance(adapter, ProviderContactAdapter):
                raise ProviderExtensionError(
                    "The provider contact mutation is not implemented.",
                    code="provider_contact_operation_not_implemented",
                )
            with self._send_lock:
                completed = self._contact_receipts.get(key)
                if completed is not None:
                    self._require_idempotency_match(
                        stored_actor=completed.actor_app_user_id,
                        stored_fingerprint=completed.request_fingerprint,
                        stored_service_credential_id=completed.service_credential_id,
                        actor=actor,
                        request_fingerprint=request_fingerprint,
                    )
                    if not isinstance(
                        completed.receipt,
                        ProviderContactMutationReceipt,
                    ):
                        raise ProviderExtensionError(
                            "The provider contact receipt cache is invalid.",
                            code="provider_operation_result_invalid",
                        )
                    self._emit_idempotency_replayed(
                        context=context,
                        operation="contacts.upsert",
                        outcome="succeeded",
                        source="memory",
                    )
                    return completed.receipt
                in_progress = self._contact_in_progress.get(key)
                if in_progress is not None:
                    self._require_idempotency_match(
                        stored_actor=in_progress[0],
                        stored_fingerprint=in_progress[1],
                        stored_service_credential_id=in_progress[2],
                        actor=actor,
                        request_fingerprint=request_fingerprint,
                    )
                    raise ProviderExtensionError(
                        "The provider contact mutation is already in progress.",
                        safe_context={
                            "messenger_account_id": str(messenger_account_id)
                        },
                        code="provider_operation_duplicate_in_progress",
                    )
                current_attempt_token: str | None = None
                if self._receipt_store is not None:
                    claim = self._receipt_store.claim(
                        messenger_account_id=str(messenger_account_id),
                        actor_app_user_id=actor.app_user_id,
                        actor_global_role=actor.global_role,
                        service_credential_id=actor.service_credential_id,
                        operation="contacts.upsert",
                        idempotency_key=request.idempotency_key,
                        request_fingerprint=request_fingerprint,
                        claim_deadline_unix_ms=context.deadline_unix_ms,
                    )
                    current_attempt_token = claim.receipt.attempt_token
                    if not claim.claimed:
                        record = claim.receipt
                        self._require_idempotency_match(
                            stored_actor=record.actor_app_user_id,
                            stored_fingerprint=record.request_fingerprint,
                            stored_service_credential_id=record.service_credential_id,
                            actor=actor,
                            request_fingerprint=request_fingerprint,
                        )
                        if record.outcome == "in_progress":
                            if record.claim_deadline_unix_ms >= int(time.time() * 1000):
                                raise ProviderExtensionError(
                                    "The provider contact mutation is already in progress.",
                                    code="provider_operation_duplicate_in_progress",
                                )
                            record = self._receipt_store.complete(
                                messenger_account_id=str(messenger_account_id),
                                actor_app_user_id=actor.app_user_id,
                                operation="contacts.upsert",
                                idempotency_key=request.idempotency_key,
                                request_fingerprint=request_fingerprint,
                                service_credential_id=actor.service_credential_id,
                                outcome="uncertain",
                                result_reference=None,
                                contact_created=None,
                                safe_reason_code=(
                                    "provider_contact_previous_attempt_incomplete"
                                ),
                                attempt_token=record.attempt_token,
                            )
                        if record.outcome == "uncertain":
                            self._emit_idempotency_interrupted(
                                context=context,
                                operation="contacts.upsert",
                                reason_code=(
                                    record.safe_reason_code
                                    or "provider_contact_previous_attempt_incomplete"
                                ),
                            )
                        replay = self._contact_receipt_from_record(record)
                        self._emit_idempotency_replayed(
                            context=context,
                            operation="contacts.upsert",
                            outcome=record.outcome,
                            source="persistent",
                        )
                        self._contact_receipts[key] = _CachedMutationReceipt(
                            actor.app_user_id,
                            request_fingerprint,
                            replay,
                            service_credential_id=actor.service_credential_id,
                        )
                        return replay
                self._contact_in_progress[key] = (
                    actor.app_user_id,
                    request_fingerprint,
                    actor.service_credential_id,
                )
            # P3-R2: a fresh contact import pays the same local policy as any
            # other mutation (its own operation scope); every pre-adapter
            # exit resolves this attempt's ownership.
            upsert_permit = None
            admitted = False
            try:
                upsert_permit = self._admit_execution(
                    messenger_account_id=str(messenger_account_id),
                    operation="contacts.upsert",
                )
                admitted = True
                receipt = await adapter.upsert_contact(context, request)
                if self._receipt_store is not None:
                    self._receipt_store.complete(
                        messenger_account_id=str(messenger_account_id),
                        actor_app_user_id=actor.app_user_id,
                        operation="contacts.upsert",
                        idempotency_key=request.idempotency_key,
                        request_fingerprint=request_fingerprint,
                        service_credential_id=actor.service_credential_id,
                        outcome="succeeded",
                        result_reference=receipt.contact_reference,
                        contact_created=receipt.created,
                        safe_reason_code=None,
                        attempt_token=current_attempt_token,
                    )
                with self._send_lock:
                    self._contact_receipts[key] = _CachedMutationReceipt(
                        actor.app_user_id,
                        request_fingerprint,
                        receipt,
                        service_credential_id=actor.service_credential_id,
                    )
                    if len(self._contact_receipts) > 2048:
                        self._contact_receipts.pop(next(iter(self._contact_receipts)))
                self._record_execution_success(
                    messenger_account_id=str(messenger_account_id),
                    operation="contacts.upsert",
                    permit=upsert_permit,
                    outcome="succeeded",
                )
                return receipt
            except BaseException as exc:
                if not admitted:
                    self._release_claim_safely(
                        actor=actor,
                        messenger_account_id=str(messenger_account_id),
                        operation="contacts.upsert",
                        idempotency_key=request.idempotency_key,
                        request_fingerprint=request_fingerprint,
                        attempt_token=current_attempt_token,
                    )
                else:
                    self._record_execution_exception(
                        messenger_account_id=str(messenger_account_id),
                        operation="contacts.upsert",
                        permit=upsert_permit,
                        error=exc,
                    )
                raise
            finally:
                with self._send_lock:
                    self._contact_in_progress.pop(key, None)

        return await self._execute(
            actor=actor,
            messenger_account_id=messenger_account_id,
            correlation_id=correlation_id,
            deadline_unix_ms=deadline_unix_ms,
            operation="contacts.upsert",
            capability=ProviderCapability.CONTACTS_WRITE,
            expected_type=ProviderContactMutationReceipt,
            invoke=invoke,
        )

    async def _extension_mutation(self, *, actor, messenger_account_id, correlation_id,
                                  deadline_unix_ms, request, operation, capability,
                                  protocol, method, fingerprint, expected_type):
        """Version 2 mutations use the same durable claims and authorization order."""
        async def invoke(adapter, context):
            if not isinstance(adapter, protocol):
                raise ProviderExtensionError("Unsupported provider mutation.", code="provider_operation_not_implemented")
            if self._receipt_store is None:
                raise ProviderExtensionError("Persistent receipt storage required.", code="provider_receipt_store_required")
            args = dict(messenger_account_id=messenger_account_id,
                        actor_app_user_id=actor.app_user_id, operation=operation,
                        idempotency_key=request.idempotency_key,
                        request_fingerprint=fingerprint, service_credential_id=actor.service_credential_id)
            claim = self._receipt_store.claim(**args, actor_global_role=actor.global_role,
                                              claim_deadline_unix_ms=context.deadline_unix_ms)
            current_attempt_token = claim.receipt.attempt_token
            if not claim.claimed:
                record = claim.receipt
                self._require_idempotency_match(
                    stored_actor=record.actor_app_user_id, stored_fingerprint=record.request_fingerprint,
                    stored_service_credential_id=record.service_credential_id,
                    actor=actor, request_fingerprint=fingerprint)
                if record.outcome == "in_progress":
                    if record.claim_deadline_unix_ms >= int(time.time() * 1000):
                        raise ProviderExtensionError("Mutation in progress.", code="provider_operation_duplicate_in_progress")
                    record = self._receipt_store.complete(**args, outcome="uncertain", result_reference=None,
                        contact_created=None, safe_reason_code="provider_operation_previous_attempt_incomplete",
                        attempt_token=record.attempt_token)
                return (self._send_receipt_from_record(record) if expected_type is ProviderSendReceipt
                        else self._contact_receipt_from_record(record))
            # Claim survives failure, cancellation or a process crash. A replay never
            # repeats an external mutation whose result might have been lost.
            # P3-R1: every pre-adapter exit resolves this attempt's ownership.
            # Admission denial releases the durable claim with the owner fence
            # so the id stays usable and no uncertain claim lingers for an
            # operation that certainly never started.
            mutation_permit = None
            admitted = False
            try:
                mutation_permit = self._admit_execution(
                    messenger_account_id=str(messenger_account_id),
                    operation=operation,
                )
                admitted = True
                receipt = await getattr(adapter, method)(context, request)
            except BaseException as exc:
                if not admitted:
                    self._release_claim_safely(
                        actor=actor,
                        messenger_account_id=str(messenger_account_id),
                        operation=operation,
                        idempotency_key=request.idempotency_key,
                        request_fingerprint=fingerprint,
                        attempt_token=current_attempt_token,
                    )
                else:
                    self._record_execution_exception(
                        messenger_account_id=str(messenger_account_id),
                        operation=operation,
                        permit=mutation_permit,
                        error=exc,
                    )
                raise
            send = isinstance(receipt, ProviderSendReceipt)
            self._receipt_store.complete(**args,
                outcome=receipt.status.value if send else "succeeded",
                result_reference=receipt.message_reference if send else receipt.contact_reference,
                contact_created=None if send else receipt.created,
                safe_reason_code=receipt.safe_reason_code if send else None,
                attempt_token=current_attempt_token)
            self._record_execution_success(
                messenger_account_id=str(messenger_account_id),
                operation=operation,
                permit=mutation_permit,
                outcome=receipt.status.value if send else "succeeded",
            )
            return receipt
        return await self._execute(actor=actor, messenger_account_id=messenger_account_id,
            correlation_id=correlation_id, deadline_unix_ms=deadline_unix_ms,
            operation=operation, capability=capability, expected_type=expected_type, invoke=invoke)

    async def remove_contact(self, *, request: ProviderContactRemoveRequest, **kwargs):
        return await self._extension_mutation(**kwargs, request=request,
            operation="contacts.remove", capability=ProviderCapability.CONTACTS_WRITE,
            protocol=ProviderContactRemovalAdapter, method="remove_contact",
            fingerprint=_request_fingerprint(b"contacts.remove", request.contact_reference.encode()),
            expected_type=ProviderContactMutationReceipt)

    async def send_media(self, *, request: ProviderSendMediaRequest, **kwargs):
        return await self._extension_mutation(**kwargs, request=request,
            operation="messages.send_media", capability=ProviderCapability.MEDIA_SEND,
            protocol=ProviderMediaSendAdapter, method="send_media",
            fingerprint=_request_fingerprint(b"messages.send_media", request.peer.opaque_reference.encode(),
                request.peer.kind.encode(), request.filename.encode(), request.data, request.caption.encode()),
            expected_type=ProviderSendReceipt)

    async def _execute(
        self,
        *,
        actor: ProviderOperationActor,
        messenger_account_id: str,
        correlation_id: str,
        deadline_unix_ms: int,
        operation: str,
        capability: ProviderCapability,
        expected_type: type[_ResultT],
        invoke: Callable[
            [ProviderAdapter, ProviderOperationContext], Awaitable[_ResultT]
        ],
    ) -> _ResultT:
        started = time.monotonic()
        adapter: ProviderAdapter | None = None
        account: ProviderAccountContext | None = None
        try:
            # The order below is part of the security contract and is covered by
            # Phase 11-B2 tests.  Adapter resolution must never precede access or
            # capability checks.
            self._authorize_account(actor, messenger_account_id, "operate")
            account = self._resolve_account_context(messenger_account_id)
            if account.messenger_account_id != str(messenger_account_id):
                raise ProviderExtensionError(
                    "The provider operation account scope changed.",
                    code="provider_extension_scope_invalid",
                )
            self._require_capability(messenger_account_id, capability)
            context = ProviderOperationContext(
                account=account,
                correlation_id=correlation_id,
                deadline_unix_ms=deadline_unix_ms,
            )
            context.require_live_deadline()
            adapter = self._resolve_adapter(account)
            manifest = adapter.manifest
            if manifest.provider != account.provider:
                raise ProviderExtensionError(
                    "The resolved provider adapter has a different account scope.",
                    safe_context={"provider": account.provider},
                    code="provider_extension_scope_invalid",
                )
            if capability not in manifest.capabilities:
                raise ProviderExtensionError(
                    "The resolved provider adapter does not declare this capability.",
                    safe_context={
                        "provider": account.provider,
                        "capability": capability.value,
                    },
                    code="provider_capability_unavailable",
                )
            self._logger.emit(
                "provider_operation_started",
                result="started",
                correlation_id=correlation_id,
                operation=operation,
                fields={
                    "messenger_account_id": account.messenger_account_id,
                    "provider": account.provider,
                    "capability": capability.value,
                },
            )
            result = await invoke(adapter, context)
            current = self._resolve_account_context(messenger_account_id)
            if current.session_generation != account.session_generation or current.provider != account.provider:
                raise ProviderExtensionError("The account changed during the operation.", code="provider_extension_scope_invalid")
            if not isinstance(result, expected_type):
                raise ProviderExtensionError(
                    "The provider adapter returned an invalid result.",
                    safe_context={"provider": account.provider, "operation": operation},
                    code="provider_operation_result_invalid",
                )
            uncertain = isinstance(result, ProviderSendReceipt) and result.status is ProviderSendStatus.UNCERTAIN
            self._logger.emit(
                "provider_operation_uncertain" if uncertain else "provider_operation_succeeded",
                level="warning" if uncertain else "info",
                result="uncertain" if uncertain else "succeeded",
                reason_code=(result.safe_reason_code or "provider_send_uncertain") if uncertain else None,
                correlation_id=correlation_id,
                operation=operation,
                fields={
                    "messenger_account_id": account.messenger_account_id,
                    "provider": account.provider,
                    "capability": capability.value,
                    "duration_ms": round((time.monotonic() - started) * 1000, 2),
                },
            )
            return result
        except BridgeError as exc:
            self._logger.emit(
                "provider_operation_rejected",
                level="warning",
                result="rejected",
                reason_code=exc.code,
                correlation_id=correlation_id,
                operation=operation,
                fields={
                    "messenger_account_id": str(messenger_account_id),
                    "provider": account.provider if account else None,
                    "capability": capability.value,
                    "error_type": type(exc).__name__,
                },
            )
            raise
        except Exception as exc:
            self._logger.emit(
                "provider_operation_failed",
                level="error",
                result="failed",
                reason_code="provider_operation_exception",
                correlation_id=correlation_id,
                operation=operation,
                fields={
                    "messenger_account_id": str(messenger_account_id),
                    "provider": account.provider if account else None,
                    "capability": capability.value,
                    "error_type": type(exc).__name__,
                },
            )
            raise ProviderExtensionError(
                "The provider operation failed safely.",
                safe_context={"operation": operation, "error_type": type(exc).__name__},
                code="provider_operation_failed",
            ) from exc
        finally:
            if adapter is not None:
                try:
                    await adapter.close()
                except Exception as exc:
                    self._logger.emit(
                        "provider_operation_adapter_close_failed",
                        level="warning",
                        result="degraded",
                        reason_code="provider_adapter_close_failed",
                        correlation_id=correlation_id,
                        operation=operation,
                        fields={
                            "messenger_account_id": str(messenger_account_id),
                            "provider": account.provider if account else None,
                            "error_type": type(exc).__name__,
                        },
                    )


__all__ = [
    "ProviderApplicationOrchestrator",
    "ProviderOperationActor",
]
