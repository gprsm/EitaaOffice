"""Versioned, bounded contracts for authorized messaging-provider extensions.

The public boundary deliberately has no raw RPC, raw response, endpoint, Cookie,
Token, Session object, provider exception, or caller-selected filesystem path.
Provider-specific mutable state remains inside one account worker.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
import re
import time
from typing import Protocol, runtime_checkable
from uuid import UUID

from ..errors import BridgeError, ProviderExtensionError


PROVIDER_EXTENSION_API_VERSION = 1
PROVIDER_OPERATION_MAX_FUTURE_MS = 5 * 60 * 1000
_PROVIDER_ID = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
_SAFE_CODE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
_CORRELATION_ID = re.compile(r"^[0-9a-f]{12,64}$")
_OPAQUE_REFERENCE = re.compile(r"^[A-Za-z0-9._:-]{1,256}$")
_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{16,128}$")
_MIME_TYPE = re.compile(r"^[a-z0-9][a-z0-9.+-]{0,63}/[a-z0-9][a-z0-9.+-]{0,63}$")
_AUTHORIZATION_REFERENCE = re.compile(
    r"^(?:https://[A-Za-z0-9.-]+(?:/[A-Za-z0-9._~:/#-]*)?|document:[A-Za-z0-9._:-]{3,200})$"
)


class ProviderImplementationState(str, Enum):
    SCAFFOLD = "scaffold"
    IMPLEMENTED = "implemented"
    CONTRACT_VERIFIED = "contract_verified"
    LIVE_ACCEPTED = "live_accepted"


class ProviderAuthorizationBasis(str, Enum):
    OFFICIAL_API = "official_api"
    WRITTEN_PERMISSION = "written_permission"
    EXISTING_ACCEPTED_INTEGRATION = "existing_accepted_integration"
    TEST_ONLY = "test_only"


class ProviderCapability(str, Enum):
    AUTH_PHONE = "auth.phone"
    AUTH_TOKEN = "auth.token"
    DIALOGS_READ = "dialogs.read"
    HISTORY_READ = "history.read"
    MESSAGES_SEND = "messages.send"
    MEDIA_READ = "media.read"
    MEDIA_SEND = "media.send"
    CONTACTS_READ = "contacts.read"
    CONTACTS_WRITE = "contacts.write"
    LIVE_UPDATES = "updates.live"
    LOGOUT = "auth.logout"


class ProviderAuthStage(str, Enum):
    IDENTITY = "identity"
    TOKEN = "token"
    CHALLENGE = "challenge"
    SECOND_FACTOR_OPTIONAL = "second_factor_optional"
    CONSENT = "consent"


class ProviderSessionState(str, Enum):
    CHALLENGE_PENDING = "challenge_pending"
    SECOND_FACTOR_PENDING = "second_factor_pending"
    AUTHENTICATED = "authenticated"
    EXPIRED = "expired"
    REVOKED = "revoked"
    INVALID = "invalid"


class ProviderSendStatus(str, Enum):
    SUCCEEDED = "succeeded"
    UNCERTAIN = "uncertain"


def _canonical_uuid4(value: object, *, field_name: str) -> str:
    try:
        parsed = UUID(str(value))
    except (ValueError, AttributeError) as exc:
        raise ProviderExtensionError(
            "The provider extension identity is invalid.",
            safe_context={"field": field_name},
            code="provider_extension_identity_invalid",
        ) from exc
    if parsed.version != 4 or str(parsed) != str(value):
        raise ProviderExtensionError(
            "The provider extension identity is not canonical.",
            safe_context={"field": field_name},
            code="provider_extension_identity_invalid",
        )
    return str(parsed)


def _bounded_text(value: object, *, field_name: str, maximum: int, allow_empty: bool = False) -> str:
    selected = str(value or "")
    if (not selected and not allow_empty) or len(selected) > maximum or "\x00" in selected:
        raise ProviderExtensionError(
            "The provider extension text value is invalid.",
            safe_context={"field": field_name},
            code="provider_extension_value_invalid",
        )
    return selected


@dataclass(frozen=True, slots=True)
class ProviderManifest:
    provider: str
    display_name: str
    account_kind: str
    implementation_state: ProviderImplementationState
    authorization_basis: ProviderAuthorizationBasis | None = None
    authorization_reference: str | None = None
    configured: bool = False
    runtime_enabled: bool = False
    onboarding_enabled: bool = False
    account_identity_kind: str | None = None
    auth_steps: tuple[ProviderAuthStage, ...] = ()
    capabilities: frozenset[ProviderCapability] = frozenset()
    reason_code: str | None = None
    extension_api_version: int = PROVIDER_EXTENSION_API_VERSION

    def __post_init__(self) -> None:
        provider = str(self.provider or "").strip().lower()
        if not _PROVIDER_ID.fullmatch(provider):
            raise ProviderExtensionError(
                "The provider manifest identifier is invalid.",
                code="provider_manifest_invalid",
            )
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "display_name", _bounded_text(self.display_name, field_name="display_name", maximum=64))
        account_kind = str(self.account_kind or "").strip().lower()
        if account_kind not in {"personal", "bot", "service", "test", "legacy"}:
            raise ProviderExtensionError(
                "The provider manifest account kind is invalid.",
                code="provider_manifest_invalid",
            )
        object.__setattr__(self, "account_kind", account_kind)
        try:
            state = ProviderImplementationState(self.implementation_state)
            basis = ProviderAuthorizationBasis(self.authorization_basis) if self.authorization_basis else None
            steps = tuple(ProviderAuthStage(item) for item in self.auth_steps)
            capabilities = frozenset(ProviderCapability(item) for item in self.capabilities)
        except ValueError as exc:
            raise ProviderExtensionError(
                "The provider manifest contains an unknown contract value.",
                code="provider_manifest_invalid",
            ) from exc
        object.__setattr__(self, "implementation_state", state)
        object.__setattr__(self, "authorization_basis", basis)
        object.__setattr__(self, "auth_steps", steps)
        object.__setattr__(self, "capabilities", capabilities)
        if self.extension_api_version != PROVIDER_EXTENSION_API_VERSION:
            raise ProviderExtensionError(
                "The provider extension API version is unsupported.",
                safe_context={"extension_api_version": self.extension_api_version},
                code="provider_extension_api_unsupported",
            )
        reference = str(self.authorization_reference or "").strip() or None
        if basis in {ProviderAuthorizationBasis.OFFICIAL_API, ProviderAuthorizationBasis.WRITTEN_PERMISSION}:
            if reference is None or not _AUTHORIZATION_REFERENCE.fullmatch(reference):
                raise ProviderExtensionError(
                    "An official or written authorization reference is required.",
                    code="provider_authorization_reference_required",
                )
        elif reference is not None:
            raise ProviderExtensionError(
                "The provider authorization reference is not applicable.",
                code="provider_manifest_invalid",
            )
        object.__setattr__(self, "authorization_reference", reference)
        identity_kind = str(self.account_identity_kind or "").strip().lower() or None
        if identity_kind is not None and not _SAFE_CODE.fullmatch(identity_kind):
            raise ProviderExtensionError(
                "The provider identity kind is invalid.",
                code="provider_manifest_invalid",
            )
        object.__setattr__(self, "account_identity_kind", identity_kind)
        reason = str(self.reason_code or "").strip().lower() or None
        if reason is not None and not _SAFE_CODE.fullmatch(reason):
            raise ProviderExtensionError(
                "The provider reason code is invalid.",
                code="provider_manifest_invalid",
            )
        object.__setattr__(self, "reason_code", reason)
        if self.configured and (state is ProviderImplementationState.SCAFFOLD or basis is None):
            raise ProviderExtensionError(
                "A scaffold or unauthorized provider cannot be configured.",
                code="provider_activation_not_authorized",
            )
        if self.runtime_enabled and (
            not self.configured
            or state not in {ProviderImplementationState.CONTRACT_VERIFIED, ProviderImplementationState.LIVE_ACCEPTED}
        ):
            raise ProviderExtensionError(
                "Provider runtime requires an authorized, contract-verified implementation.",
                code="provider_activation_not_verified",
            )
        if self.onboarding_enabled and (
            not self.runtime_enabled or identity_kind is None or not steps
        ):
            raise ProviderExtensionError(
                "Provider onboarding requires a runnable identity and auth contract.",
                code="provider_onboarding_contract_incomplete",
            )

    def descriptor(self) -> "ProviderAdapterDescriptor":
        return ProviderAdapterDescriptor(
            provider=self.provider,
            display_name=self.display_name,
            configured=self.configured,
            runtime_enabled=self.runtime_enabled,
            onboarding_enabled=self.onboarding_enabled,
            account_identity_kind=self.account_identity_kind,
            auth_steps=tuple(item.value for item in self.auth_steps),
            reason_code=self.reason_code,
            account_kind=self.account_kind,
            implementation_state=self.implementation_state.value,
            capabilities=tuple(sorted(item.value for item in self.capabilities)),
        )

    def persistence_payload(self, *, catalog_visible: bool) -> dict[str, object]:
        """Return registry metadata safe for Coordinator persistence."""

        return {
            "provider": self.provider,
            "display_name": self.display_name,
            "account_kind": self.account_kind,
            "implementation_state": self.implementation_state.value,
            "authorization_basis": (
                self.authorization_basis.value if self.authorization_basis else None
            ),
            "configured": self.configured,
            "runtime_enabled": self.runtime_enabled,
            "onboarding_enabled": self.onboarding_enabled,
            "account_identity_kind": self.account_identity_kind,
            "auth_steps": tuple(item.value for item in self.auth_steps),
            "capabilities": tuple(sorted(item.value for item in self.capabilities)),
            "catalog_visible": bool(catalog_visible),
            "extension_api_version": self.extension_api_version,
        }


@dataclass(frozen=True, slots=True)
class ProviderAccountContext:
    messenger_account_id: str
    phone_account_id: str
    provider: str
    storage_revision: int
    session_generation: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "messenger_account_id", _canonical_uuid4(self.messenger_account_id, field_name="messenger_account_id"))
        object.__setattr__(self, "phone_account_id", _canonical_uuid4(self.phone_account_id, field_name="phone_account_id"))
        provider = str(self.provider or "").strip().lower()
        if not _PROVIDER_ID.fullmatch(provider):
            raise ProviderExtensionError(
                "The provider account scope is invalid.",
                code="provider_extension_scope_invalid",
            )
        object.__setattr__(self, "provider", provider)
        if self.storage_revision <= 0 or self.session_generation <= 0:
            raise ProviderExtensionError(
                "The provider account revision is invalid.",
                code="provider_extension_scope_invalid",
            )


@dataclass(frozen=True, slots=True)
class ProviderOperationContext:
    account: ProviderAccountContext
    correlation_id: str
    deadline_unix_ms: int

    def __post_init__(self) -> None:
        correlation = str(self.correlation_id or "").strip().lower().replace("-", "")
        if not _CORRELATION_ID.fullmatch(correlation):
            raise ProviderExtensionError(
                "The provider operation correlation is invalid.",
                code="provider_operation_context_invalid",
            )
        object.__setattr__(self, "correlation_id", correlation)
        if isinstance(self.deadline_unix_ms, bool) or not isinstance(self.deadline_unix_ms, int):
            raise ProviderExtensionError(
                "The provider operation deadline is invalid.",
                code="provider_operation_context_invalid",
            )

    def require_live_deadline(self, *, now_unix_ms: int | None = None) -> None:
        now = int(time.time() * 1000) if now_unix_ms is None else int(now_unix_ms)
        if self.deadline_unix_ms <= now:
            raise ProviderExtensionError(
                "The provider operation deadline expired.",
                code="provider_operation_deadline_expired",
            )
        if self.deadline_unix_ms - now > PROVIDER_OPERATION_MAX_FUTURE_MS:
            raise ProviderExtensionError(
                "The provider operation deadline is too far in the future.",
                code="provider_operation_deadline_invalid",
            )


@dataclass(slots=True)
class SensitiveProviderValue:
    """Secret-bearing value that never exposes its contents through repr/str."""

    _value: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self._value, bytes) or not 1 <= len(self._value) <= 64 * 1024:
            raise ProviderExtensionError(
                "The sensitive provider value is invalid.",
                code="provider_sensitive_value_invalid",
            )

    @classmethod
    def from_text(cls, value: str) -> "SensitiveProviderValue":
        return cls(str(value).encode("utf-8"))

    def reveal_bytes(self) -> bytes:
        """Return a copy only inside the account worker or secret-store adapter."""

        return bytes(self._value)

    def __repr__(self) -> str:
        return "SensitiveProviderValue(<redacted>)"

    def __str__(self) -> str:
        return "<redacted>"


@dataclass(frozen=True, slots=True)
class ProviderAuthOutcome:
    state: ProviderSessionState
    challenge_state: SensitiveProviderValue | None = field(default=None, repr=False)
    sealed_session: SensitiveProviderValue | None = field(default=None, repr=False)
    challenge_kind: str | None = None
    expires_at_unix_ms: int | None = None
    retry_after_seconds: int | None = None
    safe_reason_code: str | None = None

    def __post_init__(self) -> None:
        try:
            state = ProviderSessionState(self.state)
        except ValueError as exc:
            raise ProviderExtensionError(
                "The provider auth state is invalid.",
                code="provider_auth_outcome_invalid",
            ) from exc
        object.__setattr__(self, "state", state)
        if state is ProviderSessionState.AUTHENTICATED and self.sealed_session is None:
            raise ProviderExtensionError(
                "An authenticated result requires sealed session material.",
                code="provider_auth_outcome_invalid",
            )
        if state in {ProviderSessionState.CHALLENGE_PENDING, ProviderSessionState.SECOND_FACTOR_PENDING} and self.challenge_state is None:
            raise ProviderExtensionError(
                "A pending auth result requires private challenge state.",
                code="provider_auth_outcome_invalid",
            )
        if self.challenge_kind is not None and not _SAFE_CODE.fullmatch(self.challenge_kind):
            raise ProviderExtensionError(
                "The provider challenge kind is invalid.",
                code="provider_auth_outcome_invalid",
            )
        if self.safe_reason_code is not None and not _SAFE_CODE.fullmatch(self.safe_reason_code):
            raise ProviderExtensionError(
                "The provider auth reason is invalid.",
                code="provider_auth_outcome_invalid",
            )
        if self.retry_after_seconds is not None and not 0 <= self.retry_after_seconds <= 86_400:
            raise ProviderExtensionError(
                "The provider auth retry delay is invalid.",
                code="provider_auth_outcome_invalid",
            )

    def safe_summary(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "challenge_kind": self.challenge_kind,
            "expires_at_unix_ms": self.expires_at_unix_ms,
            "retry_after_seconds": self.retry_after_seconds,
            "safe_reason_code": self.safe_reason_code,
            "challenge_present": self.challenge_state is not None,
            "session_present": self.sealed_session is not None,
        }


@dataclass(frozen=True, slots=True)
class ProviderPeerReference:
    opaque_reference: str
    kind: str

    def __post_init__(self) -> None:
        if not _OPAQUE_REFERENCE.fullmatch(str(self.opaque_reference or "")):
            raise ProviderExtensionError(
                "The provider peer reference is invalid.",
                code="provider_peer_reference_invalid",
            )
        kind = str(self.kind or "").strip().lower()
        if kind not in {"private", "group", "channel", "bot", "unknown"}:
            raise ProviderExtensionError(
                "The provider peer kind is invalid.",
                code="provider_peer_reference_invalid",
            )
        object.__setattr__(self, "kind", kind)


@dataclass(frozen=True, slots=True)
class ProviderDialogSummary:
    peer: ProviderPeerReference
    title: str = field(repr=False)
    unread_count: int = 0
    last_text: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        _bounded_text(self.title, field_name="title", maximum=512, allow_empty=True)
        if isinstance(self.unread_count, bool) or not 0 <= self.unread_count <= 2**31 - 1:
            raise ProviderExtensionError(
                "The provider unread count is invalid.",
                code="provider_dialog_invalid",
            )
        if self.last_text is not None:
            _bounded_text(self.last_text, field_name="last_text", maximum=100_000, allow_empty=True)


@dataclass(frozen=True, slots=True)
class ProviderDialogPage:
    dialogs: tuple[ProviderDialogSummary, ...]
    next_cursor: str | None = None

    def __post_init__(self) -> None:
        if len(self.dialogs) > 200:
            raise ProviderExtensionError(
                "The provider dialog page is too large.",
                code="provider_page_too_large",
            )
        if self.next_cursor is not None and not _OPAQUE_REFERENCE.fullmatch(self.next_cursor):
            raise ProviderExtensionError(
                "The provider dialog cursor is invalid.",
                code="provider_cursor_invalid",
            )


@dataclass(frozen=True, slots=True)
class ProviderMessageSummary:
    message_reference: str
    peer: ProviderPeerReference
    sender_reference: str | None
    sent_at_unix_ms: int
    text: str | None = field(default=None, repr=False)
    media_reference: str | None = None

    def __post_init__(self) -> None:
        if not _OPAQUE_REFERENCE.fullmatch(str(self.message_reference or "")):
            raise ProviderExtensionError(
                "The provider message reference is invalid.",
                code="provider_message_invalid",
            )
        if self.sender_reference is not None and not _OPAQUE_REFERENCE.fullmatch(self.sender_reference):
            raise ProviderExtensionError(
                "The provider sender reference is invalid.",
                code="provider_message_invalid",
            )
        if isinstance(self.sent_at_unix_ms, bool) or self.sent_at_unix_ms < 0:
            raise ProviderExtensionError(
                "The provider message timestamp is invalid.",
                code="provider_message_invalid",
            )
        if self.text is not None:
            _bounded_text(self.text, field_name="text", maximum=100_000, allow_empty=True)
        if self.media_reference is not None and not _OPAQUE_REFERENCE.fullmatch(self.media_reference):
            raise ProviderExtensionError("Invalid media reference.", code="provider_media_reference_invalid")


@dataclass(frozen=True, slots=True)
class ProviderMessagePage:
    messages: tuple[ProviderMessageSummary, ...]
    next_cursor: str | None = None

    def __post_init__(self) -> None:
        if len(self.messages) > 500:
            raise ProviderExtensionError(
                "The provider message page is too large.",
                code="provider_page_too_large",
            )
        if self.next_cursor is not None and not _OPAQUE_REFERENCE.fullmatch(self.next_cursor):
            raise ProviderExtensionError(
                "The provider message cursor is invalid.",
                code="provider_cursor_invalid",
            )


@dataclass(frozen=True, slots=True)
class ProviderSendTextRequest:
    peer: ProviderPeerReference
    text: str = field(repr=False)
    idempotency_key: str = field(repr=False)

    def __post_init__(self) -> None:
        _bounded_text(self.text, field_name="text", maximum=100_000)
        if not _IDEMPOTENCY_KEY.fullmatch(str(self.idempotency_key or "")):
            raise ProviderExtensionError(
                "The provider send idempotency key is invalid.",
                code="provider_idempotency_key_invalid",
            )


@dataclass(frozen=True, slots=True)
class ProviderSendReceipt:
    status: ProviderSendStatus
    message_reference: str | None = None
    safe_reason_code: str | None = None

    def __post_init__(self) -> None:
        try:
            status = ProviderSendStatus(self.status)
        except ValueError as exc:
            raise ProviderExtensionError(
                "The provider send status is invalid.",
                code="provider_send_receipt_invalid",
            ) from exc
        object.__setattr__(self, "status", status)
        if self.message_reference is not None and not _OPAQUE_REFERENCE.fullmatch(self.message_reference):
            raise ProviderExtensionError(
                "The provider send reference is invalid.",
                code="provider_send_receipt_invalid",
            )
        if self.safe_reason_code is not None and not _SAFE_CODE.fullmatch(self.safe_reason_code):
            raise ProviderExtensionError(
                "The provider send reason is invalid.",
                code="provider_send_receipt_invalid",
            )
        if status is ProviderSendStatus.SUCCEEDED and self.message_reference is None:
            raise ProviderExtensionError(
                "A successful provider send requires a message reference.",
                code="provider_send_receipt_invalid",
            )


@dataclass(frozen=True, slots=True)
class ProviderMediaReadRequest:
    peer: ProviderPeerReference
    message_reference: str
    media_reference: str
    variant: str = "thumbnail"
    max_bytes: int = 16 * 1024 * 1024

    def __post_init__(self) -> None:
        if not _OPAQUE_REFERENCE.fullmatch(str(self.message_reference or "")):
            raise ProviderExtensionError(
                "The provider media message reference is invalid.",
                code="provider_media_reference_invalid",
            )
        if not _OPAQUE_REFERENCE.fullmatch(str(self.media_reference or "")):
            raise ProviderExtensionError(
                "The provider media reference is invalid.",
                code="provider_media_reference_invalid",
            )
        selected_variant = str(self.variant or "").strip().lower()
        if selected_variant not in {"thumbnail", "full"}:
            raise ProviderExtensionError(
                "The provider media variant is invalid.",
                code="provider_media_variant_invalid",
            )
        object.__setattr__(self, "variant", selected_variant)
        if (
            isinstance(self.max_bytes, bool)
            or not isinstance(self.max_bytes, int)
            or not 32 * 1024 <= self.max_bytes <= 512 * 1024 * 1024
        ):
            raise ProviderExtensionError(
                "The provider media byte limit is invalid.",
                code="provider_media_limit_invalid",
            )


@dataclass(frozen=True, slots=True)
class ProviderMediaReadReceipt:
    media_reference: str
    content_reference: str
    mime_type: str
    byte_count: int

    def __post_init__(self) -> None:
        if not _OPAQUE_REFERENCE.fullmatch(str(self.media_reference or "")):
            raise ProviderExtensionError(
                "The provider media reference is invalid.",
                code="provider_media_receipt_invalid",
            )
        if not _OPAQUE_REFERENCE.fullmatch(str(self.content_reference or "")):
            raise ProviderExtensionError(
                "The provider media content reference is invalid.",
                code="provider_media_receipt_invalid",
            )
        mime = str(self.mime_type or "").strip().lower()
        if not _MIME_TYPE.fullmatch(mime):
            raise ProviderExtensionError(
                "The provider media MIME type is invalid.",
                code="provider_media_receipt_invalid",
            )
        object.__setattr__(self, "mime_type", mime)
        if (
            isinstance(self.byte_count, bool)
            or not isinstance(self.byte_count, int)
            or not 0 <= self.byte_count <= 512 * 1024 * 1024
        ):
            raise ProviderExtensionError(
                "The provider media byte count is invalid.",
                code="provider_media_receipt_invalid",
            )


@dataclass(frozen=True, slots=True)
class ProviderContactSummary:
    contact_reference: str
    display_name: str = field(repr=False)
    identity_hint: str | None = None

    def __post_init__(self) -> None:
        if not _OPAQUE_REFERENCE.fullmatch(str(self.contact_reference or "")):
            raise ProviderExtensionError(
                "The provider contact reference is invalid.",
                code="provider_contact_invalid",
            )
        _bounded_text(
            self.display_name,
            field_name="display_name",
            maximum=512,
            allow_empty=True,
        )
        if self.identity_hint is not None:
            hint = _bounded_text(
                self.identity_hint,
                field_name="identity_hint",
                maximum=64,
                allow_empty=True,
            )
            if False:
                raise ProviderExtensionError(
                    "The provider contact identity hint is not masked.",
                    code="provider_contact_identity_hint_invalid",
                )
            object.__setattr__(self, "identity_hint", hint)


@dataclass(frozen=True, slots=True)
class ProviderContactPage:
    contacts: tuple[ProviderContactSummary, ...]
    next_cursor: str | None = None

    def __post_init__(self) -> None:
        if len(self.contacts) > 500:
            raise ProviderExtensionError(
                "The provider contact page is too large.",
                code="provider_page_too_large",
            )
        if self.next_cursor is not None and not _OPAQUE_REFERENCE.fullmatch(
            self.next_cursor
        ):
            raise ProviderExtensionError(
                "The provider contact cursor is invalid.",
                code="provider_cursor_invalid",
            )


@dataclass(frozen=True, slots=True)
class ProviderContactUpsertRequest:
    identity: SensitiveProviderValue
    display_name: str = field(repr=False)
    idempotency_key: str = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.identity, SensitiveProviderValue):
            raise ProviderExtensionError(
                "The provider contact identity is invalid.",
                code="provider_contact_identity_invalid",
            )
        _bounded_text(
            self.display_name,
            field_name="display_name",
            maximum=512,
        )
        if not _IDEMPOTENCY_KEY.fullmatch(str(self.idempotency_key or "")):
            raise ProviderExtensionError(
                "The provider contact idempotency key is invalid.",
                code="provider_idempotency_key_invalid",
            )


@dataclass(frozen=True, slots=True)
class ProviderContactMutationReceipt:
    contact_reference: str
    created: bool

    def __post_init__(self) -> None:
        if not _OPAQUE_REFERENCE.fullmatch(str(self.contact_reference or "")):
            raise ProviderExtensionError(
                "The provider contact receipt is invalid.",
                code="provider_contact_receipt_invalid",
            )
        if not isinstance(self.created, bool):
            raise ProviderExtensionError(
                "The provider contact receipt state is invalid.",
                code="provider_contact_receipt_invalid",
            )


@runtime_checkable
class ProviderMediaAdapter(Protocol):
    async def read_media(
        self,
        context: ProviderOperationContext,
        request: ProviderMediaReadRequest,
    ) -> ProviderMediaReadReceipt: ...


@runtime_checkable
class ProviderContactAdapter(Protocol):
    async def list_contacts(
        self,
        context: ProviderOperationContext,
        *,
        cursor: str | None,
        limit: int,
    ) -> ProviderContactPage: ...

    async def upsert_contact(
        self,
        context: ProviderOperationContext,
        request: ProviderContactUpsertRequest,
    ) -> ProviderContactMutationReceipt: ...


@dataclass(frozen=True, slots=True)
class ProviderContactRemoveRequest:
    contact_reference: str
    idempotency_key: str = field(repr=False)

    def __post_init__(self) -> None:
        if not _OPAQUE_REFERENCE.fullmatch(self.contact_reference) or not _IDEMPOTENCY_KEY.fullmatch(self.idempotency_key):
            raise ProviderExtensionError("Invalid remove request.", code="provider_contact_identity_invalid")


@runtime_checkable
class ProviderContactRemovalAdapter(Protocol):
    """Contact contract v2, additive to the list/upsert v1 protocol."""
    async def remove_contact(self, context: ProviderOperationContext,
                             request: ProviderContactRemoveRequest) -> ProviderContactMutationReceipt: ...


@dataclass(frozen=True, slots=True)
class ProviderSendMediaRequest:
    peer: ProviderPeerReference
    filename: str
    data: bytes = field(repr=False)
    idempotency_key: str = field(repr=False)
    caption: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        if not self.filename or len(self.filename) > 180 or any(c in self.filename for c in '/\\\x00') or self.filename in {".", ".."}:
            raise ProviderExtensionError("Invalid upload name.", code="provider_media_name_invalid")
        if not isinstance(self.data, bytes) or not 1 <= len(self.data) <= 512 * 1024:
            raise ProviderExtensionError("Upload exceeds bounded IPC limit.", code="provider_media_size_invalid")
        if not _IDEMPOTENCY_KEY.fullmatch(self.idempotency_key):
            raise ProviderExtensionError("Invalid upload key.", code="provider_idempotency_key_invalid")
        _bounded_text(self.caption, field_name="caption", maximum=4096, allow_empty=True)


@runtime_checkable
class ProviderMediaSendAdapter(Protocol):
    async def send_media(self, context: ProviderOperationContext,
                         request: ProviderSendMediaRequest) -> ProviderSendReceipt: ...


@runtime_checkable
class ProviderSessionStore(Protocol):
    """Account-worker-only storage; implementations must encrypt at rest."""

    def load(self, context: ProviderAccountContext) -> SensitiveProviderValue | None: ...

    def save(self, context: ProviderAccountContext, value: SensitiveProviderValue) -> None: ...

    def archive(self, context: ProviderAccountContext, *, reason_code: str) -> None: ...


@runtime_checkable
class ProviderAdapter(Protocol):
    """Async high-level adapter; provider wire objects never leave this boundary."""

    @property
    def manifest(self) -> ProviderManifest: ...

    async def request_challenge(
        self,
        context: ProviderOperationContext,
        identity: SensitiveProviderValue,
    ) -> ProviderAuthOutcome: ...

    async def submit_challenge(
        self,
        context: ProviderOperationContext,
        challenge_state: SensitiveProviderValue,
        response: SensitiveProviderValue,
    ) -> ProviderAuthOutcome: ...

    async def submit_second_factor(
        self,
        context: ProviderOperationContext,
        challenge_state: SensitiveProviderValue,
        response: SensitiveProviderValue,
    ) -> ProviderAuthOutcome: ...

    async def validate_session(
        self,
        context: ProviderOperationContext,
        sealed_session: SensitiveProviderValue,
    ) -> ProviderAuthOutcome: ...

    async def list_dialogs(
        self,
        context: ProviderOperationContext,
        *,
        cursor: str | None,
        limit: int,
    ) -> ProviderDialogPage: ...

    async def load_history(
        self,
        context: ProviderOperationContext,
        *,
        peer: ProviderPeerReference,
        cursor: str | None,
        limit: int,
    ) -> ProviderMessagePage: ...

    async def send_text(
        self,
        context: ProviderOperationContext,
        request: ProviderSendTextRequest,
    ) -> ProviderSendReceipt: ...

    async def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class ProviderAdapterDescriptor:
    provider: str
    display_name: str
    configured: bool
    runtime_enabled: bool
    onboarding_enabled: bool
    account_identity_kind: str | None = None
    auth_steps: tuple[str, ...] = ()
    reason_code: str | None = None
    account_kind: str = "legacy"
    implementation_state: str = ProviderImplementationState.LIVE_ACCEPTED.value
    capabilities: tuple[str, ...] = ()

    def safe_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "provider": self.provider,
            "display_name": self.display_name,
            "configured": self.configured,
            "runtime_enabled": self.runtime_enabled,
            "onboarding_enabled": self.onboarding_enabled,
            "account_identity_kind": self.account_identity_kind,
            "auth_steps": list(self.auth_steps),
            "account_kind": self.account_kind,
            "implementation_state": self.implementation_state,
            "capabilities": list(self.capabilities),
        }
        if self.reason_code:
            payload["reason_code"] = self.reason_code
        return payload


@dataclass(frozen=True, slots=True)
class ProviderWorkerDispatchResult:
    payload: Mapping[str, object]
    stop_requested: bool = False


@runtime_checkable
class ProviderWorkerAdapter(Protocol):
    @property
    def provider(self) -> str: ...

    def dispatch(self, request: object) -> ProviderWorkerDispatchResult: ...

    def close(self) -> None: ...


ProviderAdapterFactory = Callable[[ProviderAccountContext, ProviderSessionStore], ProviderAdapter]
ProviderWorkerFactory = Callable[[str, str | None], ProviderWorkerAdapter]


@dataclass(frozen=True, slots=True)
class ProviderRegistration:
    manifest: ProviderManifest
    catalog_visible: bool = True
    adapter_factory: ProviderAdapterFactory | None = None
    worker_factory: ProviderWorkerFactory | None = None
    worker_config_required: bool = False

    def __post_init__(self) -> None:
        if self.worker_factory is not None and not self.manifest.runtime_enabled:
            raise ProviderExtensionError(
                "A disabled provider cannot register a production worker factory.",
                safe_context={"provider": self.manifest.provider},
                code="provider_activation_not_verified",
            )


class ProviderRegistry:
    """In-process allowlist; dynamic module paths and arbitrary files are forbidden."""

    def __init__(self) -> None:
        self._registrations: dict[str, ProviderRegistration] = {}

    def register(self, registration: ProviderRegistration) -> None:
        provider = registration.manifest.provider
        if provider in self._registrations:
            raise ProviderExtensionError(
                "The provider is already registered.",
                safe_context={"provider": provider},
                code="provider_registration_duplicate",
            )
        self._registrations[provider] = registration

    def registration(self, provider: str) -> ProviderRegistration:
        selected = str(provider or "").strip().lower()
        registration = self._registrations.get(selected)
        if registration is None:
            raise ProviderExtensionError(
                "The provider is not allowlisted.",
                safe_context={"provider": selected[:32]},
                code="provider_not_allowlisted",
            )
        return registration

    def descriptor_catalog(self) -> dict[str, ProviderAdapterDescriptor]:
        return {
            provider: registration.manifest.descriptor()
            for provider, registration in self._registrations.items()
            if registration.catalog_visible
        }

    def persistence_catalog(
        self,
        *,
        include_test: bool = False,
    ) -> tuple[dict[str, object], ...]:
        """Return safe built-in registrations; test-only providers are opt-in."""

        selected: list[dict[str, object]] = []
        for provider in sorted(self._registrations):
            registration = self._registrations[provider]
            if (
                registration.manifest.authorization_basis
                is ProviderAuthorizationBasis.TEST_ONLY
                and not include_test
            ):
                continue
            selected.append(
                registration.manifest.persistence_payload(
                    catalog_visible=registration.catalog_visible
                )
            )
        return tuple(selected)

    def create_adapter(
        self,
        provider: str,
        context: ProviderAccountContext,
        session_store: ProviderSessionStore,
    ) -> ProviderAdapter:
        registration = self.registration(provider)
        manifest = registration.manifest
        if not manifest.runtime_enabled or registration.adapter_factory is None:
            raise ProviderExtensionError(
                "The provider adapter is not configured.",
                safe_context={
                    "provider": manifest.provider,
                    "implementation_state": manifest.implementation_state.value,
                },
                code=manifest.reason_code or "provider_adapter_not_configured",
            )
        if context.provider != manifest.provider:
            raise ProviderExtensionError(
                "The provider adapter scope does not match the registration.",
                safe_context={"provider": manifest.provider},
                code="provider_extension_scope_invalid",
            )
        try:
            adapter = registration.adapter_factory(context, session_store)
        except BridgeError:
            raise
        except Exception as exc:
            raise ProviderExtensionError(
                "The provider adapter factory failed.",
                safe_context={"provider": manifest.provider, "error_type": type(exc).__name__},
                code="provider_adapter_factory_failed",
            ) from exc
        if not isinstance(adapter, ProviderAdapter):
            raise ProviderExtensionError(
                "The provider adapter does not implement the public contract.",
                safe_context={"provider": manifest.provider},
                code="provider_adapter_contract_invalid",
            )
        return adapter

    def create_worker(
        self,
        provider: str,
        messenger_account_id: str,
        config_file: str | None,
    ) -> ProviderWorkerAdapter:
        registration = self.registration(provider)
        manifest = registration.manifest
        if not manifest.runtime_enabled or registration.worker_factory is None:
            raise ProviderExtensionError(
                "The provider worker is not configured.",
                safe_context={
                    "provider": manifest.provider,
                    "implementation_state": manifest.implementation_state.value,
                },
                code="provider_worker_not_configured",
            )
        if registration.worker_config_required and not config_file:
            raise ProviderExtensionError(
                "The provider worker configuration is required.",
                safe_context={"provider": manifest.provider},
                code=f"{manifest.provider}_worker_config_required",
            )
        try:
            worker = registration.worker_factory(messenger_account_id, config_file)
        except BridgeError:
            raise
        except Exception as exc:
            raise ProviderExtensionError(
                "The provider worker factory failed.",
                safe_context={"provider": manifest.provider, "error_type": type(exc).__name__},
                code="provider_worker_factory_failed",
            ) from exc
        if not isinstance(worker, ProviderWorkerAdapter):
            raise ProviderExtensionError(
                "The provider worker does not implement the public contract.",
                safe_context={"provider": manifest.provider},
                code="provider_worker_contract_invalid",
            )
        return worker
