"""Typed, safe exception hierarchy for Eitaa Bridge."""

from __future__ import annotations

from typing import Any


class BridgeError(Exception):
    component = "bridge"
    code = "bridge_error"

    def __init__(
        self,
        message: str,
        *,
        safe_context: dict[str, Any] | None = None,
        debug_file: str | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.safe_context = dict(safe_context or {})
        self.debug_file = debug_file
        if code is not None:
            self.code = code

    def __str__(self) -> str:
        suffix = f" [debug file: {self.debug_file}]" if self.debug_file else ""
        return f"{self.message}{suffix}"


class BridgeConfigurationError(BridgeError):
    component = "configuration"
    code = "configuration_error"


class CredentialError(BridgeError):
    component = "credentials"
    code = "credential_error"


class CoreCompatibilityError(BridgeError):
    component = "core_binding"
    code = "core_compatibility_error"


class AuthenticationRuntimeError(BridgeError):
    """Safe wrapper for local/native authentication runtime failures."""

    component = "authentication"
    code = "authentication_runtime_error"


class SessionOwnershipError(BridgeError):
    """Fail-closed error for invalid or ambiguous provider-session ownership."""

    component = "session_ownership"
    code = "session_ownership_error"


class EitaaRuntimeError(BridgeError):
    """Fail-closed error for account-scoped Eitaa runtime ownership."""

    component = "eitaa_runtime"
    code = "eitaa_runtime_error"


class WorkerIpcError(BridgeError):
    """Safe failure at the authenticated local worker IPC boundary."""

    component = "worker_ipc"
    code = "worker_ipc_error"


class ProviderExtensionError(BridgeError):
    """Safe failure at the allowlisted provider-extension boundary."""

    component = "provider_extension"
    code = "provider_extension_error"


class WordPressError(BridgeError):
    component = "wordpress"
    code = "wordpress_error"


class WordPressConnectionError(WordPressError):
    code = "wordpress_connection_error"


class WordPressAuthenticationError(WordPressError):
    code = "wordpress_authentication_error"


class WordPressHttpError(WordPressError):
    code = "wordpress_http_error"


class WordPressResponseError(WordPressError):
    code = "wordpress_response_error"


class WordPressAmbiguousWriteError(WordPressError):
    """A write may have reached WordPress, so automatic retry is unsafe."""

    code = "wordpress_ambiguous_write"


class MediaFileError(BridgeError):
    component = "media_file"
    code = "media_file_error"


class DoctorError(BridgeError):
    component = "doctor"
    code = "doctor_error"


class PublicationWorkflowError(BridgeError):
    component = "publication"
    code = "publication_workflow_error"


class PublicationMessageNotFoundError(PublicationWorkflowError):
    code = "publication_message_not_found"


class PublicationBlockedError(PublicationWorkflowError):
    code = "publication_blocked"


class PublicationCollisionError(PublicationWorkflowError):
    code = "publication_collision"


class CompositionError(BridgeError):
    component = "composer"
    code = "composition_error"


class CompositionValidationError(CompositionError):
    code = "composition_validation_error"


class CompositionStateError(CompositionError):
    code = "composition_state_error"


class CompositionBlockedError(CompositionError):
    code = "composition_blocked"


class CompositionCollisionError(CompositionError):
    code = "composition_collision"


class LocalContentIndexError(BridgeError):
    component = "content_index"
    code = "content_index_error"


class LocalContentIndexStoreError(LocalContentIndexError):
    code = "content_index_store_error"


class ContactDirectoryError(BridgeError):
    component = "contact_directory"
    code = "contact_directory_error"


class CoordinatorError(BridgeError):
    """Safe base error for account-registry and migration operations."""

    component = "coordinator"
    code = "coordinator_error"


class CoordinatorSchemaError(CoordinatorError):
    code = "coordinator_schema_error"


class CoordinatorIdentityError(CoordinatorError):
    code = "coordinator_identity_error"


class CoordinatorConflictError(CoordinatorError):
    """A safe, non-enumerating conflict in coordinator-owned state."""

    code = "coordinator_conflict"


class CoordinatorMigrationError(CoordinatorError):
    code = "coordinator_migration_error"


class CoordinatorPreflightError(CoordinatorMigrationError):
    code = "coordinator_preflight_error"


class CoordinatorAuthenticationError(CoordinatorError):
    component = "app_auth"
    code = "app_authentication_error"


class CoordinatorAuthorizationError(CoordinatorAuthenticationError):
    code = "app_authorization_error"


class CoordinatorAuthRateLimitError(CoordinatorAuthenticationError):
    code = "app_auth_rate_limited"
