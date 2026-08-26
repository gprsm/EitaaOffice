"""Compatibility adapter that keeps Eitaa translation outside orchestration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from ...errors import ProviderExtensionError
from ..contracts import (
    ProviderAccountContext,
    ProviderAuthOutcome,
    ProviderContactMutationReceipt,
    ProviderContactPage,
    ProviderContactUpsertRequest,
    ProviderDialogPage,
    ProviderManifest,
    ProviderMediaReadReceipt,
    ProviderMediaReadRequest,
    ProviderMessagePage,
    ProviderOperationContext,
    ProviderPeerReference,
    ProviderSendReceipt,
    ProviderSendTextRequest,
    SensitiveProviderValue,
)


@dataclass(frozen=True, slots=True)
class EitaaCompatibilityOperations:
    list_dialogs: Callable[
        [ProviderOperationContext, str | None, int],
        Awaitable[ProviderDialogPage],
    ]
    load_history: Callable[
        [ProviderOperationContext, ProviderPeerReference, str | None, int],
        Awaitable[ProviderMessagePage],
    ]
    send_text: Callable[
        [ProviderOperationContext, ProviderSendTextRequest],
        Awaitable[ProviderSendReceipt],
    ]
    read_media: Callable[
        [ProviderOperationContext, ProviderMediaReadRequest],
        Awaitable[ProviderMediaReadReceipt],
    ] | None = None
    list_contacts: Callable[
        [ProviderOperationContext, str | None, int],
        Awaitable[ProviderContactPage],
    ] | None = None
    upsert_contact: Callable[
        [ProviderOperationContext, ProviderContactUpsertRequest],
        Awaitable[ProviderContactMutationReceipt],
    ] | None = None


class EitaaProviderApplicationAdapter:
    """Typed bridge to the already accepted Eitaa runtime implementation."""

    def __init__(
        self,
        account: ProviderAccountContext,
        manifest: ProviderManifest,
        operations: EitaaCompatibilityOperations,
    ) -> None:
        if manifest.provider != account.provider:
            raise ProviderExtensionError(
                "The Eitaa adapter scope is invalid.",
                code="provider_extension_scope_invalid",
            )
        self._account = account
        self._manifest = manifest
        self._operations = operations

    @property
    def manifest(self) -> ProviderManifest:
        return self._manifest

    def _require_scope(self, context: ProviderOperationContext) -> None:
        if context.account != self._account:
            raise ProviderExtensionError(
                "The Eitaa operation account scope changed.",
                code="provider_extension_scope_invalid",
            )
        context.require_live_deadline()

    async def request_challenge(
        self,
        context: ProviderOperationContext,
        identity: SensitiveProviderValue,
    ) -> ProviderAuthOutcome:
        del context, identity
        raise ProviderExtensionError(
            "Authentication uses the account-scoped Eitaa auth service.",
            code="provider_auth_operation_not_migrated",
        )

    async def submit_challenge(
        self,
        context: ProviderOperationContext,
        challenge_state: SensitiveProviderValue,
        response: SensitiveProviderValue,
    ) -> ProviderAuthOutcome:
        del context, challenge_state, response
        raise ProviderExtensionError(
            "Authentication uses the account-scoped Eitaa auth service.",
            code="provider_auth_operation_not_migrated",
        )

    async def submit_second_factor(
        self,
        context: ProviderOperationContext,
        challenge_state: SensitiveProviderValue,
        response: SensitiveProviderValue,
    ) -> ProviderAuthOutcome:
        return await self.submit_challenge(context, challenge_state, response)

    async def validate_session(
        self,
        context: ProviderOperationContext,
        sealed_session: SensitiveProviderValue,
    ) -> ProviderAuthOutcome:
        del context, sealed_session
        raise ProviderExtensionError(
            "Session validation uses the account-scoped Eitaa auth service.",
            code="provider_auth_operation_not_migrated",
        )

    async def list_dialogs(
        self,
        context: ProviderOperationContext,
        *,
        cursor: str | None,
        limit: int,
    ) -> ProviderDialogPage:
        self._require_scope(context)
        result = await self._operations.list_dialogs(context, cursor, limit)
        if not isinstance(result, ProviderDialogPage):
            raise ProviderExtensionError(
                "The Eitaa dialog result is invalid.",
                code="provider_operation_result_invalid",
            )
        return result

    async def load_history(
        self,
        context: ProviderOperationContext,
        *,
        peer: ProviderPeerReference,
        cursor: str | None,
        limit: int,
    ) -> ProviderMessagePage:
        self._require_scope(context)
        result = await self._operations.load_history(context, peer, cursor, limit)
        if not isinstance(result, ProviderMessagePage):
            raise ProviderExtensionError(
                "The Eitaa history result is invalid.",
                code="provider_operation_result_invalid",
            )
        return result

    async def send_text(
        self,
        context: ProviderOperationContext,
        request: ProviderSendTextRequest,
    ) -> ProviderSendReceipt:
        self._require_scope(context)
        result = await self._operations.send_text(context, request)
        if not isinstance(result, ProviderSendReceipt):
            raise ProviderExtensionError(
                "The Eitaa send result is invalid.",
                code="provider_operation_result_invalid",
            )
        return result

    async def read_media(
        self,
        context: ProviderOperationContext,
        request: ProviderMediaReadRequest,
    ) -> ProviderMediaReadReceipt:
        self._require_scope(context)
        operation = self._operations.read_media
        if operation is None:
            raise ProviderExtensionError(
                "The Eitaa media operation has not been migrated.",
                code="provider_media_operation_not_implemented",
            )
        result = await operation(context, request)
        if not isinstance(result, ProviderMediaReadReceipt):
            raise ProviderExtensionError(
                "The Eitaa media result is invalid.",
                code="provider_operation_result_invalid",
            )
        return result

    async def list_contacts(
        self,
        context: ProviderOperationContext,
        *,
        cursor: str | None,
        limit: int,
    ) -> ProviderContactPage:
        self._require_scope(context)
        operation = self._operations.list_contacts
        if operation is None:
            raise ProviderExtensionError(
                "The Eitaa contact operation has not been migrated.",
                code="provider_contact_operation_not_implemented",
            )
        result = await operation(context, cursor, limit)
        if not isinstance(result, ProviderContactPage):
            raise ProviderExtensionError(
                "The Eitaa contact result is invalid.",
                code="provider_operation_result_invalid",
            )
        return result

    async def upsert_contact(
        self,
        context: ProviderOperationContext,
        request: ProviderContactUpsertRequest,
    ) -> ProviderContactMutationReceipt:
        self._require_scope(context)
        operation = self._operations.upsert_contact
        if operation is None:
            raise ProviderExtensionError(
                "The Eitaa contact mutation has not been migrated.",
                code="provider_contact_operation_not_implemented",
            )
        result = await operation(context, request)
        if not isinstance(result, ProviderContactMutationReceipt):
            raise ProviderExtensionError(
                "The Eitaa contact mutation result is invalid.",
                code="provider_operation_result_invalid",
            )
        return result

    async def close(self) -> None:
        # Runtime lifetime is owned by EitaaRuntimeRegistry, not one operation.
        return None


__all__ = [
    "EitaaCompatibilityOperations",
    "EitaaProviderApplicationAdapter",
]
