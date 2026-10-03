"""UI-facing local application API independent of any web framework."""

from __future__ import annotations

import asyncio
import atexit
import base64
import binascii
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
import hmac
import json
import mimetypes
import os
import re
import shutil
import sqlite3
import threading
import time
import unicodedata
import uuid
from datetime import date, datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Mapping
from urllib.parse import parse_qs, urlsplit

from eitaa_core import (
    EitaaAuth,
    EitaaCore,
    EitaaCoreConfig,
    DialogCollection,
    MediaDownloadOptions,
    MessageSearchQuery,
    Peer,
    PeerType,
    BulkMessageSpec,
    BulkRecipientStatus,
    BulkSendOptions,
    MemberSearchQuery,
    MemberRole,
    MemberState,
    PhoneNumber,
    PhoneListResolveOptions,
    MembershipInviteOptions,
    SendKind,
    load_peer_file,
    save_peer_file,
)

from eitaa_core.errors import EitaaCoreError, NetworkError, RpcError

from ..errors import (
    AuthenticationRuntimeError,
    BridgeConfigurationError,
    BridgeError,
    CompositionBlockedError,
    CompositionCollisionError,
    CompositionValidationError,
    ContactDirectoryError,
    CoordinatorAuthenticationError,
    CoordinatorAuthorizationError,
    CoordinatorAuthRateLimitError,
    CoordinatorConflictError,
    CoordinatorSchemaError,
    CredentialError,
    EitaaRuntimeError,
    LocalContentIndexError,
    WordPressAuthenticationError,
    WordPressConnectionError,
    WordPressError,
)
from ..licensing import enforce_installed_license
from ..facade import EitaaBridge
from ..infrastructure.composition_manifest import CompositionManifestLoader
from ..infrastructure.contact_store import (
    ContactMutationContext,
    SQLiteContactStore,
    normalize_phone,
)
from ..infrastructure.config import (
    BridgeConfigLoader,
    DeploymentPortSettings,
    EnvLoader,
    WordPressSiteSettings,
)
from ..infrastructure.coordinator import (
    AccountExecutionPolicyService,
    AppAuthPolicy,
    AuthorizedAppSession,
    CoordinatorAppAuth,
    CoordinatorDatabase,
    IssuedAppSession,
    PersistentOperationJobService,
    ProviderOperationReceiptStore,
    PhoneProtector,
    SafeCoordinatorAuditService,
    WindowsDpapiPhoneProtector,
    classify_failure,
    masked_phone,
    validate_canonical_e164,
)
from ..infrastructure.diagnostics import (
    BridgeDiagnosticManager,
    RuntimeLogger,
    catalog_payload,
    enforce_runtime_log_retention,
    observability_disk_health,
    prune_old_diagnostic_runs,
)
from ..infrastructure.eitaa.dialog_permissions import consume_dialog_account_roles
from ..providers.registry import default_provider_registry
from .reporting_api_v3 import dispatch as _reporting_v3_route_dispatch
from ..providers.contracts import (
    ProviderAccountContext,
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
    ProviderPeerReference,
    ProviderSendReceipt,
    ProviderSendStatus,
    ProviderSendTextRequest,
    SensitiveProviderValue,
)
from ..providers.eitaa import (
    EitaaCompatibilityOperations,
    EitaaProviderApplicationAdapter,
)
from ..version import __version__
from .content_index import DEFAULT_SCORE_THRESHOLD, IndexLabel
from .content_index_service import LocalContentIndexService
from .contact_import import map_contact_rows, parse_tabular
from .account_auth import AccountAuthChallenge, LegacyAuthChallenge
from .account_runtime import EitaaAccountRuntime, EitaaRuntimeRegistry
from .process_runtime import EitaaProcessRuntime
from .provider_adapter import provider_adapter_catalog
from .provider_capabilities import (
    ProviderCapabilityService,
    provider_capability_for_route,
)
from .provider_orchestration import (
    ProviderApplicationOrchestrator,
    ProviderOperationActor,
)
from .scheduler import EitaaPriority
from ..reporting import (
    build_prayer_dossier,
    realization_report,
    ALL_FORMS,
    FORMS_BY_PROGRAM,
    DialogWatchConfig,
    FilledForm,
    FormAnswer,
    ProgramId,
    ProgramKind,
    ReportedEvent,
    ReportingExportError,
    ReportingService,
    ReportingStore,
    UnresolvedStarCellsError,
    UnitScope,
)


_LOCALIZED_LOGIN_CODE_DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)
_LOGIN_CODE_DIRECTION_MARKS = frozenset(
    "\u200c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
)


def _normalize_login_code(value: Any) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    translated = normalized.translate(_LOCALIZED_LOGIN_CODE_DIGITS)
    return "".join(
        character
        for character in translated
        if not character.isspace() and character not in _LOGIN_CODE_DIRECTION_MARKS
    )


_MIGRATED_PROCESS_AUTH_ROUTES = frozenset(
    {
        ("GET", "/api/v1/auth/status"),
        ("POST", "/api/v1/auth/request-code"),
        ("POST", "/api/v1/auth/submit-code"),
        ("POST", "/api/v1/auth/submit-password"),
        ("POST", "/api/v1/auth/logout"),
        ("POST", "/api/v1/auth/reset-local-session"),
        ("POST", "/api/v1/auth/recover-phone-identity"),
    }
)


def _is_migrated_process_auth_route(method: str, path: str) -> bool:
    """Whether this v1 route already executes through the auth Child RPC."""

    return (method, path) in _MIGRATED_PROCESS_AUTH_ROUTES


def _provider_login_code_failure(error: RpcError) -> tuple[str, str, str, str]:
    provider_text = str(getattr(error, "text", "") or "").upper()
    if "PHONE_CODE_EXPIRED" in provider_text or "PHONE_CODE_HASH" in provider_text:
        return (
            "expired",
            "provider_code_expired",
            "auth_provider_code_expired",
            "کد ورود منقضی شده است. یک کد تازه دریافت کنید.",
        )
    if "PHONE_CODE_INVALID" in provider_text or "PHONE_CODE_EMPTY" in provider_text:
        return (
            "invalid",
            "provider_code_invalid",
            "auth_provider_code_invalid",
            "کد ورود صحیح نیست. کد تازهٔ ایتا را دوباره وارد کنید.",
        )
    if "FLOOD" in provider_text:
        return (
            "rate_limited",
            "provider_code_rate_limited",
            "auth_provider_code_rate_limited",
            "تعداد تلاش‌ها زیاد بوده است. کمی بعد یک کد تازه دریافت کنید.",
        )
    return (
        "rejected",
        "provider_code_rejected",
        "auth_provider_code_rejected",
        "ایتا کد ورود را نپذیرفت. یک کد تازه دریافت و دوباره تلاش کنید.",
    )


@dataclass(slots=True, frozen=True)
class ServiceAuthContext:
    service_id: str
    service_name: str
    allowed_providers: list[str]
    allowed_messenger_account_ids: list[str] | None
    scopes: list[str]

@dataclass(slots=True, frozen=True)
class ApiResponse:
    status: int
    payload: dict[str, Any]
    headers: dict[str, str] = field(default_factory=dict)


APP_USER_SESSION_COOKIE = "eitaa_bridge_app_session"
_APP_USER_UPDATE_ROUTE = re.compile(
    r"^/api/v2/app-users/(?P<app_user_id>[0-9a-fA-F-]{36})/update$"
)
_APP_USER_REVOKE_SESSIONS_ROUTE = re.compile(
    r"^/api/v2/app-users/(?P<app_user_id>[0-9a-fA-F-]{36})/revoke-sessions$"
)
_PHONE_ACCOUNT_MEMBERSHIPS_ROUTE = re.compile(
    r"^/api/v2/phone-accounts/(?P<phone_account_id>[0-9a-fA-F-]{36})/memberships$"
)
_APP_INTEGRATION_UPDATE_ROUTE = re.compile(
    r"^/api/v2/app-integrations/(?P<integration_id>[0-9a-fA-F-]{36})/update$"
)
_APP_SESSION_REVOKE_ROUTE = re.compile(
    r"^/api/v2/app-auth/sessions/(?P<session_id>[0-9a-fA-F-]{36})/revoke$"
)
_MESSENGER_ACCOUNT_ROUTE = re.compile(
    r"^/api/v2/messenger-accounts/(?P<messenger_account_id>[0-9a-fA-F-]{36})$"
)
_MESSENGER_ACCOUNT_CAPABILITIES_ROUTE = re.compile(
    r"^/api/v2/messenger-accounts/(?P<messenger_account_id>[0-9a-fA-F-]{36})/capabilities$"
)
_MESSENGER_ACCOUNT_WORKER_ROUTE = re.compile(
    r"^/api/v2/messenger-accounts/(?P<messenger_account_id>[0-9a-fA-F-]{36})/worker/(?P<action>start|stop)$"
)
_MESSENGER_ACCOUNT_DIALOG_QUERY_ROUTE = re.compile(
    r"^/api/v2/messenger-accounts/(?P<messenger_account_id>[0-9a-fA-F-]{36})/dialogs/query$"
)
_MESSENGER_ACCOUNT_HISTORY_QUERY_ROUTE = re.compile(
    r"^/api/v2/messenger-accounts/(?P<messenger_account_id>[0-9a-fA-F-]{36})/history/query$"
)
_MESSENGER_ACCOUNT_SEND_TEXT_ROUTE = re.compile(
    r"^/api/v2/messenger-accounts/(?P<messenger_account_id>[0-9a-fA-F-]{36})/messages/send-text$"
)
_MESSENGER_ACCOUNT_MEDIA_READ_ROUTE = re.compile(
    r"^/api/v2/messenger-accounts/(?P<messenger_account_id>[0-9a-fA-F-]{36})/media/read$"
)
_MESSENGER_ACCOUNT_CONTACT_QUERY_ROUTE = re.compile(
    r"^/api/v2/messenger-accounts/(?P<messenger_account_id>[0-9a-fA-F-]{36})/contacts/query$"
)
_MESSENGER_ACCOUNT_CONTACT_UPSERT_ROUTE = re.compile(
    r"^/api/v2/messenger-accounts/(?P<messenger_account_id>[0-9a-fA-F-]{36})/contacts/upsert$"
)
_REPORTING_CANDIDATE_REVIEW_ROUTE = re.compile(
    r"^/api/v2/reporting/candidates/(?P<candidate_id>[a-zA-Z0-9_-]+)/review$"
)
_REPORTING_CANDIDATE_SUGGEST_ROUTE = re.compile(
    r"^/api/v2/reporting/candidates/(?P<candidate_id>[a-zA-Z0-9_-]+)/suggest$"
)
_OFFICE_NORMALIZE_REVIEW_ROUTE = re.compile(
    r"^/api/v3/office/queue/(?P<candidate_id>[a-zA-Z0-9_-]+)/review$"
)
_OFFICE_WP_LINK_ACTION_ROUTE = re.compile(
    r"^/api/v3/office/wp-links/(?P<link_id>[a-zA-Z0-9_-]+)/(?P<action>link|unlink)$"
)
_REPORTING_FORM_ROUTE = re.compile(
    r"^/api/v2/reporting/forms/(?P<program_id>[a-zA-Z0-9_-]+)$"
)
_REPORTING_MANDATE_ROUTE = re.compile(
    r"^/api/v2/reporting/mandates/(?P<mandate_id>[a-zA-Z0-9_-]+)$"
)
_SAFE_LOG_ROUTE_SEGMENT = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
_SAFE_CLIENT_ERROR_TYPE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,80}$")
_CLIENT_DIAGNOSTIC_EVENTS = frozenset(
    {
        "renderer_render_error",
        "renderer_unhandled_error",
        "renderer_unhandled_rejection",
    }
)


def _safe_log_path(path: str) -> str:
    """Keep route shape while excluding identifiers or attacker-supplied secrets."""

    segments: list[str] = []
    for segment in str(path or "/").split("/"):
        if not segment:
            continue
        lowered = segment.lower()
        segments.append(lowered if _SAFE_LOG_ROUTE_SEGMENT.fullmatch(lowered) else "{redacted}")
    return "/" + "/".join(segments)


class BridgeApplicationApi:
    """Stable JSON API consumed by the future local UI.

    This class performs routing and validation without depending on FastAPI,
    Flask, SQL, or Core internals. The HTTP adapter is intentionally thin.
    """

    API_VERSION = "v1"
    MAX_MEDIA_MB = 1024

    def __init__(
        self,
        config_path: str | Path = "bridge.json",
        *,
        env_file: str | Path | None = None,
        bearer_token: str | None = None,
        phone_protector: PhoneProtector | None = None,
    ) -> None:
        self.config_path = Path(config_path).expanduser().resolve()
        self.env_file = Path(env_file).expanduser().resolve() if env_file else None
        # Packaged installations fail closed before Config, Coordinator DB,
        # Provider runtime, or diagnostics state is opened. Development trees
        # are not gated unless they carry the explicit release policy marker.
        enforce_installed_license(self.config_path.parent)
        config = BridgeConfigLoader.load(self.config_path, env_file=self.env_file)
        self.config = config
        EnvLoader.load(config.env_file)
        configured_token = bearer_token if bearer_token is not None else os.getenv("EITAA_BRIDGE_API_TOKEN")
        self.bearer_token = configured_token.strip() if configured_token and configured_token.strip() else None
        self.base_directory = config.source_file.parent
        self._provider_registry = default_provider_registry()
        coordinator_database = (
            self.base_directory / "data" / "coordinator" / "coordinator.sqlite3"
        )
        self.app_user_auth_enabled = config.features.app_user_auth.enabled
        self.app_user_self_registration_enabled = bool(
            self.app_user_auth_enabled
            and config.features.app_user_auth.self_registration_enabled
            and config.deployment.mode in {"desktop_loopback", "trusted_lan_http"}
        )
        self._app_auth: CoordinatorAppAuth | None = None
        clean_install_bootstrap = False
        if self.app_user_auth_enabled:
            coordinator_store = CoordinatorDatabase(coordinator_database)
            coordinator_store.initialize()
            coordinator_counts = coordinator_store.safe_summary()["counts"]
            clean_install_bootstrap = all(
                int(coordinator_counts[key]) == 0
                for key in ("app_users", "phone_accounts", "messenger_accounts")
            )
            policy = config.features.app_user_auth
            app_auth_kwargs: dict[str, object] = {
                "policy": AppAuthPolicy(
                    idle_timeout_minutes=policy.idle_timeout_minutes,
                    absolute_timeout_hours=policy.absolute_timeout_hours,
                    max_failed_attempts=policy.max_failed_attempts,
                    lockout_minutes=policy.lockout_minutes,
                )
            }
            if phone_protector is not None:
                app_auth_kwargs["phone_protector"] = phone_protector
            self._app_auth = CoordinatorAppAuth(
                coordinator_database,
                **app_auth_kwargs,
            )
            self._app_auth.initialize()
        self._application_diagnostics = BridgeDiagnosticManager(
            config.diagnostics.root, enabled=config.diagnostics.enabled
        )
        self._application_logger = RuntimeLogger(
            self.base_directory / "runtime" / "logs" / "application.jsonl",
            source="application",
        )
        runtime_registry: EitaaRuntimeRegistry | None = None
        try:
            # A restart with only created or paused accounts is the same
            # onboarding state as an empty install: no worker can run yet,
            # and the explicit UI Start is what promotes the account.
            coordinator_store = CoordinatorDatabase(coordinator_database)
            no_runnable_account = (
                config.features.multi_session.enabled
                and not coordinator_store.has_runnable_messenger_account()
            )
            allow_onboarding_bootstrap = clean_install_bootstrap or no_runnable_account
            runtime_registry = EitaaRuntimeRegistry(
                config,
                application_diagnostics=self._application_diagnostics,
                application_logger=self._application_logger,
                coordinator_database=coordinator_database,
                allow_empty_bootstrap=allow_onboarding_bootstrap,
            )
            selected_runtime: EitaaAccountRuntime | EitaaProcessRuntime | None
            if config.features.multi_session.enabled:
                if allow_onboarding_bootstrap:
                    # With no runnable account, onboarding must remain reachable
                    # after the first admin has been created as well as on an
                    # entirely empty install. Process mode has no v1 runtime;
                    # in-process mode can retain its inert legacy runtime.
                    selected_runtime = (
                        None
                        if config.features.worker_process.enabled
                        else runtime_registry.legacy_runtime
                    )
                else:
                    try:
                        selected_runtime = runtime_registry.resolve_v1()
                    except EitaaRuntimeError as exc:
                        if exc.code != "eitaa_runtime_account_not_runnable":
                            raise
                        if config.features.worker_process.enabled:
                            raise
                        selected_runtime = runtime_registry.legacy_runtime
            else:
                selected_runtime = runtime_registry.legacy_runtime
        except Exception as exc:
            if runtime_registry is not None:
                runtime_registry.close()
            self._application_logger.emit(
                "application_start_failed",
                level="error",
                reason_code="application_runtime_initialization_failed",
                fields={"error_type": type(exc).__name__},
            )
            self._application_logger.close()
            raise
        self._runtime_registry = runtime_registry
        self._coordinator: CoordinatorDatabase | None = None
        self._persistent_job_service: PersistentOperationJobService | None = None
        self._execution_policy: AccountExecutionPolicyService | None = None
        self._coordinator_audit: SafeCoordinatorAuditService | None = None
        self._provider_capability_service: ProviderCapabilityService | None = None
        self._provider_receipt_store: ProviderOperationReceiptStore | None = None
        self._persistent_job_worker_id = str(uuid.uuid4())
        self._persistent_job_lease_lock = threading.RLock()
        self._persistent_job_lease_stops: dict[str, threading.Event] = {}
        self._m2m_rate_limit_lock = threading.Lock()
        self._m2m_rate_limit_history: dict[str, list[float]] = {}
        self._m2m_failed_verify_lock = threading.Lock()
        self._m2m_failed_verify_history: list[float] = []
        if coordinator_database.is_file():
            self._coordinator = CoordinatorDatabase(coordinator_database)
            provider_reconciliation = self._coordinator.reconcile_provider_registrations(
                self._provider_registry.persistence_catalog()
            )
            if provider_reconciliation["created"] or provider_reconciliation["updated"]:
                self._application_logger.emit(
                    "provider_registry_reconciled",
                    result="succeeded",
                    fields=provider_reconciliation,
                )
            self._provider_capability_service = ProviderCapabilityService(
                self._coordinator,
                self._provider_registry,
            )
            self._coordinator.reconcile_wordpress_integrations(
                [
                    {
                        "integration_key": site.site_key,
                        "display_name": f"WordPress ({site.site_key})",
                    }
                    for site in config.wordpress_sites
                ]
            )
            self._persistent_job_service = PersistentOperationJobService(
                self._coordinator
            )
            self._provider_receipt_store = ProviderOperationReceiptStore(
                self._coordinator
            )
            self._execution_policy = AccountExecutionPolicyService(
                self._coordinator
            )
            self._coordinator_audit = SafeCoordinatorAuditService(
                self._coordinator
            )
            recovery = self._persistent_job_service.recover_expired_jobs()
            if any(recovery.safe_summary().values()):
                self._application_logger.emit(
                    "persistent_jobs_recovered", fields=recovery.safe_summary()
                )
        reporting_db = self.base_directory / "data" / "reporting" / "reporting.sqlite3"
        self._reporting_store = ReportingStore(reporting_db)
        self._reporting_service = ReportingService(store=self._reporting_store)
        self._request_runtime: ContextVar[
            EitaaAccountRuntime | EitaaProcessRuntime | None
        ] = ContextVar(
            f"eitaa_bridge_request_runtime_{id(self)}",
            default=None,
        )
        self._request_actor_app_user_id: ContextVar[str | None] = ContextVar(
            f"eitaa_bridge_request_actor_{id(self)}",
            default=None,
        )
        self._request_actor_global_role: ContextVar[str | None] = ContextVar(
            f"eitaa_bridge_request_actor_role_{id(self)}",
            default=None,
        )
        self._request_service_auth_context: ContextVar[ServiceAuthContext | None] = ContextVar(
            f"eitaa_bridge_request_service_auth_context_{id(self)}",
            default=None,
        )
        self._provider_operation_site_key: ContextVar[str | None] = ContextVar(
            f"eitaa_bridge_provider_operation_site_{id(self)}",
            default=None,
        )
        eitaa_provider = self._provider_registry.registration("eitaa").manifest.provider
        self._provider_application_adapter_factories = {
            eitaa_provider: self._create_eitaa_application_adapter,
        }
        self._provider_orchestrator = ProviderApplicationOrchestrator(
            authorize_account=self._authorize_provider_operation_account,
            resolve_account_context=self._provider_operation_account_context,
            require_capability=lambda account_id, capability: (
                self._require_provider_capability_service().require(
                    account_id, capability
                )
            ),
            resolve_adapter=self._resolve_provider_application_adapter,
            logger=self._application_logger,
            receipt_store=self._provider_receipt_store,
        )
        # Chat gateway wiring: the agent adapter is selected only from an
        # explicit bridge.json "agent_gateway" section; without it the marked
        # test adapter answers. An invalid section fails startup (no guesses).
        from .agent_gateway import configure_default_adapter
        try:
            raw_config = json.loads(Path(config_path).read_text(encoding="utf-8"))
            agent_section = (
                raw_config.get("agent_gateway")
                if isinstance(raw_config, dict)
                else None
            )
        except (OSError, ValueError):
            agent_section = None
        configure_default_adapter(agent_section)
        self._client_diagnostic_lock = threading.RLock()
        self._client_diagnostic_windows: dict[str, list[float]] = {}
        self._bind_runtime(selected_runtime)
        self._media_token_scope_lock = threading.RLock()
        self._media_token_accounts: dict[str, str | None] = {}
        threading.Thread(
            target=self._prune_diagnostics,
            name="bridge-diagnostics-prune",
            daemon=True,
        ).start()
        self._application_logger.emit(
            "content_auto_index_scheduler_skipped",
            result="rejected",
            reason_code="content_auto_index_scheduler_disabled_safe_default",
            correlation_id=RuntimeLogger.correlation_id(),
            fields={
                "manual_index_available": True,
                "mode": "disabled_safe_default",
            },
        )
        self._contact_store = SQLiteContactStore(
            self.base_directory / "data" / "contacts.sqlite3"
        )
        self._contact_store.reconcile_provider_registrations(
            self._provider_registry.persistence_catalog()
        )
        self._application_logger.emit(
            "application_started",
            result="succeeded",
            fields={
                "deployment_mode": self.config.deployment.mode,
                "app_user_auth_enabled": self.app_user_auth_enabled,
                "multi_session_enabled": self.config.features.multi_session.enabled,
                "clean_install_bootstrap": clean_install_bootstrap,
            },
        )
        atexit.register(self.close)

    def _bind_runtime(
        self,
        runtime: EitaaAccountRuntime | EitaaProcessRuntime | None,
    ) -> None:
        """Bind API v1 compatibility fields to one explicit runtime owner."""

        self._v1_runtime = runtime

    @property
    def _runtime(self) -> EitaaAccountRuntime | EitaaProcessRuntime:
        selected = self._request_runtime.get()
        if selected is not None:
            return selected
        if self._v1_runtime is None:
            raise EitaaRuntimeError(
                "Select and start a messaging account before using the workspace.",
                code="messenger_account_selection_required",
            )
        return self._v1_runtime

    def _scoped_cache_key(self, namespace: str, *parts: object) -> str:
        return self._runtime.data_scope.key(namespace, *parts)

    def __getattr__(self, name: str) -> Any:
        runtime_fields = {
            "_diagnostics": "diagnostics",
            "_runtime_logger": "logger",
            "_media_cache_lock": "media_cache_lock",
            "_media_cache_files": "media_cache_files",
            "_avatar_source_cache_lock": "avatar_source_cache_lock",
            "_avatar_source_cache": "avatar_source_cache",
            "_avatar_source_cache_ttl_seconds": "avatar_source_cache_ttl_seconds",
            "_auth_lock": "auth_lock",
            "_eitaa_lock": "eitaa_lock",
            "_scheduler": "scheduler",
            "_jobs_lock": "jobs_lock",
            "_dialog_sync_jobs": "dialog_sync_jobs",
            "_content_index_lock": "content_index_lock",
            "_content_index_jobs": "content_index_jobs",
            "_content_index_active": "content_index_active",
            "_content_index_cancellations": "content_index_cancellations",
            "_content_index_store": "content_index_store",
            "_sender_directory": "sender_directory",
            "_contact_import_lock": "contact_import_lock",
            "_contact_import_jobs": "contact_import_jobs",
            "_contact_import_cancellations": "contact_import_cancellations",
            "_eitaa_contacts_cache_lock": "eitaa_contacts_cache_lock",
            "_eitaa_contacts_cache": "eitaa_contacts_cache",
            "_eitaa_contacts_cache_ttl_seconds": "eitaa_contacts_cache_ttl_seconds",
            "_background_tasks": "background_tasks",
            "_read_queue_lock": "read_queue_lock",
            "_pending_read_receipts": "pending_read_receipts",
            "_read_receipt_delay_seconds": "read_receipt_delay_seconds",
            "dialog_catalog": "dialog_catalog",
        }
        selected = runtime_fields.get(name)
        if selected is None:
            raise AttributeError(name)
        return getattr(self._runtime, selected)

    @property
    def upload_root(self) -> Path:
        """Upload staging root owned by the v1-selected runtime."""

        return self._runtime.upload_directory

    @property
    def _active_dialog_sync_job(self) -> str | None:
        return self._runtime.active_dialog_sync_job

    @_active_dialog_sync_job.setter
    def _active_dialog_sync_job(self, value: str | None) -> None:
        self._runtime.active_dialog_sync_job = value

    @property
    def _read_worker_active(self) -> bool:
        return self._runtime.read_worker_active

    @_read_worker_active.setter
    def _read_worker_active(self, value: bool) -> None:
        self._runtime.read_worker_active = value

    @property
    def _auth_runtime(self) -> EitaaAuth | None:
        return self._runtime.auth_runtime

    @_auth_runtime.setter
    def _auth_runtime(self, value: EitaaAuth | None) -> None:
        self._runtime.auth_runtime = value

    @property
    def _auth_challenge(self) -> Any | None:
        return self._runtime.auth_challenge

    @_auth_challenge.setter
    def _auth_challenge(self, value: Any | None) -> None:
        self._runtime.auth_challenge = value

    def register_media_cache_file(self, path: Path, mime_type: str) -> str:
        """Register a cached UI media file under an unguessable process-local token."""
        resolved = path.expanduser().resolve()
        if self._runtime.ownership.account_data_directory is not None:
            media_root = self._runtime.ownership.core.media_directory.resolve()
            try:
                resolved.relative_to(media_root)
            except ValueError as exc:
                raise CompositionValidationError(
                    "The media cache file is outside the selected account.",
                    code="api_media_cache_account_boundary",
                ) from exc
        token = uuid.uuid4().hex
        with self._media_cache_lock:
            now = time.monotonic()
            self._media_cache_files[token] = (
                resolved,
                mime_type,
                now,
                self._runtime.data_scope.scope_key,
            )
            with self._media_token_scope_lock:
                self._media_token_accounts[token] = (
                    self._runtime.ownership.messenger_account_id
                )
            if len(self._media_cache_files) > 256:
                oldest = sorted(self._media_cache_files.items(), key=lambda item: item[1][2])[:64]
                for key, _ in oldest:
                    self._media_cache_files.pop(key, None)
                    with self._media_token_scope_lock:
                        self._media_token_accounts.pop(key, None)
        return token

    def resolve_media_cache_file(
        self,
        token: str,
        *,
        messenger_account_id: str | None = None,
    ) -> tuple[Path, str] | None:
        context_token = None
        selected_runtime: EitaaAccountRuntime | EitaaProcessRuntime | None = None
        if messenger_account_id:
            selected_runtime = self._runtime_registry.runtime_for_account(
                messenger_account_id
            )
            context_token = self._request_runtime.set(selected_runtime)
        if len(token) != 32 or any(character not in "0123456789abcdef" for character in token):
            if context_token is not None:
                self._request_runtime.reset(context_token)
            return None
        try:
            if isinstance(selected_runtime, EitaaProcessRuntime):
                return None
            with self._media_cache_lock:
                item = self._media_cache_files.get(token)
                if item is None:
                    return None
                path, mime_type, _, stored_scope = item
                if stored_scope != self._runtime.data_scope.scope_key:
                    return None
                if not path.is_file():
                    self._media_cache_files.pop(token, None)
                    with self._media_token_scope_lock:
                        self._media_token_accounts.pop(token, None)
                    return None
                self._media_cache_files[token] = (
                    path,
                    mime_type,
                    time.monotonic(),
                    stored_scope,
                )
                return path, mime_type
        finally:
            if context_token is not None:
                self._request_runtime.reset(context_token)

    def read_remote_media_cache_chunk(
        self,
        token: str,
        *,
        messenger_account_id: str | None,
        offset: int,
        max_bytes: int = 192 * 1024,
    ) -> tuple[bytes, str, int, int, bool] | None:
        """Read one bounded child-owned media chunk without exposing its path."""

        if (
            not messenger_account_id
            or not re.fullmatch(r"[0-9a-f]{32}", str(token or ""))
            or isinstance(offset, bool)
            or not isinstance(offset, int)
            or offset < 0
            or isinstance(max_bytes, bool)
            or not isinstance(max_bytes, int)
            or not 1 <= max_bytes <= 192 * 1024
        ):
            return None
        runtime = self._runtime_registry.runtime_for_account(
            messenger_account_id
        )
        if not isinstance(runtime, EitaaProcessRuntime):
            return None
        try:
            payload = runtime.provider_operation_request(
                "eitaa.provider.media.read_chunk",
                {
                    "cache_reference": f"cache:{token}",
                    "offset": offset,
                    "max_bytes": max_bytes,
                },
                timeout_seconds=30.0,
            )
        except EitaaRuntimeError as exc:
            if exc.code in {
                "provider_media_content_not_found",
                "provider_media_content_reference_invalid",
            }:
                with self._media_token_scope_lock:
                    self._media_token_accounts.pop(token, None)
                return None
            raise
        try:
            content_reference = str(payload.get("content_reference") or "")
            mime_type = str(payload.get("mime_type") or "")
            total = int(payload.get("total_bytes"))
            returned_offset = int(payload.get("offset"))
            next_offset = int(payload.get("next_offset"))
            eof = payload.get("eof")
            encoded = payload.get("data_base64")
            if not isinstance(encoded, str) or not isinstance(eof, bool):
                raise ValueError("shape")
            data = base64.b64decode(encoded.encode("ascii"), validate=True)
        except (TypeError, ValueError, UnicodeError, binascii.Error) as exc:
            raise EitaaRuntimeError(
                "The Eitaa Child media chunk result is invalid.",
                code="eitaa_process_provider_result_invalid",
            ) from exc
        if (
            content_reference != f"cache:{token}"
            or not re.fullmatch(
                r"[a-z0-9][a-z0-9.+-]{0,63}/[a-z0-9][a-z0-9.+-]{0,63}",
                mime_type.lower(),
            )
            or not 0 <= total <= 512 * 1024 * 1024
            or returned_offset != offset
            or next_offset != offset + len(data)
            or next_offset > total
            or len(data) > max_bytes
            or (not data and next_offset < total)
            or eof != (next_offset >= total)
        ):
            raise EitaaRuntimeError(
                "The Eitaa Child media chunk result is invalid.",
                code="eitaa_process_provider_result_invalid",
            )
        return data, mime_type.lower(), total, next_offset, eof

    def upload_root_for_account(self, messenger_account_id: str | None) -> Path:
        if not messenger_account_id:
            return self.upload_root
        return self._runtime_registry.runtime_for_account(
            messenger_account_id
        ).upload_directory

    def _prune_diagnostics(self) -> None:
        result = prune_old_diagnostic_runs(
            self._application_diagnostics.root,
            protected_run_ids={self._application_diagnostics.run_id},
            keep_newest=50,
            max_age_days=30,
        )
        if result["removed"] or result["failed"]:
            self._application_logger.emit("diagnostics_pruned", fields=result)
        runtime_logs = enforce_runtime_log_retention(self.base_directory)
        disk = observability_disk_health(self.base_directory)
        degraded = bool(
            result["failed"]
            or runtime_logs["failed"]
            or disk["status"] != "healthy"
        )
        self._application_logger.emit(
            "observability_maintenance_completed",
            level="warning" if degraded else "info",
            result="degraded" if degraded else "succeeded",
            reason_code="observability_maintenance_degraded" if degraded else None,
            fields={"diagnostics": result, "runtime_logs": runtime_logs, "disk": disk},
        )

    def _runtime_bound_target(self, callback: Any) -> Any:
        """Capture the current account for work that continues on another thread."""

        runtime = self._runtime
        correlation_id = RuntimeLogger.current_correlation_id()
        actor_app_user_id = self._request_actor_app_user_id.get()
        actor_global_role = self._request_actor_global_role.get()

        def bound(*args: Any, **kwargs: Any) -> Any:
            token = self._request_runtime.set(runtime)
            actor_token = self._request_actor_app_user_id.set(actor_app_user_id)
            role_token = self._request_actor_global_role.set(actor_global_role)
            correlation_token = RuntimeLogger.bind_correlation_id(correlation_id)
            try:
                return callback(*args, **kwargs)
            finally:
                RuntimeLogger.reset_correlation_id(correlation_token)
                self._request_actor_app_user_id.reset(actor_token)
                self._request_actor_global_role.reset(role_token)
                self._request_runtime.reset(token)

        return bound

    def _persistent_job_create(
        self,
        operation: str,
        *,
        recipient_ref_hashes: tuple[str, ...] = (),
    ) -> str:
        service = self._persistent_job_service
        actor_id = self._request_actor_app_user_id.get()
        actor_role = self._request_actor_global_role.get()
        account_id = self._runtime.ownership.messenger_account_id
        if service is None or not actor_id or not actor_role or not account_id:
            return uuid.uuid4().hex
        created = service.create_job(
            actor_app_user_id=actor_id,
            actor_global_role=actor_role,
            messenger_account_id=account_id,
            operation=operation,
            idempotency_key=f"job:{uuid.uuid4().hex}",
            safe_payload_ref=f"api:{operation}",
            recipient_ref_hashes=recipient_ref_hashes,
        )
        return created.job.job_id

    def _persistent_job_begin(self, job_id: str) -> None:
        service = self._persistent_job_service
        if service is None or len(job_id) != 36:
            return
        record = service.get_job(job_id)
        if self._execution_policy is not None:
            permit = self._execution_policy.acquire(
                messenger_account_id=record.messenger_account_id,
                operation_scope=record.operation,
                claim_id=job_id,
            )
            if not permit.allowed:
                raise EitaaRuntimeError(
                    "The selected MessengerAccount operation is temporarily deferred.",
                    code="account_execution_deferred",
                    safe_context={
                        "retry_after_ms": permit.retry_after_ms,
                        "blocked_reason": permit.blocked_reason,
                        "circuit_state": permit.circuit_state,
                    },
                )
        service.lease_job(
            job_id,
            worker_id=self._persistent_job_worker_id,
            worker_generation=1,
            lease_seconds=300,
        )
        service.start_attempt(
            job_id,
            worker_id=self._persistent_job_worker_id,
            worker_generation=1,
        )
        stop = threading.Event()
        with self._persistent_job_lease_lock:
            self._persistent_job_lease_stops[job_id] = stop

        def renew() -> None:
            while not stop.wait(90):
                try:
                    service.renew_lease(
                        job_id,
                        worker_id=self._persistent_job_worker_id,
                        worker_generation=1,
                        lease_seconds=300,
                    )
                except BridgeError as exc:
                    self._application_logger.emit(
                        "persistent_job_lease_renew_failed",
                        level="error",
                        fields={"job_id": job_id, "error_code": exc.code},
                    )
                    stop.set()
                except Exception as exc:
                    self._application_logger.emit(
                        "persistent_job_lease_renew_failed",
                        level="error",
                        reason_code="persistent_job_lease_renew_unexpected_error",
                        fields={"job_id": job_id, "error_type": type(exc).__name__},
                    )
                    stop.set()

        threading.Thread(
            target=renew,
            name=f"persistent-job-lease-{job_id[:8]}",
            daemon=True,
        ).start()

    def _persistent_job_finish(
        self,
        job_id: str,
        *,
        state: str,
        error_code: str | None = None,
    ) -> None:
        service = self._persistent_job_service
        if service is None or len(job_id) != 36:
            return
        with self._persistent_job_lease_lock:
            stop = self._persistent_job_lease_stops.pop(job_id, None)
        if stop is not None:
            stop.set()
        result = {
            "completed": "succeeded",
            "succeeded": "succeeded",
            "cancelled": "cancelled",
            "failed": "failed",
        }.get(state, "uncertain")
        selected_code = str(error_code or "").strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_.-]{0,80}", selected_code):
            selected_code = "operation_failed" if result == "failed" else ""
        try:
            record = service.get_job(job_id)
            if record.status != "running":
                return
            retry_after_ms = None
            error_class = None
            if result == "failed" and self._execution_policy is not None:
                classified = classify_failure(selected_code or "operation_failed")
                decision = self._execution_policy.record_failure(
                    messenger_account_id=record.messenger_account_id,
                    operation_scope=record.operation,
                    claim_id=job_id,
                    failure=classified,
                )
                retry_after_ms = decision.retry_after_ms
                error_class = decision.error_class.value
                selected_code = decision.error_code
                result = decision.job_result
            elif result == "uncertain" and self._execution_policy is not None:
                classified = classify_failure(
                    selected_code or "operation_effect_uncertain",
                    effect_may_have_occurred=True,
                )
                decision = self._execution_policy.record_failure(
                    messenger_account_id=record.messenger_account_id,
                    operation_scope=record.operation,
                    claim_id=job_id,
                    failure=classified,
                )
                error_class = decision.error_class.value
                selected_code = decision.error_code
            service.complete_attempt(
                job_id,
                worker_id=self._persistent_job_worker_id,
                worker_generation=1,
                result=result,
                error_class=error_class,
                error_code=selected_code or None,
                retry_after_ms=retry_after_ms,
            )
            if result == "succeeded" and self._execution_policy is not None:
                self._execution_policy.record_success(
                    messenger_account_id=record.messenger_account_id,
                    operation_scope=record.operation,
                    claim_id=job_id,
                )
        except BridgeError as exc:
            self._application_logger.emit(
                "persistent_job_completion_failed",
                level="error",
                fields={"job_id": job_id, "error_code": exc.code},
            )

    def _persistent_job_cancel(self, job_id: str) -> None:
        service = self._persistent_job_service
        actor_id = self._request_actor_app_user_id.get()
        actor_role = self._request_actor_global_role.get()
        if service is None or len(job_id) != 36 or not actor_id or not actor_role:
            return
        service.request_cancel(
            job_id,
            actor_app_user_id=actor_id,
            actor_global_role=actor_role,
        )

    def _persistent_job_snapshot(
        self,
        job_id: str,
        *,
        kind: str,
        identifier_field: str = "job_id",
        state_field: str = "state",
    ) -> dict[str, Any] | None:
        service = self._persistent_job_service
        if service is None or len(job_id) != 36:
            return None
        try:
            record = service.get_job(job_id)
        except BridgeError:
            return None
        if (
            record.actor_app_user_id != self._request_actor_app_user_id.get()
            or record.messenger_account_id
            != self._runtime.ownership.messenger_account_id
        ):
            return None
        state = {
            "pending": "queued",
            "leased": "queued",
            "running": "running",
            "succeeded": "completed",
            "failed": "failed",
            "cancelled": "cancelled",
            "uncertain": "uncertain",
        }[record.status]
        return {
            identifier_field: record.job_id,
            "kind": kind,
            state_field: state,
            "persistent": True,
            "attempt_count": record.attempt_count,
            "cancel_requested": record.cancel_requested_at is not None,
            "completed_at": record.completed_at,
            "last_error_class": record.last_error_class,
            "last_error_code": record.last_error_code,
        }

    @contextmanager
    def _open_bridge(
        self,
        config_path: str | Path,
        *,
        env_file: str | Path | None = None,
        site_key: str | None = None,
        open_core: bool = False,
        wordpress_session: Any | None = None,
        runtime: EitaaAccountRuntime | EitaaProcessRuntime | None = None,
    ) -> Iterator[EitaaBridge]:
        selected_runtime = runtime or self._runtime
        actor_app_user_id = self._request_actor_app_user_id.get()
        if actor_app_user_id and self._coordinator is not None:
            self._coordinator.require_app_integration_access(
                app_user_id=actor_app_user_id,
                integration_type="wordpress",
                integration_key=site_key or self.config.default_site_key,
                operation="use",
            )
        if isinstance(selected_runtime, EitaaProcessRuntime):
            raise EitaaRuntimeError(
                "This provider operation has not been migrated to a DTO-based Child RPC.",
                code="eitaa_process_operation_ipc_required",
            )
        # The shared Core owns a thread-affine SQLite connection.  Reuse it only
        # on the scheduler worker that created and serializes it; ordinary HTTP
        # request threads receive a short-lived owned Core instead.
        reuse_core = bool(
            open_core and selected_runtime.scheduler.is_worker_thread()
        )
        scope = selected_runtime.operation_scope() if open_core else nullcontext()
        with scope:
            opened = EitaaBridge.open(
                config_path,
                env_file=env_file,
                site_key=site_key,
                open_core=open_core,
                wordpress_session=wordpress_session,
                diagnostics=selected_runtime.diagnostics,
                reuse_core=reuse_core,
                core_config_override=selected_runtime.ownership.core,
                data_scope=selected_runtime.data_scope,
                actor_app_user_id=actor_app_user_id,
            )
            with opened as bridge:
                yield bridge

    def close(self) -> None:
        self._application_logger.emit(
            "application_stopping",
            result="started",
            fields={"reason_code": "application_close_requested"},
        )
        with self._persistent_job_lease_lock:
            lease_stops = tuple(self._persistent_job_lease_stops.values())
            self._persistent_job_lease_stops.clear()
        for stop in lease_stops:
            stop.set()
        try:
            self._runtime_registry.close()
        except Exception as exc:
            self._application_logger.emit(
                "application_stop_failed",
                level="error",
                reason_code="application_runtime_close_failed",
                fields={"error_type": type(exc).__name__},
            )
            raise
        else:
            self._application_logger.emit(
                "application_stopped",
                result="succeeded",
                fields={"reason_code": "application_close_completed"},
            )
        finally:
            self._application_logger.close()

    def dispatch(
        self,
        method: str,
        raw_path: str,
        *,
        body: Mapping[str, Any] | None = None,
        authorization: str | None = None,
        app_session_token: str | None = None,
        csrf_token: str | None = None,
        client_kind: str = "api",
        client_address: str | None = None,
        messenger_account_id: str | None = None,
        correlation_id: str | None = None,
    ) -> ApiResponse:
        started = time.perf_counter()
        request_id = self._application_logger.correlation_id(correlation_id)
        parsed = urlsplit(raw_path)
        path = parsed.path.rstrip("/") or "/"
        selected_method = method.upper().strip()
        runtime_token = self._request_runtime.set(None)
        actor_token = self._request_actor_app_user_id.set(None)
        role_token = self._request_actor_global_role.set(None)
        correlation_token = RuntimeLogger.bind_correlation_id(request_id)
        try:
            response = self._dispatch_inner(
                method,
                raw_path,
                body=body,
                authorization=authorization,
                app_session_token=app_session_token,
                csrf_token=csrf_token,
                client_kind=client_kind,
                client_address=client_address,
                request_id=request_id,
                messenger_account_id=messenger_account_id,
            )
        except Exception as exc:
            response = self._error_response(exc)
        try:
            error = response.payload.get("error") if isinstance(response.payload, dict) else None
            selected_runtime = self._request_runtime.get() or self._v1_runtime
            request_fields = {
                "request_id": request_id,
                "method": selected_method,
                "path": _safe_log_path(path),
                "status": response.status,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                "error_code": error.get("error_code") if isinstance(error, dict) else None,
                "messenger_account_id": (
                    selected_runtime.ownership.messenger_account_id
                    if selected_runtime is not None
                    else None
                ),
                "app_user_id": self._request_actor_app_user_id.get(),
            }
            level = "error" if response.status >= 500 else ("warning" if response.status >= 400 else "info")
            result = "failed" if response.status >= 500 else ("rejected" if response.status >= 400 else "succeeded")
            self._application_logger.emit(
                "api_request",
                level=level,
                result=result,
                reason_code=(
                    str(request_fields["error_code"] or "api_request_failed")
                    if response.status >= 400
                    else None
                ),
                fields=request_fields,
            )
            if (
                selected_runtime is not None
                and selected_runtime.logger is not self._application_logger
            ):
                selected_runtime.logger.emit(
                    "account_api_request",
                    level=level,
                    result=result,
                    reason_code=(
                        str(request_fields["error_code"] or "api_request_failed")
                        if response.status >= 400
                        else None
                    ),
                    fields=request_fields,
                )
            return response
        finally:
            RuntimeLogger.reset_correlation_id(correlation_token)
            self._request_actor_app_user_id.reset(actor_token)
            self._request_actor_global_role.reset(role_token)
            self._request_runtime.reset(runtime_token)

    def _dispatch_inner(
        self,
        method: str,
        raw_path: str,
        *,
        body: Mapping[str, Any] | None = None,
        authorization: str | None = None,
        app_session_token: str | None = None,
        csrf_token: str | None = None,
        client_kind: str = "api",
        client_address: str | None = None,
        request_id: str | None = None,
        messenger_account_id: str | None = None,
    ) -> ApiResponse:
        try:
            selected_method = method.upper().strip()
            parsed = urlsplit(raw_path)
            path = parsed.path.rstrip("/") or "/"
            query = {key: values[-1] for key, values in parse_qs(parsed.query, keep_blank_values=True).items()}
            payload = dict(body or {})
            # Every request starts with a clean actor/service identity: stale
            # M2M context from a previous request on this execution context
            # must never influence authorization (F-085 gap #1).
            self._request_actor_app_user_id.set(None)
            self._request_actor_global_role.set(None)
            self._request_service_auth_context.set(None)
            # M2M routes authenticate with their own service credential below;
            # the legacy shared bearer must not shadow them.
            if not self.app_user_auth_enabled and not path.startswith("/api/v2/m2m/"):
                self._authorize(authorization)
            forged_account_fields = self._untrusted_account_context_fields(
                {"body": payload, "query": query}
            )
            if path.startswith("/api/v1/") and forged_account_fields:
                raise CompositionValidationError(
                    "Account context is selected by the authenticated server request only.",
                    code=(
                        "api_contact_target_account_not_trusted"
                        if path.startswith("/api/v1/contacts/")
                        else "api_account_context_not_writable"
                    ),
                    safe_context={"rejected_fields": sorted(forged_account_fields)},
                )

            if selected_method == "GET" and path == "/api/v1/health":
                return ApiResponse(200, self._health())
            if selected_method == "GET" and path == "/api/v1/readiness":
                return ApiResponse(200, self._readiness())
            if selected_method == "GET" and path == "/api/v1/schema":
                return ApiResponse(200, self._schema())
            if selected_method == "GET" and path == "/api/v2/app-auth/status":
                return self._app_auth_status(
                    app_session_token,
                    request_id=request_id,
                )
            if selected_method == "POST" and path == "/api/v2/app-auth/setup":
                return self._app_auth_setup(
                    payload,
                    client_kind=client_kind,
                    request_id=request_id,
                )
            if selected_method == "POST" and path == "/api/v2/app-auth/login":
                return self._app_auth_login(
                    payload,
                    client_kind=client_kind,
                    client_address=(
                        client_address
                        if self.config.deployment.mode
                        in {"trusted_lan_http", "web_reverse_proxy"}
                        else None
                    ),
                    request_id=request_id,
                )
            if selected_method == "POST" and path == "/api/v2/app-auth/register":
                return self._app_auth_register(
                    payload,
                    client_kind=client_kind,
                    request_id=request_id,
                )

            app_session = None
            is_m2m = path.startswith("/api/v2/m2m/")
            m2m_credential = None

            if is_m2m:
                if not authorization or not authorization.startswith("Bearer eb_svc_"):
                    raise CoordinatorAuthenticationError(
                        "M2M request missing valid service token.",
                        code="m2m_auth_missing",
                    )
                if not request_id:
                    raise CompositionValidationError("M2M requests require X-Request-Id.", code="m2m_request_id_missing")

                if body is not None and len(json.dumps(body, ensure_ascii=True)) > 65536:
                    raise CompositionValidationError("M2M request body exceeds 64KB.", code="m2m_request_too_large")

                from ..infrastructure.coordinator.service_credentials import ServiceCredentialService
                svc_service = ServiceCredentialService(self._coordinator)
                token_val = authorization[len("Bearer "):].strip()

                if not self._check_m2m_failed_verify_throttle():
                    raise CoordinatorAuthRateLimitError(
                        "M2M token verification temporarily throttled.",
                        code="m2m_auth_throttled",
                    )
                m2m_credential = svc_service.verify_token(token_val)
                if not m2m_credential:
                    self._record_m2m_failed_verify()
                    raise CoordinatorAuthenticationError(
                        "Invalid or revoked service token.",
                        code="m2m_auth_invalid",
                    )

                if not self._check_m2m_rate_limit(m2m_credential.id, max_requests=60, window_seconds=60.0):
                    raise CoordinatorAuthRateLimitError(
                        "M2M rate limit exceeded.",
                        code="m2m_rate_limit_exceeded",
                    )

                self._request_actor_app_user_id.set(m2m_credential.created_by_app_user_id)
                self._request_actor_global_role.set("service")
                self._request_service_auth_context.set(ServiceAuthContext(
                    service_id=m2m_credential.id,
                    service_name=m2m_credential.service_name,
                    allowed_providers=m2m_credential.allowed_providers,
                    allowed_messenger_account_ids=m2m_credential.allowed_messenger_account_ids,
                    scopes=m2m_credential.scopes,
                ))

                from .m2m_api import dispatch_m2m
                try:
                    m2m_response = asyncio.run(dispatch_m2m(
                        selected_method,
                        path,
                        body=payload,
                        service_auth_context=m2m_credential,
                        request_id=request_id,
                        orchestrator=self._provider_orchestrator,
                        coordinator=self._coordinator,
                        resolve_handler=self._m2m_resolve_recipients,
                    ))
                finally:
                    # Immediate cleanup, even on error: the service identity
                    # must not outlive its request on this execution context
                    # (F-085 gap #1).
                    self._request_actor_app_user_id.set(None)
                    self._request_actor_global_role.set(None)
                    self._request_service_auth_context.set(None)
                return m2m_response
            elif self.app_user_auth_enabled:
                app_auth = self._require_app_auth_service()
                app_session = app_auth.authorize(
                    app_session_token,
                    csrf_token=csrf_token,
                    require_csrf=selected_method not in {"GET", "HEAD", "OPTIONS"},
                    request_id=request_id,
                )
                self._request_actor_app_user_id.set(
                    app_session.principal.app_user_id
                )
                self._request_actor_global_role.set(
                    app_session.principal.global_role
                )

            if selected_method == "GET" and path == "/api/v2/app-auth/me":
                return self._app_auth_me(app_session)
            if selected_method == "GET" and path == "/api/v2/service-credentials":
                session = self._require_authorized_session(app_session)
                if session.principal.global_role != "admin":
                    raise CoordinatorAuthorizationError(
                        "فقط مدیر سامانه به این عملیات دسترسی دارد.",
                        code="app_auth_admin_required",
                    )
                svc = self._require_service_credential_service()
                creds = svc.list_credentials()
                return ApiResponse(200, {"ok": True, "credentials": [
                    {
                        "id": c.id,
                        "service_name": c.service_name,
                        "allowed_providers": c.allowed_providers,
                        "allowed_messenger_account_ids": c.allowed_messenger_account_ids,
                        "scopes": c.scopes,
                        "created_at": c.created_at,
                        "updated_at": c.updated_at,
                        "revoked_at": c.revoked_at,
                        "created_by_app_user_id": c.created_by_app_user_id,
                        "description": c.description
                    } for c in creds
                ]})
            if selected_method == "POST" and path == "/api/v2/service-credentials":
                session = self._require_authorized_session(app_session)
                if session.principal.global_role != "admin":
                    raise CoordinatorAuthorizationError(
                        "فقط مدیر سامانه به این عملیات دسترسی دارد.",
                        code="app_auth_admin_required",
                    )
                svc = self._require_service_credential_service()
                if not payload:
                    raise CompositionValidationError("Missing body")
                allowed_providers, allowed_accounts, scopes = self._validate_service_credential_fences(payload)
                cred, token = svc.create_credential(
                    service_name=payload["service_name"],
                    allowed_providers=allowed_providers,
                    allowed_messenger_account_ids=allowed_accounts,
                    scopes=scopes,
                    description=payload.get("description", ""),
                    created_by_app_user_id=session.principal.app_user_id,
                )
                if self._application_logger is not None:
                    self._application_logger.emit(
                        "service_credential_created",
                        correlation_id=request_id,
                        fields={"credential_id": cred.id, "service_name": cred.service_name},
                    )
                return ApiResponse(200, {"ok": True, "token": token, "credential": {
                    "id": cred.id,
                    "service_name": cred.service_name,
                    "allowed_providers": cred.allowed_providers,
                    "allowed_messenger_account_ids": cred.allowed_messenger_account_ids,
                    "scopes": cred.scopes,
                    "created_at": cred.created_at,
                    "updated_at": cred.updated_at,
                    "revoked_at": cred.revoked_at,
                    "created_by_app_user_id": cred.created_by_app_user_id,
                    "description": cred.description
                }})
            match = re.match(r"^/api/v2/service-credentials/([a-zA-Z0-9-]+)/(revoke|rotate)$", path)
            if selected_method == "POST" and match:
                session = self._require_authorized_session(app_session)
                if session.principal.global_role != "admin":
                    raise CoordinatorAuthorizationError(
                        "فقط مدیر سامانه به این عملیات دسترسی دارد.",
                        code="app_auth_admin_required",
                    )
                cred_id = match.group(1)
                action = match.group(2)
                svc = self._require_service_credential_service()
                if action == "revoke":
                    svc.revoke_credential(cred_id)
                    if self._application_logger is not None:
                        self._application_logger.emit(
                            "service_credential_revoked",
                            correlation_id=request_id,
                            fields={"credential_id": cred_id},
                        )
                    return ApiResponse(200, {"ok": True})
                elif action == "rotate":
                    try:
                        token = svc.rotate_credential(cred_id)
                    except LookupError:
                        raise CoordinatorAuthorizationError(
                            "Service credential not found or already revoked.",
                            code="service_credential_not_found",
                        )
                    if self._application_logger is not None:
                        self._application_logger.emit(
                            "service_credential_rotated",
                            correlation_id=request_id,
                            fields={"credential_id": cred_id},
                        )
                    return ApiResponse(200, {"ok": True, "token": token})

            if selected_method == "GET" and path == "/api/v2/observability/events":
                return ApiResponse(200, {"ok": True, "catalog": catalog_payload()})
            if selected_method == "GET" and path == "/api/v2/observability/health":
                return ApiResponse(200, self._observability_health())
            if selected_method == "POST" and path == "/api/v2/client-diagnostics":
                return self._client_diagnostics_report(
                    app_session,
                    payload,
                    client_kind=client_kind,
                    request_id=request_id,
                )
            if selected_method == "GET" and path == "/api/v2/audit":
                return self._audit_query(app_session, query)
            if selected_method == "POST" and path == "/api/v2/audit/export":
                return self._audit_export(app_session, payload)

            # Reporting management routes
            if selected_method == "GET" and path == "/api/v2/reporting/config":
                return self._reporting_get_config()
            if selected_method == "PUT" and path == "/api/v2/reporting/config":
                return self._reporting_set_config(payload)
            if selected_method == "POST" and path == "/api/v2/reporting/scan":
                return self._reporting_scan(payload)
            if selected_method == "GET" and path == "/api/v2/reporting/candidates":
                return self._reporting_list_candidates(query)
            cand_review_match = _REPORTING_CANDIDATE_REVIEW_ROUTE.fullmatch(path)
            if selected_method == "POST" and cand_review_match:
                return self._reporting_review_candidate(
                    cand_review_match.group("candidate_id"),
                    payload,
                    app_session=app_session,
                )
            cand_suggest_match = _REPORTING_CANDIDATE_SUGGEST_ROUTE.fullmatch(path)
            if selected_method in ("POST", "GET") and cand_suggest_match:
                return self._reporting_suggest_candidate(
                    cand_suggest_match.group("candidate_id"),
                    payload,
                )
            if selected_method == "GET" and path == "/api/v2/reporting/events":
                return self._reporting_list_events(query)
            if selected_method == "POST" and path == "/api/v2/reporting/events":
                return self._reporting_create_event(payload, app_session=app_session)
            if selected_method == "GET" and path == "/api/v2/reporting/forms":
                return self._reporting_list_forms(query)
            form_match = _REPORTING_FORM_ROUTE.fullmatch(path)
            if selected_method == "GET" and form_match:
                return self._reporting_get_form(form_match.group("program_id"))
            if selected_method == "PUT" and form_match:
                return self._reporting_save_form(
                    form_match.group("program_id"),
                    payload,
                    app_session=app_session,
                )
            if selected_method == "GET" and path == "/api/v2/reporting/mandates":
                return self._reporting_list_mandates(query)
            if selected_method == "POST" and path == "/api/v2/reporting/mandates":
                return self._reporting_create_mandate(payload)
            mandate_match = _REPORTING_MANDATE_ROUTE.fullmatch(path)
            if selected_method == "DELETE" and mandate_match:
                return self._reporting_delete_mandate(mandate_match.group("mandate_id"))
            if selected_method == "POST" and path == "/api/v2/reporting/export":
                return self._reporting_export(payload, app_session=app_session)
            if selected_method == "GET" and path == "/api/v2/reporting/exports":
                return self._reporting_list_exports(query)
            # Reporting transactional core (v3, phase 2 of the unified
            # reporting strategy): delegated dispatcher returns None for
            # unknown paths so the route chain continues.
            reporting_v3_response = self._reporting_v3_dispatch(
                selected_method, path, payload=payload, query=query,
                app_session=app_session,
            )
            if reporting_v3_response is not None:
                v3_status, v3_payload, v3_headers = reporting_v3_response
                return ApiResponse(v3_status, v3_payload, v3_headers)
            # Office product (v3): sections, registry, queues, dossier
            if selected_method == "GET" and path == "/api/v3/office/sections":
                return self._office_sections(query)
            if selected_method == "GET" and path == "/api/v3/office/registry":
                return self._office_registry(query)
            if selected_method == "GET" and path == "/api/v3/office/queue":
                return self._office_queue()
            office_review_match = _OFFICE_NORMALIZE_REVIEW_ROUTE.fullmatch(path)
            if selected_method == "POST" and office_review_match:
                return self._office_review_normalization(
                    office_review_match.group("candidate_id"), payload
                )
            office_wp_match = _OFFICE_WP_LINK_ACTION_ROUTE.fullmatch(path)
            if selected_method == "POST" and office_wp_match:
                return self._office_manage_wp_link(
                    office_wp_match.group("link_id"),
                    office_wp_match.group("action"),
                    payload,
                )
            if selected_method == "GET" and path == "/api/v3/office/dossier":
                return self._office_dossier(query)
            if selected_method == "GET" and path == "/api/v3/office/bimonthly":
                return self._office_bimonthly(query)
            if selected_method == "GET" and path == "/api/v3/office/wp-links":
                return self._office_wp_links(query)
            if selected_method == "POST" and path == "/api/v2/app-auth/logout":
                return self._app_auth_logout(app_session, request_id=request_id)
            if selected_method == "POST" and path == "/api/v2/app-auth/logout-all":
                return self._app_auth_logout_all(app_session, request_id=request_id)
            if selected_method == "GET" and path == "/api/v2/app-auth/sessions":
                return self._app_auth_sessions_list(app_session)
            session_revoke_match = _APP_SESSION_REVOKE_ROUTE.fullmatch(path)
            if selected_method == "POST" and session_revoke_match:
                return self._app_auth_session_revoke(
                    app_session,
                    session_revoke_match.group("session_id"),
                    request_id=request_id,
                )
            if selected_method == "POST" and path == "/api/v2/app-auth/change-password":
                return self._app_auth_change_password(
                    app_session,
                    payload,
                    request_id=request_id,
                )
            if selected_method == "GET" and path == "/api/v2/app-users":
                return self._app_users_list(app_session)
            if selected_method == "POST" and path == "/api/v2/app-users":
                return self._app_users_create(
                    app_session,
                    payload,
                    request_id=request_id,
                )
            user_update_match = _APP_USER_UPDATE_ROUTE.fullmatch(path)
            if selected_method == "POST" and user_update_match:
                return self._app_users_update(
                    app_session,
                    user_update_match.group("app_user_id"),
                    payload,
                    request_id=request_id,
                )
            user_revoke_match = _APP_USER_REVOKE_SESSIONS_ROUTE.fullmatch(path)
            if selected_method == "POST" and user_revoke_match:
                return self._app_users_revoke_sessions(
                    app_session,
                    user_revoke_match.group("app_user_id"),
                    request_id=request_id,
                )
            if selected_method == "GET" and path == "/api/v2/phone-accounts":
                return self._phone_accounts_list(app_session)
            membership_match = _PHONE_ACCOUNT_MEMBERSHIPS_ROUTE.fullmatch(path)
            if selected_method == "POST" and membership_match:
                return self._phone_account_membership_update(
                    app_session,
                    membership_match.group("phone_account_id"),
                    payload,
                    request_id=request_id,
                )
            if selected_method == "GET" and path == "/api/v2/app-integrations":
                return self._app_integrations_list(app_session)
            integration_match = _APP_INTEGRATION_UPDATE_ROUTE.fullmatch(path)
            if selected_method == "POST" and integration_match:
                return self._app_integration_update(
                    app_session,
                    integration_match.group("integration_id"),
                    payload,
                    request_id=request_id,
                )
            if selected_method == "GET" and path == "/api/v2/messenger-accounts":
                return self._messenger_accounts_list(app_session)
            if selected_method == "POST" and path == "/api/v2/messenger-accounts":
                return self._messenger_account_onboard(
                    app_session,
                    body or {},
                    request_id=request_id,
                )
            account_match = _MESSENGER_ACCOUNT_ROUTE.fullmatch(path)
            if selected_method == "GET" and account_match:
                return self._messenger_account_status(
                    app_session,
                    account_match.group("messenger_account_id"),
                )
            capabilities_match = _MESSENGER_ACCOUNT_CAPABILITIES_ROUTE.fullmatch(path)
            if selected_method == "GET" and capabilities_match:
                return self._messenger_account_capabilities(
                    app_session,
                    capabilities_match.group("messenger_account_id"),
                )
            worker_match = _MESSENGER_ACCOUNT_WORKER_ROUTE.fullmatch(path)
            if selected_method == "POST" and worker_match:
                return self._messenger_account_worker_action(
                    app_session,
                    worker_match.group("messenger_account_id"),
                    action=worker_match.group("action"),
                    request_id=request_id,
                )
            dialog_query_match = _MESSENGER_ACCOUNT_DIALOG_QUERY_ROUTE.fullmatch(path)
            if selected_method == "POST" and dialog_query_match:
                return self._provider_dialog_query(
                    app_session,
                    dialog_query_match.group("messenger_account_id"),
                    payload,
                    request_id=request_id,
                )
            history_query_match = _MESSENGER_ACCOUNT_HISTORY_QUERY_ROUTE.fullmatch(path)
            if selected_method == "POST" and history_query_match:
                return self._provider_history_query(
                    app_session,
                    history_query_match.group("messenger_account_id"),
                    payload,
                    request_id=request_id,
                )
            send_text_match = _MESSENGER_ACCOUNT_SEND_TEXT_ROUTE.fullmatch(path)
            if selected_method == "POST" and send_text_match:
                return self._provider_send_text(
                    app_session,
                    send_text_match.group("messenger_account_id"),
                    payload,
                    request_id=request_id,
                )
            media_read_match = _MESSENGER_ACCOUNT_MEDIA_READ_ROUTE.fullmatch(path)
            if selected_method == "POST" and media_read_match:
                return self._provider_media_read(
                    app_session,
                    media_read_match.group("messenger_account_id"),
                    payload,
                    request_id=request_id,
                )
            contact_query_match = _MESSENGER_ACCOUNT_CONTACT_QUERY_ROUTE.fullmatch(path)
            if selected_method == "POST" and contact_query_match:
                return self._provider_contact_query(
                    app_session,
                    contact_query_match.group("messenger_account_id"),
                    payload,
                    request_id=request_id,
                )
            contact_upsert_match = _MESSENGER_ACCOUNT_CONTACT_UPSERT_ROUTE.fullmatch(path)
            if selected_method == "POST" and contact_upsert_match:
                return self._provider_contact_upsert(
                    app_session,
                    contact_upsert_match.group("messenger_account_id"),
                    payload,
                    request_id=request_id,
                )

            if path.startswith("/api/v1/"):
                if self.config.features.multi_session.enabled:
                    selected_account_id = (
                        str(messenger_account_id or "").strip()
                        or self.config.features.multi_session.legacy_default_messenger_account_id
                    )
                    if not selected_account_id:
                        raise CoordinatorAuthorizationError(
                            "Select a messaging account before using the workspace.",
                            code="messenger_account_selection_required",
                        )
                    if app_session is not None:
                        self._require_app_auth_service().require_messenger_account_access(
                            app_session.principal,
                            selected_account_id,
                            operation="operate",
                        )
                    elif messenger_account_id:
                        raise CoordinatorAuthenticationError(
                            "AppUser authentication is required for account selection.",
                            code="app_auth_required",
                        )
                    required_capability = provider_capability_for_route(
                        selected_method, path
                    )
                    if required_capability is not None:
                        try:
                            self._require_provider_capability_service().require(
                                selected_account_id,
                                required_capability,
                            )
                        except BridgeError as exc:
                            self._application_logger.emit(
                                "provider_capability_check_rejected",
                                level="warning",
                                result="rejected",
                                reason_code=exc.code,
                                correlation_id=request_id,
                                fields={
                                    "messenger_account_id": selected_account_id,
                                    "capability": required_capability.value,
                                },
                            )
                            raise
                    selected_runtime = self._runtime_registry.runtime_for_account(
                        selected_account_id
                    )
                    self._request_runtime.set(selected_runtime)
                    if (
                        isinstance(selected_runtime, EitaaProcessRuntime)
                        and not (
                            selected_method == "GET"
                            and path == "/api/v1/scheduler/status"
                        )
                        and not _is_migrated_process_auth_route(selected_method, path)
                    ):
                        raise EitaaRuntimeError(
                            "This API route has not been migrated to a DTO-based Child RPC.",
                            code="eitaa_process_operation_ipc_required",
                        )
                else:
                    if messenger_account_id:
                        raise CoordinatorAuthorizationError(
                            "Account selection is not enabled.",
                            code="multi_session_account_selector_disabled",
                        )
                    if (
                        app_session is not None
                        and not self._require_app_auth_service().can_use_legacy_workspace(
                            app_session.principal
                        )
                    ):
                        raise CoordinatorAuthorizationError(
                            "This AppUser has no messaging account access.",
                            code="app_auth_legacy_workspace_forbidden",
                        )
            if selected_method == "GET" and path == "/api/v1/scheduler/status":
                return ApiResponse(200, {"ok": True, "scheduler": self._scheduler.snapshot()})
            if selected_method == "GET" and path == "/api/v1/auth/status":
                return ApiResponse(
                    200,
                    self._auth_status(app_session=app_session, request_id=request_id),
                )
            if selected_method == "POST" and path == "/api/v1/auth/request-code":
                return ApiResponse(
                    200,
                    self._auth_request_code(
                        payload,
                        app_session=app_session,
                        request_id=request_id,
                    ),
                )
            if selected_method == "POST" and path == "/api/v1/auth/submit-code":
                return ApiResponse(
                    200,
                    self._auth_submit_code(
                        payload,
                        app_session=app_session,
                        request_id=request_id,
                    ),
                )
            if selected_method == "POST" and path == "/api/v1/auth/submit-password":
                return ApiResponse(
                    200,
                    self._auth_submit_password(
                        payload,
                        app_session=app_session,
                        request_id=request_id,
                    ),
                )
            if selected_method == "POST" and path == "/api/v1/auth/logout":
                return ApiResponse(
                    200,
                    self._auth_logout(app_session=app_session, request_id=request_id),
                )
            if selected_method == "POST" and path == "/api/v1/auth/reset-local-session":
                return ApiResponse(
                    200,
                    self._auth_reset_local_session(
                        payload,
                        app_session=app_session,
                        request_id=request_id,
                    ),
                )
            if selected_method == "POST" and path == "/api/v1/auth/recover-phone-identity":
                return ApiResponse(
                    200,
                    self._auth_recover_phone_identity(
                        payload,
                        app_session=app_session,
                        request_id=request_id,
                    ),
                )
            if selected_method == "GET" and path == "/api/v1/sites":
                return ApiResponse(200, self._sites())
            if selected_method == "GET" and path == "/api/v1/settings/sites":
                return ApiResponse(200, self._settings_sites())
            if selected_method == "GET" and path == "/api/v2/settings/deployment":
                return ApiResponse(
                    200,
                    self._settings_deployment(app_session=app_session),
                )
            if selected_method == "POST" and path == "/api/v2/settings/deployment/port":
                return ApiResponse(
                    200,
                    self._settings_deployment_port_update(
                        payload,
                        app_session=app_session,
                        request_id=request_id,
                    ),
                )
            if selected_method == "POST" and path == "/api/v1/settings/sites/upsert":
                return ApiResponse(200, self._settings_site_upsert(payload))
            if selected_method == "POST" and path == "/api/v1/settings/sites/default":
                return ApiResponse(200, self._settings_site_default(payload))
            if selected_method == "POST" and path == "/api/v1/settings/sites/delete":
                return ApiResponse(200, self._settings_site_delete(payload))
            if selected_method == "POST" and path == "/api/v1/settings/sites/test":
                return ApiResponse(200, self._settings_site_test(payload))
            if selected_method == "GET" and path == "/api/v1/capabilities":
                return ApiResponse(200, self._capabilities(query))
            if selected_method == "GET" and path == "/api/v1/compositions":
                return ApiResponse(200, self._compositions(query))
            if selected_method == "GET" and path == "/api/v1/wordpress/categories":
                return ApiResponse(200, self._terms(query, taxonomy="category"))
            if selected_method == "GET" and path == "/api/v1/wordpress/tags":
                return ApiResponse(200, self._terms(query, taxonomy="post_tag"))
            if selected_method == "POST" and path == "/api/v1/wordpress/tags":
                return ApiResponse(201, self._create_tag(payload))
            if selected_method == "POST" and path == "/api/v1/wordpress/post":
                return ApiResponse(200, self._wordpress_post(payload))
            if selected_method == "POST" and path == "/api/v1/dialogs/list":
                return ApiResponse(200, self._dialogs_list(payload))
            if selected_method == "POST" and path == "/api/v1/dialogs/live-sync":
                return ApiResponse(200, self._dialogs_live_sync(payload))
            if selected_method == "POST" and path == "/api/v1/dialogs/sync":
                return ApiResponse(200, self._dialogs_sync(payload))
            if selected_method == "POST" and path == "/api/v1/dialogs/sync/start":
                return ApiResponse(202, self._dialogs_sync_start(payload))
            if selected_method == "GET" and path == "/api/v1/dialogs/sync/status":
                return ApiResponse(200, self._dialogs_sync_status(query))
            if selected_method == "POST" and path == "/api/v1/dialogs/avatar":
                return ApiResponse(200, self._dialogs_avatar(payload))
            if selected_method == "POST" and path == "/api/v1/dialogs/manual":
                return ApiResponse(201, self._dialogs_manual(payload))
            if selected_method == "POST" and path == "/api/v1/dialogs/favorite":
                return ApiResponse(200, self._dialogs_favorite(payload))
            if selected_method == "POST" and path == "/api/v1/dialogs/display-kind":
                return ApiResponse(200, self._dialogs_display_kind(payload))
            if selected_method == "POST" and path == "/api/v1/community/members/sync":
                return ApiResponse(200, self._community_members_sync(payload))
            if selected_method == "POST" and path == "/api/v1/community/members/list":
                return ApiResponse(200, self._community_members_list(payload))
            if selected_method == "POST" and path == "/api/v1/community/members/sync/start":
                return ApiResponse(202, self._community_members_sync_start(payload))
            if selected_method == "POST" and path == "/api/v1/community/members/remove/start":
                return ApiResponse(202, self._community_members_remove_start(payload))
            if selected_method == "POST" and path == "/api/v1/community/members/invite/start":
                return ApiResponse(202, self._community_members_invite_start(payload))
            if selected_method == "POST" and path == "/api/v1/community/bulk/preview":
                return ApiResponse(200, self._community_bulk_preview(payload))
            if selected_method == "POST" and path == "/api/v1/community/bulk/validate":
                return ApiResponse(200, self._community_bulk_validate(payload))
            if selected_method == "POST" and path == "/api/v1/community/bulk/create":
                return ApiResponse(201, self._community_bulk_create(payload))
            if selected_method == "POST" and path == "/api/v1/community/bulk/run":
                return ApiResponse(202, self._community_bulk_run(payload))
            if selected_method == "POST" and path == "/api/v1/community/bulk/jobs":
                return ApiResponse(200, self._community_bulk_jobs(payload))
            if selected_method == "POST" and path == "/api/v1/community/bulk/recipients":
                return ApiResponse(200, self._community_bulk_recipients(payload))
            if selected_method == "POST" and path == "/api/v1/community/bulk/action":
                return ApiResponse(200, self._community_bulk_action(payload))
            if selected_method == "POST" and path == "/api/v1/phone-lists/import":
                return ApiResponse(201, self._phone_list_import(payload))
            if selected_method == "GET" and path == "/api/v1/phone-lists":
                return ApiResponse(200, self._phone_lists(query))
            if selected_method == "POST" and path == "/api/v1/phone-lists/status":
                return ApiResponse(200, self._phone_list_status(payload))
            if selected_method == "POST" and path == "/api/v1/phone-lists/resolve":
                return ApiResponse(202, self._phone_list_resolve(payload))
            if selected_method == "POST" and path == "/api/v1/phone-lists/preview":
                return ApiResponse(200, self._phone_list_preview(payload))
            if selected_method == "POST" and path == "/api/v1/phone-lists/bulk/create":
                return ApiResponse(201, self._phone_list_bulk_create(payload))
            if selected_method == "POST" and path == "/api/v1/membership/preview":
                return ApiResponse(200, self._membership_preview(payload))
            if selected_method == "POST" and path == "/api/v1/membership/create":
                return ApiResponse(201, self._membership_create(payload))
            if selected_method == "POST" and path == "/api/v1/membership/run":
                return ApiResponse(202, self._membership_run(payload))
            if selected_method == "POST" and path == "/api/v1/membership/jobs":
                return ApiResponse(200, self._membership_jobs(payload))
            if selected_method == "POST" and path == "/api/v1/membership/action":
                return ApiResponse(200, self._membership_action(payload))
            if selected_method == "GET" and path == "/api/v1/background/status":
                return ApiResponse(200, self._background_status(query))
            if selected_method == "POST" and path == "/api/v1/messages/list":
                return ApiResponse(200, self._messages_list(payload))
            if selected_method == "POST" and path == "/api/v1/messages/media-preview":
                return ApiResponse(200, self._media_preview(payload))
            if selected_method == "POST" and path == "/api/v1/messages/send":
                return ApiResponse(201, self._message_send(payload))
            if selected_method == "POST" and path == "/api/v1/messages/read":
                return ApiResponse(200, self._messages_read(payload))
            if selected_method == "POST" and path == "/api/v1/messages/read/enqueue":
                return ApiResponse(202, self._messages_read_enqueue(payload))
            if selected_method == "POST" and path == "/api/v1/messages/sync":
                return ApiResponse(200, self._messages_sync(payload))
            if selected_method == "POST" and path == "/api/v1/messages/date-range/sync":
                return ApiResponse(200, self._messages_date_range_sync(payload))
            if selected_method == "POST" and path == "/api/v1/messages/usage":
                return ApiResponse(200, self._message_usage(payload))
            if selected_method == "POST" and path == "/api/v1/messages/index/start":
                return ApiResponse(202, self._content_index_start(payload))
            if selected_method == "GET" and path == "/api/v1/messages/index/status":
                return ApiResponse(200, self._content_index_status(query))
            if selected_method == "POST" and path == "/api/v1/messages/index/cancel":
                return ApiResponse(202, self._content_index_cancel(payload))
            if selected_method == "POST" and path == "/api/v1/messages/index/results":
                return ApiResponse(200, self._content_index_results(payload))
            if selected_method == "POST" and path == "/api/v1/messages/index/feedback":
                return ApiResponse(201, self._content_index_feedback(payload))
            if selected_method == "POST" and path == "/api/v1/eitaa-contacts/list":
                return ApiResponse(200, self._eitaa_contacts_list(payload))
            if selected_method == "POST" and path == "/api/v1/eitaa-contacts/add":
                return ApiResponse(201, self._eitaa_contacts_add(payload))
            if selected_method == "POST" and path == "/api/v1/eitaa-contacts/remove":
                return ApiResponse(200, self._eitaa_contacts_remove(payload))
            if selected_method == "POST" and path == "/api/v1/eitaa-contacts/categorize":
                return ApiResponse(200, self._eitaa_contacts_categorize(payload))
            if selected_method == "POST" and path == "/api/v1/eitaa-contacts/import-local/start":
                return ApiResponse(202, self._eitaa_contacts_import_local_start(payload))
            if selected_method == "POST" and path == "/api/v1/contacts/add-to-messenger/start":
                return ApiResponse(202, self._contacts_add_to_messenger_start(payload))
            if selected_method == "POST" and path == "/api/v1/contacts/list":
                return ApiResponse(200, self._contacts_list(payload))
            if selected_method == "POST" and path == "/api/v1/contacts/audit":
                return ApiResponse(200, self._contacts_audit(payload))
            if selected_method == "POST" and path == "/api/v1/contacts/upsert":
                return ApiResponse(200, self._contacts_upsert(payload))
            if selected_method == "POST" and path == "/api/v1/contacts/archive":
                return ApiResponse(200, self._contacts_archive(payload))
            if selected_method == "GET" and path == "/api/v1/contacts/categories":
                return ApiResponse(200, self._contact_categories())
            if selected_method == "POST" and path == "/api/v1/contacts/categories/save":
                return ApiResponse(200, self._contact_category_save(payload))
            if selected_method == "POST" and path == "/api/v1/contacts/categories/delete":
                return ApiResponse(200, self._contact_category_delete(payload))
            if selected_method == "POST" and path == "/api/v1/contacts/import/preview":
                return ApiResponse(200, self._contact_import_preview(payload))
            if selected_method == "POST" and path == "/api/v1/contacts/import/start":
                return ApiResponse(202, self._contact_import_start(payload))
            if selected_method == "POST" and path == "/api/v1/contacts/import/community/start":
                return ApiResponse(202, self._contact_community_import_start(payload))
            if selected_method == "POST" and path == "/api/v1/contacts/import/phone-list/start":
                return ApiResponse(202, self._contact_phone_list_import_start(payload))
            if selected_method == "GET" and path == "/api/v1/contacts/import/status":
                return ApiResponse(200, self._contact_import_status(query))
            if selected_method == "POST" and path == "/api/v1/contacts/import/cancel":
                return ApiResponse(202, self._contact_import_cancel(payload))
            if selected_method == "POST" and path == "/api/v1/contacts/targets/preview":
                return ApiResponse(200, self._contact_targets(payload))
            if selected_method == "POST" and path == "/api/v1/compositions/preview":
                return ApiResponse(200, self._composition_action(payload, action="preview"))
            if selected_method == "POST" and path == "/api/v1/compositions/status":
                return ApiResponse(200, self._composition_action(payload, action="status"))
            if selected_method == "POST" and path == "/api/v1/compositions/publish":
                result = self._composition_action(payload, action="publish")
                status = 201 if result.get("outcome") == "composition_created" else 200
                return ApiResponse(status, result)
            if selected_method == "POST" and path == "/api/v1/compositions/update":
                return ApiResponse(200, self._composition_action(payload, action="update"))
            return ApiResponse(
                404,
                {
                    "ok": False,
                    "error": {
                        "component": "api",
                        "error_code": "api_route_not_found",
                        "message": "API route was not found.",
                        "safe_context": {"method": selected_method, "path": path},
                    },
                },
            )
        except Exception as exc:  # centralized safe conversion for HTTP callers
            return self._error_response(exc)

    def authorize_local_resource(
        self,
        method: str,
        *,
        authorization: str | None = None,
        app_session_token: str | None = None,
        csrf_token: str | None = None,
        client_kind: str = "api",
        messenger_account_id: str | None = None,
    ) -> ApiResponse:
        """Authorize uploads and cached media served outside JSON routing."""
        try:
            if not self.app_user_auth_enabled:
                self._authorize(authorization)
                if messenger_account_id:
                    raise CoordinatorAuthorizationError(
                        "Account selection is not enabled.",
                        code="multi_session_account_selector_disabled",
                    )
                return ApiResponse(204, {"ok": True, "messenger_account_id": None})
            session = self._require_app_auth_service().authorize(
                app_session_token,
                csrf_token=csrf_token,
                require_csrf=method.upper().strip() not in {"GET", "HEAD", "OPTIONS"},
            )
            if self.config.features.multi_session.enabled:
                selected_id = (
                    str(messenger_account_id or "").strip()
                    or self.config.features.multi_session.legacy_default_messenger_account_id
                )
                if not selected_id:
                    raise CoordinatorAuthorizationError(
                        "Select a messaging account before accessing local files.",
                        code="messenger_account_selection_required",
                    )
                self._require_app_auth_service().require_messenger_account_access(
                    session.principal,
                    selected_id,
                    operation="operate",
                )
                self._runtime_registry.runtime_for_account(selected_id)
                return ApiResponse(
                    204,
                    {"ok": True, "messenger_account_id": selected_id},
                )
            if messenger_account_id:
                raise CoordinatorAuthorizationError(
                    "Account selection is not enabled.",
                    code="multi_session_account_selector_disabled",
                )
            if not self._require_app_auth_service().can_use_legacy_workspace(
                session.principal
            ):
                raise CoordinatorAuthorizationError(
                    "This AppUser has no messaging account access.",
                    code="app_auth_legacy_workspace_forbidden",
                )
            return ApiResponse(204, {"ok": True, "messenger_account_id": None})
        except Exception as exc:
            return self._error_response(exc)

    def authorize_media_cache_token(
        self,
        token: str,
        *,
        authorization: str | None = None,
        app_session_token: str | None = None,
        client_kind: str = "api",
    ) -> ApiResponse:
        """Resolve account context from an opaque token, never from URL input."""

        with self._media_token_scope_lock:
            known = token in self._media_token_accounts
            account_id = self._media_token_accounts.get(token)
        if not known:
            return ApiResponse(
                404,
                {
                    "ok": False,
                    "error": {
                        "component": "api",
                        "error_code": "api_media_cache_not_found",
                        "message": "The media cache item was not found.",
                        "safe_context": {},
                        "debug_file": None,
                    },
                },
            )
        return self.authorize_local_resource(
            "GET",
            authorization=authorization,
            app_session_token=app_session_token,
            client_kind=client_kind,
            messenger_account_id=account_id,
        )

    def _require_service_credential_service(self):
        from ..infrastructure.coordinator.service_credentials import ServiceCredentialService
        return ServiceCredentialService(self._coordinator)

    _M2M_CREDENTIAL_SCOPES = frozenset(
        {"messages.send", "messages.status", "contacts.resolve", "agent.chat"}
    )

    def _validate_service_credential_fences(
        self,
        payload: Mapping[str, Any],
    ) -> tuple[list[str], list[str], list[str]]:
        """An issued credential must carry explicit, valid fences.

        Missing, empty or unknown providers/accounts/scopes are rejected;
        a credential is never granted unlimited access by omission, and it
        can only reference accounts that already exist.
        """
        def _string_list(value: Any) -> list[str]:
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                return []
            return [item.strip() for item in value if item.strip()]

        providers = _string_list(payload.get("allowed_providers"))
        accounts = _string_list(payload.get("allowed_messenger_account_ids"))
        scopes = _string_list(payload.get("scopes"))

        if not providers:
            raise CompositionValidationError(
                "allowed_providers must be a non-empty list.",
                code="m2m_credential_providers_required",
            )
        from .provider_adapter import provider_adapter_catalog
        known_providers = set(provider_adapter_catalog().keys())
        unknown_providers = [item for item in providers if item not in known_providers]
        if unknown_providers:
            raise CompositionValidationError(
                "allowed_providers contains an unknown provider.",
                code="m2m_credential_provider_unknown",
            )
        if not accounts:
            raise CompositionValidationError(
                "allowed_messenger_account_ids must be a non-empty list.",
                code="m2m_credential_accounts_required",
            )
        coordinator = self._require_coordinator()
        for account_id in accounts:
            try:
                coordinator.messenger_account_runtime(account_id)
            except Exception as exc:
                raise CompositionValidationError(
                    "allowed_messenger_account_ids contains an unknown account.",
                    code="m2m_credential_account_unknown",
                ) from exc
        if not scopes:
            raise CompositionValidationError(
                "scopes must be a non-empty list.",
                code="m2m_credential_scopes_required",
            )
        unknown_scopes = [item for item in scopes if item not in self._M2M_CREDENTIAL_SCOPES]
        if unknown_scopes:
            raise CompositionValidationError(
                "scopes contains an unknown scope.",
                code="m2m_credential_scope_unknown",
            )
        return providers, accounts, scopes

    def _check_m2m_rate_limit(self, service_id: str, max_requests: int = 60, window_seconds: float = 60.0) -> bool:
        now = time.time()
        cutoff = now - window_seconds
        with self._m2m_rate_limit_lock:
            history = self._m2m_rate_limit_history.get(service_id, [])
            valid = [t for t in history if t > cutoff]
            if len(valid) >= max_requests:
                self._m2m_rate_limit_history[service_id] = valid
                return False
            valid.append(now)
            self._m2m_rate_limit_history[service_id] = valid
            return True

    def _check_m2m_failed_verify_throttle(self, max_failures: int = 30, window_seconds: float = 60.0) -> bool:
        """Bound pre-auth PBKDF2 work: refuse token verification while the
        recent failure rate stays above the threshold (DoS guard)."""
        now = time.time()
        cutoff = now - window_seconds
        with self._m2m_failed_verify_lock:
            self._m2m_failed_verify_history = [
                t for t in self._m2m_failed_verify_history if t > cutoff
            ]
            return len(self._m2m_failed_verify_history) < max_failures

    def _record_m2m_failed_verify(self, window_seconds: float = 60.0) -> None:
        now = time.time()
        cutoff = now - window_seconds
        with self._m2m_failed_verify_lock:
            self._m2m_failed_verify_history = [
                t for t in self._m2m_failed_verify_history if t > cutoff
            ]
            self._m2m_failed_verify_history.append(now)

    def _m2m_resolve_recipients(
        self,
        recipients: list[Mapping[str, Any]],
        messenger_account_id: str,
    ) -> list[dict[str, Any]]:
        """Read-only phone/dialog resolution for the M2M surface.

        Never writes data and never fabricates peer references: a recipient is
        `resolved` only when the shared contact directory maps it to an Eitaa
        identity AND the account's dialog catalog holds that dialog, so the
        returned reference is directly usable by the send path.
        """
        results: list[dict[str, Any]] = []
        # Read-only peek: resolve must never start a worker/runtime as a side
        # effect; an account without a live runtime resolves as unsupported.
        runtime = self._runtime_registry.peek_runtime_for_account(messenger_account_id)
        catalog = getattr(runtime, "dialog_catalog", None) if runtime is not None else None
        catalog_available = (
            runtime is not None
            and not isinstance(runtime, EitaaProcessRuntime)
            and catalog is not None
        )

        for recipient in recipients:
            kind = str(recipient.get("kind", ""))
            value = str(recipient.get("value", ""))
            if not catalog_available:
                results.append({
                    "status": "unsupported",
                    "peer_reference": None,
                    "reason": "resolve_unavailable_in_worker_mode",
                })
                continue
            if kind == "dialog":
                dialog = self._m2m_dialog_lookup(catalog, value)
                if dialog is not None:
                    results.append({"status": "resolved", "peer_reference": value, "reason": None})
                else:
                    results.append({"status": "unresolved", "peer_reference": None, "reason": "dialog_not_found"})
                continue
            if kind != "phone":
                results.append({"status": "unsupported", "peer_reference": None, "reason": "unsupported_kind"})
                continue
            try:
                normalized = normalize_phone(value)
            except ValueError:
                results.append({"status": "unsupported", "peer_reference": None, "reason": "invalid_phone"})
                continue
            matches = self._contact_store.find_contacts_by_eitaa_identity(
                phones=[normalized],
                messenger_account_id=messenger_account_id,
            )
            resolved_here = False
            for contact in matches:
                raw_user_id = contact.get("eitaa_user_id")
                if raw_user_id is None:
                    continue
                try:
                    user_id = int(raw_user_id)
                except (TypeError, ValueError):
                    continue
                if user_id <= 0:
                    continue
                dialog_key = f"user:{user_id}"
                if self._m2m_dialog_lookup(catalog, dialog_key) is not None:
                    results.append({"status": "resolved", "peer_reference": dialog_key, "reason": None})
                    resolved_here = True
                    break
            if not resolved_here:
                reason = "recipient_not_found"
                if matches:
                    reason = "contact_without_active_dialog"
                results.append({"status": "unresolved", "peer_reference": None, "reason": reason})
        return results

    @staticmethod
    def _m2m_dialog_lookup(catalog: Any, dialog_key: str) -> dict[str, Any] | None:
        try:
            dialog = catalog.get(str(dialog_key))
        except Exception:
            return None
        if isinstance(dialog, dict) and (dialog.get("active", True) or dialog.get("source") == "manual"):
            return dialog
        return None

    def _require_app_auth_service(self) -> CoordinatorAppAuth:
        if not self.app_user_auth_enabled or self._app_auth is None:
            raise CoordinatorAuthenticationError(
                "ورود کاربران نرم‌افزار فعال نیست.",
                code="app_auth_disabled",
            )
        return self._app_auth

    def _require_coordinator_audit(self) -> SafeCoordinatorAuditService:
        if self._coordinator_audit is None:
            raise CoordinatorAuthorizationError(
                "Coordinator audit is unavailable.", code="coordinator_audit_unavailable"
            )
        return self._coordinator_audit

    def _require_coordinator(self) -> CoordinatorDatabase:
        if self._coordinator is None:
            raise CoordinatorAuthorizationError(
                "Coordinator is unavailable.", code="coordinator_unavailable"
            )
        return self._coordinator

    def _require_provider_capability_service(self) -> ProviderCapabilityService:
        if self._provider_capability_service is None:
            raise CoordinatorAuthorizationError(
                "Provider capability service is unavailable.",
                code="provider_capability_service_unavailable",
            )
        return self._provider_capability_service

    def _authorize_provider_operation_account(
        self,
        actor: ProviderOperationActor,
        messenger_account_id: str,
        operation: str,
    ) -> None:
        service_ctx = self._request_service_auth_context.get()
        if service_ctx is not None:
            # Service fence: explicit account list first…
            if not service_ctx.allowed_messenger_account_ids or (
                messenger_account_id not in service_ctx.allowed_messenger_account_ids
            ):
                raise CoordinatorAuthorizationError(
                    "Service credential is not authorized for this messenger account.",
                    safe_context={"messenger_account_id": str(messenger_account_id)},
                    code="messenger_account_access_denied",
                )
            coordinator = self._require_coordinator()
            runtime = coordinator.messenger_account_runtime(messenger_account_id)
            # …then the provider allowlist, so a credential limited to one
            # provider can never drive an account of another provider.
            account_provider = str(getattr(runtime, "provider", ""))
            if not service_ctx.allowed_providers or (
                account_provider not in service_ctx.allowed_providers
            ):
                raise CoordinatorAuthorizationError(
                    "Service credential is not authorized for this provider.",
                    safe_context={"messenger_account_id": str(messenger_account_id)},
                    code="m2m_provider_not_allowed",
                )
            return

        coordinator = self._require_coordinator()
        try:
            coordinator.require_messenger_account_access(
                messenger_account_id,
                app_user_id=actor.app_user_id,
                global_role=actor.global_role,
                operation=operation,
            )
        except CoordinatorSchemaError as exc:
            if exc.code in {
                "messenger_account_access_denied",
                "messenger_account_actor_inactive",
            }:
                raise CoordinatorAuthorizationError(
                    "You cannot operate the selected messaging account.",
                    safe_context={"messenger_account_id": str(messenger_account_id)},
                    code="messenger_account_access_denied",
                ) from exc
            raise

    def _provider_operation_account_context(
        self,
        messenger_account_id: str,
    ) -> ProviderAccountContext:
        record = self._require_coordinator().messenger_account_runtime(
            messenger_account_id
        )
        return ProviderAccountContext(
            messenger_account_id=record.messenger_account_id,
            phone_account_id=record.phone_account_id,
            provider=record.provider,
            storage_revision=record.storage_revision,
            session_generation=record.session_generation,
        )

    def _resolve_provider_application_adapter(
        self,
        account: ProviderAccountContext,
    ) -> Any:
        factory = self._provider_application_adapter_factories.get(account.provider)
        if factory is None:
            raise BridgeConfigurationError(
                "The provider application adapter is not configured.",
                safe_context={"provider": account.provider},
                code="provider_application_adapter_not_configured",
            )
        return factory(account)

    def _create_eitaa_application_adapter(
        self,
        account: ProviderAccountContext,
    ) -> EitaaProviderApplicationAdapter:
        return EitaaProviderApplicationAdapter(
            account,
            self._provider_registry.registration(account.provider).manifest,
            EitaaCompatibilityOperations(
                list_dialogs=self._eitaa_provider_dialogs,
                load_history=self._eitaa_provider_history,
                send_text=self._eitaa_provider_send_text,
                read_media=self._eitaa_provider_media,
                list_contacts=self._eitaa_provider_contacts,
                upsert_contact=self._eitaa_provider_contact_upsert,
            ),
        )

    @contextmanager
    def _eitaa_provider_runtime_scope(
        self,
        account: ProviderAccountContext,
    ) -> Iterator[None]:
        runtime = self._eitaa_provider_runtime(account)
        if isinstance(runtime, EitaaProcessRuntime):
            raise EitaaRuntimeError(
                "This provider operation requires a bounded Child RPC.",
                code="eitaa_process_operation_ipc_required",
            )
        token = self._request_runtime.set(runtime)
        try:
            yield
        finally:
            self._request_runtime.reset(token)

    def _eitaa_provider_runtime(
        self,
        account: ProviderAccountContext,
    ) -> EitaaAccountRuntime | EitaaProcessRuntime:
        runtime = self._runtime_registry.runtime_for_account(
            account.messenger_account_id
        )
        if runtime.runtime_record is None or (
            runtime.runtime_record.messenger_account_id
            != account.messenger_account_id
        ):
            raise EitaaRuntimeError(
                "The Eitaa provider runtime account scope is invalid.",
                code="eitaa_provider_runtime_scope_invalid",
            )
        return runtime

    def _eitaa_process_provider_request(
        self,
        account: ProviderAccountContext,
        method: str,
        payload: Mapping[str, object],
        *,
        timeout_seconds: float,
    ) -> dict[str, object] | None:
        runtime = self._eitaa_provider_runtime(account)
        if not isinstance(runtime, EitaaProcessRuntime):
            return None
        return runtime.provider_operation_request(
            method,
            payload,
            timeout_seconds=timeout_seconds,
        )

    @staticmethod
    def _eitaa_process_items(
        payload: Mapping[str, object],
        field: str,
        *,
        maximum: int,
    ) -> list[Mapping[str, object]]:
        value = payload.get(field)
        if not isinstance(value, list) or len(value) > maximum:
            raise CompositionValidationError(
                "The Eitaa Child provider result is invalid.",
                safe_context={"field": field},
                code="eitaa_process_provider_result_invalid",
            )
        if any(not isinstance(item, Mapping) for item in value):
            raise CompositionValidationError(
                "The Eitaa Child provider result is invalid.",
                safe_context={"field": field},
                code="eitaa_process_provider_result_invalid",
            )
        return list(value)

    @staticmethod
    def _eitaa_process_cursor(payload: Mapping[str, object]) -> str | None:
        value = payload.get("next_cursor")
        if value is None:
            return None
        if not isinstance(value, str):
            raise CompositionValidationError(
                "The Eitaa Child provider cursor is invalid.",
                code="eitaa_process_provider_result_invalid",
            )
        return value

    def _bind_process_media_reference(
        self,
        account: ProviderAccountContext,
        content_reference: str,
    ) -> None:
        marker = "cache:"
        cache_reference = (
            content_reference[len(marker) :]
            if content_reference.startswith(marker)
            else ""
        )
        if not re.fullmatch(r"[0-9a-f]{32}", cache_reference):
            raise CompositionValidationError(
                "The Eitaa Child media reference is invalid.",
                code="provider_media_receipt_invalid",
            )
        with self._media_token_scope_lock:
            self._media_token_accounts[cache_reference] = (
                account.messenger_account_id
            )
            if len(self._media_token_accounts) > 1024:
                for stale in tuple(self._media_token_accounts)[:256]:
                    self._media_token_accounts.pop(stale, None)

    def _provider_operation_site(self) -> str:
        return self._site_key(
            {"site_key": self._provider_operation_site_key.get()}
        )

    @staticmethod
    def _provider_peer_kind(dialog: Mapping[str, Any]) -> str:
        selected = str(dialog.get("display_kind") or "").strip().lower()
        return {
            "personal": "private",
            "group": "group",
            "channel": "channel",
        }.get(selected, "unknown")

    @staticmethod
    def _provider_offset_cursor(value: str | None) -> int:
        if value is None:
            return 0
        selected = str(value)
        if not selected.startswith("offset:") or not selected[7:].isdigit():
            raise CompositionValidationError(
                "The provider page cursor is invalid.",
                code="provider_cursor_invalid",
            )
        return int(selected[7:])

    @staticmethod
    def _provider_history_cursor(value: str | None) -> int | None:
        if value is None:
            return None
        selected = str(value)
        if not selected.startswith("before:") or not selected[7:].isdigit():
            raise CompositionValidationError(
                "The provider history cursor is invalid.",
                code="provider_cursor_invalid",
            )
        return int(selected[7:])

    @staticmethod
    def _provider_message_timestamp(value: object) -> int:
        if isinstance(value, int) and not isinstance(value, bool):
            return max(0, value * 1000 if value < 10_000_000_000 else value)
        selected = str(value or "").strip()
        if not selected:
            return 0
        try:
            parsed = datetime.fromisoformat(selected.replace("Z", "+00:00"))
        except ValueError:
            return 0
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0, int(parsed.timestamp() * 1000))

    async def _eitaa_provider_dialogs(
        self,
        context: Any,
        cursor: str | None,
        limit: int,
    ) -> ProviderDialogPage:
        offset = self._provider_offset_cursor(cursor)
        process_payload = self._eitaa_process_provider_request(
            context.account,
            "eitaa.provider.dialogs.query",
            {
                "site_key": self._provider_operation_site(),
                "cursor": cursor,
                "limit": limit,
            },
            timeout_seconds=90.0,
        )
        if process_payload is not None:
            dialogs: list[ProviderDialogSummary] = []
            for item in self._eitaa_process_items(
                process_payload,
                "dialogs",
                maximum=200,
            ):
                dialogs.append(
                    ProviderDialogSummary(
                        peer=ProviderPeerReference(
                            str(item.get("peer_reference") or ""),
                            str(item.get("peer_kind") or "unknown"),
                        ),
                        title=str(item.get("title") or ""),
                        unread_count=int(item.get("unread_count") or 0),
                    )
                )
            return ProviderDialogPage(
                tuple(dialogs),
                next_cursor=self._eitaa_process_cursor(process_payload),
            )
        with self._eitaa_provider_runtime_scope(context.account):
            payload = self._dialogs_list(
                {
                    "site_key": self._provider_operation_site(),
                    "refresh_if_empty": True,
                }
            )
        dialogs = list(payload.get("dialogs") or [])
        selected = dialogs[offset : offset + limit]
        summaries: list[ProviderDialogSummary] = []
        for item in selected:
            if not isinstance(item, Mapping):
                continue
            peer_key = str(item.get("peer_key") or "").strip()
            peer_payload = (
                item.get("peer") if isinstance(item.get("peer"), Mapping) else {}
            )
            summaries.append(
                ProviderDialogSummary(
                    peer=ProviderPeerReference(
                        peer_key,
                        self._provider_peer_kind(item),
                    ),
                    title=str(peer_payload.get("title") or "")[:512],
                    unread_count=max(0, int(item.get("unread_count") or 0)),
                )
            )
        next_offset = offset + len(selected)
        return ProviderDialogPage(
            tuple(summaries),
            next_cursor=(
                f"offset:{next_offset}" if next_offset < len(dialogs) else None
            ),
        )

    async def _eitaa_provider_history(
        self,
        context: Any,
        peer: ProviderPeerReference,
        cursor: str | None,
        limit: int,
    ) -> ProviderMessagePage:
        process_payload = self._eitaa_process_provider_request(
            context.account,
            "eitaa.provider.history.query",
            {
                "site_key": self._provider_operation_site(),
                "peer_reference": peer.opaque_reference,
                "peer_kind": peer.kind,
                "cursor": cursor,
                "limit": limit,
            },
            timeout_seconds=90.0,
        )
        if process_payload is not None:
            messages: list[ProviderMessageSummary] = []
            for item in self._eitaa_process_items(
                process_payload,
                "messages",
                maximum=500,
            ):
                text = item.get("text")
                result_peer = ProviderPeerReference(
                    str(item.get("peer_reference") or ""),
                    str(item.get("peer_kind") or "unknown"),
                )
                if result_peer != peer:
                    raise CompositionValidationError(
                        "The Eitaa Child history scope is invalid.",
                        code="eitaa_process_provider_result_invalid",
                    )
                messages.append(
                    ProviderMessageSummary(
                        message_reference=str(
                            item.get("message_reference") or ""
                        ),
                        peer=result_peer,
                        sender_reference=(
                            str(item.get("sender_reference"))
                            if item.get("sender_reference") is not None
                            else None
                        ),
                        sent_at_unix_ms=int(
                            item.get("sent_at_unix_ms") or 0
                        ),
                        text=str(text) if text is not None else None,
                    )
                )
            return ProviderMessagePage(
                tuple(messages),
                next_cursor=self._eitaa_process_cursor(process_payload),
            )
        with self._eitaa_provider_runtime_scope(context.account):
            dialog = self.dialog_catalog.get(peer.opaque_reference)
            if dialog is None:
                raise CompositionValidationError(
                    "The selected dialog was not found.",
                    code="api_dialog_not_found",
                )
            payload = self._messages_list(
                {
                    "site_key": self._provider_operation_site(),
                    "peer_file": dialog.get("peer_file"),
                    "limit": limit,
                    "before_id": self._provider_history_cursor(cursor),
                }
            )
        messages: list[ProviderMessageSummary] = []
        for item in payload.get("messages") or []:
            if not isinstance(item, Mapping):
                continue
            message_id = int(item.get("id") or 0)
            if message_id <= 0:
                continue
            sender_raw = str(item.get("sender_key") or "").strip() or None
            if sender_raw is not None and not re.fullmatch(
                r"[A-Za-z0-9._:-]{1,256}", sender_raw
            ):
                sender_raw = None
            text = item.get("text")
            messages.append(
                ProviderMessageSummary(
                    message_reference=f"message:{message_id}",
                    peer=peer,
                    sender_reference=sender_raw,
                    sent_at_unix_ms=self._provider_message_timestamp(
                        item.get("date") or item.get("sent_at")
                    ),
                    text=(str(text)[:100_000] if text is not None else None),
                )
            )
        next_before = payload.get("next_before_id")
        return ProviderMessagePage(
            tuple(messages),
            next_cursor=(
                f"before:{int(next_before)}"
                if next_before not in {None, ""} and int(next_before) > 0
                else None
            ),
        )

    async def _eitaa_provider_send_text(
        self,
        context: Any,
        request: ProviderSendTextRequest,
    ) -> ProviderSendReceipt:
        process_payload = self._eitaa_process_provider_request(
            context.account,
            "eitaa.provider.messages.send_text",
            {
                "site_key": self._provider_operation_site(),
                "peer_reference": request.peer.opaque_reference,
                "peer_kind": request.peer.kind,
                "text": request.text,
                "idempotency_key": request.idempotency_key,
            },
            timeout_seconds=90.0,
        )
        if process_payload is not None:
            try:
                status = ProviderSendStatus(str(process_payload.get("status") or ""))
            except ValueError as exc:
                raise CompositionValidationError(
                    "The Eitaa Child send result is invalid.",
                    code="eitaa_process_provider_result_invalid",
                ) from exc
            reference = process_payload.get("message_reference")
            reason = process_payload.get("safe_reason_code")
            return ProviderSendReceipt(
                status,
                message_reference=(str(reference) if reference is not None else None),
                safe_reason_code=(str(reason) if reason is not None else None),
            )
        with self._eitaa_provider_runtime_scope(context.account):
            dialog = self.dialog_catalog.get(request.peer.opaque_reference)
            if dialog is None:
                raise CompositionValidationError(
                    "The selected dialog was not found.",
                    code="api_dialog_not_found",
                )
            payload = self._message_send(
                {
                    "site_key": self._provider_operation_site(),
                    "peer_file": dialog.get("peer_file"),
                    "text": request.text,
                    "send_as": "auto",
                }
            )
        result = payload.get("result") if isinstance(payload, Mapping) else None
        result_mapping = result if isinstance(result, Mapping) else {}
        remote_id = result_mapping.get("message_id") or result_mapping.get("id")
        reference = (
            f"message:{int(remote_id)}"
            if remote_id not in {None, ""} and str(remote_id).isdigit()
            else f"send:{request.idempotency_key[:64]}"
        )
        return ProviderSendReceipt(
            ProviderSendStatus.SUCCEEDED,
            message_reference=reference,
        )

    @staticmethod
    def _provider_reference_integer(value: str, *, prefix: str) -> int:
        selected = str(value or "")
        marker = f"{prefix}:"
        suffix = selected[len(marker) :] if selected.startswith(marker) else ""
        if not suffix.isdigit() or int(suffix) <= 0:
            raise CompositionValidationError(
                "The provider numeric reference is invalid.",
                code="provider_reference_invalid",
            )
        return int(suffix)

    async def _eitaa_provider_media(
        self,
        context: Any,
        request: ProviderMediaReadRequest,
    ) -> ProviderMediaReadReceipt:
        message_id = self._provider_reference_integer(
            request.message_reference, prefix="message"
        )
        process_payload = self._eitaa_process_provider_request(
            context.account,
            "eitaa.provider.media.read",
            {
                "site_key": self._provider_operation_site(),
                "peer_reference": request.peer.opaque_reference,
                "message_reference": request.message_reference,
                "media_reference": request.media_reference,
                "variant": request.variant,
                "max_bytes": request.max_bytes,
            },
            timeout_seconds=180.0,
        )
        if process_payload is not None:
            receipt = ProviderMediaReadReceipt(
                media_reference=str(
                    process_payload.get("media_reference") or ""
                ),
                content_reference=str(
                    process_payload.get("content_reference") or ""
                ),
                mime_type=str(
                    process_payload.get("mime_type")
                    or "application/octet-stream"
                ),
                byte_count=int(process_payload.get("byte_count") or 0),
            )
            if receipt.media_reference != request.media_reference:
                raise CompositionValidationError(
                    "The Eitaa Child media scope is invalid.",
                    code="eitaa_process_provider_result_invalid",
                )
            self._bind_process_media_reference(
                context.account,
                receipt.content_reference,
            )
            return receipt
        with self._eitaa_provider_runtime_scope(context.account):
            dialog = self.dialog_catalog.get(request.peer.opaque_reference)
            if dialog is None:
                raise CompositionValidationError(
                    "The selected dialog was not found.",
                    code="api_dialog_not_found",
                )
            payload = self._media_preview(
                {
                    "site_key": self._provider_operation_site(),
                    "peer_file": dialog.get("peer_file"),
                    "message_id": message_id,
                    "quality": request.variant,
                    "max_bytes": request.max_bytes,
                }
            )
        if not payload.get("media_present") or not payload.get("preview_available"):
            raise CompositionValidationError(
                "The selected provider media is unavailable.",
                code="provider_media_not_found",
            )
        media_url = str(payload.get("media_url") or "")
        marker = "/api/v1/media-cache/"
        cache_token = media_url[len(marker) :] if media_url.startswith(marker) else ""
        if not re.fullmatch(r"[A-Za-z0-9._:-]{1,256}", cache_token):
            raise CompositionValidationError(
                "The provider media content reference is invalid.",
                code="provider_media_receipt_invalid",
            )
        return ProviderMediaReadReceipt(
            media_reference=request.media_reference,
            content_reference=f"cache:{cache_token}",
            mime_type=str(payload.get("mime_type") or "application/octet-stream"),
            byte_count=int(payload.get("bytes") or 0),
        )

    async def _eitaa_provider_contacts(
        self,
        context: Any,
        cursor: str | None,
        limit: int,
    ) -> ProviderContactPage:
        offset = self._provider_offset_cursor(cursor)
        process_payload = self._eitaa_process_provider_request(
            context.account,
            "eitaa.provider.contacts.query",
            {
                "site_key": self._provider_operation_site(),
                "cursor": cursor,
                "limit": limit,
            },
            timeout_seconds=120.0,
        )
        if process_payload is not None:
            contacts: list[ProviderContactSummary] = []
            for item in self._eitaa_process_items(
                process_payload,
                "contacts",
                maximum=500,
            ):
                hint = item.get("identity_hint")
                contacts.append(
                    ProviderContactSummary(
                        contact_reference=str(
                            item.get("contact_reference") or ""
                        ),
                        display_name=str(item.get("display_name") or ""),
                        identity_hint=(str(hint) if hint is not None else None),
                    )
                )
            return ProviderContactPage(
                tuple(contacts),
                next_cursor=self._eitaa_process_cursor(process_payload),
            )
        with self._eitaa_provider_runtime_scope(context.account):
            payload = self._eitaa_contacts_list(
                {
                    "site_key": self._provider_operation_site(),
                    "refresh": False,
                    "sync_local": False,
                    "offset": offset,
                    "limit": limit,
                }
            )
        contacts: list[ProviderContactSummary] = []
        for item in payload.get("contacts") or []:
            if not isinstance(item, Mapping):
                continue
            user_id = item.get("user_id")
            if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
                continue
            phone = str(item.get("phone") or "").strip()
            display_name = str(item.get("display_name") or "")[:512]
            if phone and display_name.strip() == phone:
                display_name = f"کاربر {user_id}"
            try:
                identity_hint = masked_phone(phone) if phone else None
            except BridgeError:
                identity_hint = None
            contacts.append(
                ProviderContactSummary(
                    contact_reference=f"contact:{user_id}",
                    display_name=display_name,
                    identity_hint=identity_hint,
                )
            )
        next_offset = offset + len(contacts)
        return ProviderContactPage(
            tuple(contacts),
            next_cursor=(f"offset:{next_offset}" if payload.get("has_more") else None),
        )

    async def _eitaa_provider_contact_upsert(
        self,
        context: Any,
        request: ProviderContactUpsertRequest,
    ) -> ProviderContactMutationReceipt:
        try:
            identity = request.identity.reveal_bytes().decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise CompositionValidationError(
                "The provider contact identity is invalid.",
                code="provider_contact_identity_invalid",
            ) from exc
        phone = validate_canonical_e164(identity)
        process_payload = self._eitaa_process_provider_request(
            context.account,
            "eitaa.provider.contacts.upsert",
            {
                "site_key": self._provider_operation_site(),
                "identity": phone,
                "display_name": request.display_name,
                "idempotency_key": request.idempotency_key,
            },
            timeout_seconds=120.0,
        )
        if process_payload is not None:
            created = process_payload.get("created")
            if not isinstance(created, bool):
                raise CompositionValidationError(
                    "The Eitaa Child contact result is invalid.",
                    code="eitaa_process_provider_result_invalid",
                )
            return ProviderContactMutationReceipt(
                contact_reference=str(
                    process_payload.get("contact_reference") or ""
                ),
                created=created,
            )
        with self._eitaa_provider_runtime_scope(context.account):
            payload = self._eitaa_contacts_add(
                {
                    "site_key": self._provider_operation_site(),
                    "phone": phone,
                    "first_name": request.display_name,
                    "last_name": "",
                    "save_local": False,
                }
            )
        contact = payload.get("contact")
        selected = contact if isinstance(contact, Mapping) else {}
        user_id = selected.get("user_id")
        if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
            raise CompositionValidationError(
                "The provider contact receipt is invalid.",
                code="provider_contact_receipt_invalid",
            )
        return ProviderContactMutationReceipt(
            contact_reference=f"contact:{user_id}",
            created=bool(payload.get("contact_added")),
        )

    @staticmethod
    def _provider_operation_actor(
        app_session: AuthorizedAppSession | None,
    ) -> ProviderOperationActor:
        if app_session is None:
            raise CoordinatorAuthenticationError(
                "AppUser authentication is required.",
                code="app_auth_required",
            )
        return ProviderOperationActor(
            app_user_id=app_session.principal.app_user_id,
            global_role=app_session.principal.global_role,
        )

    @staticmethod
    def _require_provider_operation_fields(
        payload: Mapping[str, Any],
        allowed: set[str],
    ) -> None:
        rejected = sorted(str(key) for key in payload if key not in allowed)
        if rejected:
            raise CompositionValidationError(
                "The provider operation contains unsupported fields.",
                safe_context={"rejected_fields": rejected},
                code="provider_operation_fields_rejected",
            )

    def _provider_dialog_query(
        self,
        app_session: AuthorizedAppSession | None,
        messenger_account_id: str,
        payload: Mapping[str, Any],
        *,
        request_id: str | None,
    ) -> ApiResponse:
        self._require_provider_operation_fields(
            payload, {"site_key", "cursor", "limit"}
        )
        site_key = self._site_key(payload)
        cursor = str(payload.get("cursor") or "").strip() or None
        limit = self._integer(
            payload.get("limit", 100), "limit", minimum=1, maximum=200
        )
        token = self._provider_operation_site_key.set(site_key)
        try:
            page = asyncio.run(
                self._provider_orchestrator.list_dialogs(
                    actor=self._provider_operation_actor(app_session),
                    messenger_account_id=messenger_account_id,
                    correlation_id=self._application_logger.correlation_id(request_id),
                    deadline_unix_ms=int(time.time() * 1000) + 90_000,
                    cursor=cursor,
                    limit=limit,
                )
            )
        finally:
            self._provider_operation_site_key.reset(token)
        account = self._provider_operation_account_context(messenger_account_id)
        return ApiResponse(
            200,
            {
                "ok": True,
                "messenger_account_id": account.messenger_account_id,
                "provider": account.provider,
                "dialogs": [
                    {
                        "peer_reference": item.peer.opaque_reference,
                        "peer_kind": item.peer.kind,
                        "title": item.title,
                        "unread_count": item.unread_count,
                    }
                    for item in page.dialogs
                ],
                "next_cursor": page.next_cursor,
            },
        )

    def _provider_history_query(
        self,
        app_session: AuthorizedAppSession | None,
        messenger_account_id: str,
        payload: Mapping[str, Any],
        *,
        request_id: str | None,
    ) -> ApiResponse:
        self._require_provider_operation_fields(
            payload,
            {"site_key", "peer_reference", "peer_kind", "cursor", "limit"},
        )
        site_key = self._site_key(payload)
        peer = ProviderPeerReference(
            str(payload.get("peer_reference") or "").strip(),
            str(payload.get("peer_kind") or "unknown").strip().lower(),
        )
        cursor = str(payload.get("cursor") or "").strip() or None
        limit = self._integer(
            payload.get("limit", 100), "limit", minimum=1, maximum=500
        )
        token = self._provider_operation_site_key.set(site_key)
        try:
            page = asyncio.run(
                self._provider_orchestrator.load_history(
                    actor=self._provider_operation_actor(app_session),
                    messenger_account_id=messenger_account_id,
                    correlation_id=self._application_logger.correlation_id(request_id),
                    deadline_unix_ms=int(time.time() * 1000) + 90_000,
                    peer=peer,
                    cursor=cursor,
                    limit=limit,
                )
            )
        finally:
            self._provider_operation_site_key.reset(token)
        account = self._provider_operation_account_context(messenger_account_id)
        return ApiResponse(
            200,
            {
                "ok": True,
                "messenger_account_id": account.messenger_account_id,
                "provider": account.provider,
                "messages": [
                    {
                        "message_reference": item.message_reference,
                        "peer_reference": item.peer.opaque_reference,
                        "peer_kind": item.peer.kind,
                        "sender_reference": item.sender_reference,
                        "sent_at_unix_ms": item.sent_at_unix_ms,
                        "text": item.text,
                    }
                    for item in page.messages
                ],
                "next_cursor": page.next_cursor,
            },
        )

    def _provider_send_text(
        self,
        app_session: AuthorizedAppSession | None,
        messenger_account_id: str,
        payload: Mapping[str, Any],
        *,
        request_id: str | None,
    ) -> ApiResponse:
        self._require_provider_operation_fields(
            payload,
            {
                "site_key",
                "peer_reference",
                "peer_kind",
                "text",
                "idempotency_key",
                "confirm",
            },
        )
        site_key = self._site_key(payload)
        peer = ProviderPeerReference(
            str(payload.get("peer_reference") or "").strip(),
            str(payload.get("peer_kind") or "unknown").strip().lower(),
        )
        correlation = self._application_logger.correlation_id(request_id)
        selected_key = str(payload.get("idempotency_key") or "").strip()
        if not selected_key:
            raise CompositionValidationError(
                "An idempotency key is required for provider send.",
                code="provider_idempotency_key_required",
            )
        if payload.get("confirm") is not True:
            raise CompositionValidationError(
                "Provider message send requires explicit confirmation.",
                code="provider_message_send_confirmation_required",
            )
        request = ProviderSendTextRequest(
            peer=peer,
            text=str(payload.get("text") or ""),
            idempotency_key=selected_key,
        )
        token = self._provider_operation_site_key.set(site_key)
        try:
            receipt = asyncio.run(
                self._provider_orchestrator.send_text(
                    actor=self._provider_operation_actor(app_session),
                    messenger_account_id=messenger_account_id,
                    correlation_id=correlation,
                    deadline_unix_ms=int(time.time() * 1000) + 90_000,
                    request=request,
                )
            )
        finally:
            self._provider_operation_site_key.reset(token)
        account = self._provider_operation_account_context(messenger_account_id)
        return ApiResponse(
            201,
            {
                "ok": True,
                "messenger_account_id": account.messenger_account_id,
                "provider": account.provider,
                "status": receipt.status.value,
                "message_reference": receipt.message_reference,
                "safe_reason_code": receipt.safe_reason_code,
            },
        )

    def _provider_media_read(
        self,
        app_session: AuthorizedAppSession | None,
        messenger_account_id: str,
        payload: Mapping[str, Any],
        *,
        request_id: str | None,
    ) -> ApiResponse:
        self._require_provider_operation_fields(
            payload,
            {
                "site_key",
                "peer_reference",
                "peer_kind",
                "message_reference",
                "media_reference",
                "variant",
                "max_bytes",
            },
        )
        site_key = self._site_key(payload)
        request = ProviderMediaReadRequest(
            peer=ProviderPeerReference(
                str(payload.get("peer_reference") or "").strip(),
                str(payload.get("peer_kind") or "unknown").strip().lower(),
            ),
            message_reference=str(payload.get("message_reference") or "").strip(),
            media_reference=str(payload.get("media_reference") or "").strip(),
            variant=str(payload.get("variant") or "thumbnail").strip().lower(),
            max_bytes=self._integer(
                payload.get("max_bytes", 16 * 1024 * 1024),
                "max_bytes",
                minimum=32 * 1024,
                maximum=512 * 1024 * 1024,
            ),
        )
        token = self._provider_operation_site_key.set(site_key)
        try:
            receipt = asyncio.run(
                self._provider_orchestrator.read_media(
                    actor=self._provider_operation_actor(app_session),
                    messenger_account_id=messenger_account_id,
                    correlation_id=self._application_logger.correlation_id(request_id),
                    deadline_unix_ms=int(time.time() * 1000) + 180_000,
                    request=request,
                )
            )
        finally:
            self._provider_operation_site_key.reset(token)
        account = self._provider_operation_account_context(messenger_account_id)
        return ApiResponse(
            200,
            {
                "ok": True,
                "messenger_account_id": account.messenger_account_id,
                "provider": account.provider,
                "media_reference": receipt.media_reference,
                "content_reference": receipt.content_reference,
                "mime_type": receipt.mime_type,
                "byte_count": receipt.byte_count,
            },
        )

    def _provider_contact_query(
        self,
        app_session: AuthorizedAppSession | None,
        messenger_account_id: str,
        payload: Mapping[str, Any],
        *,
        request_id: str | None,
    ) -> ApiResponse:
        self._require_provider_operation_fields(
            payload, {"site_key", "cursor", "limit"}
        )
        site_key = self._site_key(payload)
        cursor = str(payload.get("cursor") or "").strip() or None
        limit = self._integer(
            payload.get("limit", 100), "limit", minimum=1, maximum=500
        )
        token = self._provider_operation_site_key.set(site_key)
        try:
            page = asyncio.run(
                self._provider_orchestrator.list_contacts(
                    actor=self._provider_operation_actor(app_session),
                    messenger_account_id=messenger_account_id,
                    correlation_id=self._application_logger.correlation_id(request_id),
                    deadline_unix_ms=int(time.time() * 1000) + 120_000,
                    cursor=cursor,
                    limit=limit,
                )
            )
        finally:
            self._provider_operation_site_key.reset(token)
        account = self._provider_operation_account_context(messenger_account_id)
        return ApiResponse(
            200,
            {
                "ok": True,
                "messenger_account_id": account.messenger_account_id,
                "provider": account.provider,
                "contacts": [
                    {
                        "contact_reference": item.contact_reference,
                        "display_name": item.display_name,
                        "identity_hint": item.identity_hint,
                    }
                    for item in page.contacts
                ],
                "next_cursor": page.next_cursor,
            },
        )

    def _provider_contact_upsert(
        self,
        app_session: AuthorizedAppSession | None,
        messenger_account_id: str,
        payload: Mapping[str, Any],
        *,
        request_id: str | None,
    ) -> ApiResponse:
        self._require_provider_operation_fields(
            payload,
            {"site_key", "identity", "display_name", "idempotency_key", "confirm"},
        )
        site_key = self._site_key(payload)
        if payload.get("confirm") is not True:
            raise CompositionValidationError(
                "Provider contact mutation requires explicit confirmation.",
                code="provider_contact_mutation_confirmation_required",
            )
        identity = str(payload.get("identity") or "")
        display_name = str(payload.get("display_name") or "").strip()
        idempotency_key = str(payload.get("idempotency_key") or "").strip()
        if not identity:
            raise CompositionValidationError(
                "A provider contact identity is required.",
                code="provider_contact_identity_required",
            )
        if not idempotency_key:
            raise CompositionValidationError(
                "An idempotency key is required for provider contact mutation.",
                code="provider_idempotency_key_required",
            )
        request = ProviderContactUpsertRequest(
            identity=SensitiveProviderValue.from_text(identity),
            display_name=display_name,
            idempotency_key=idempotency_key,
        )
        token = self._provider_operation_site_key.set(site_key)
        try:
            receipt = asyncio.run(
                self._provider_orchestrator.upsert_contact(
                    actor=self._provider_operation_actor(app_session),
                    messenger_account_id=messenger_account_id,
                    correlation_id=self._application_logger.correlation_id(request_id),
                    deadline_unix_ms=int(time.time() * 1000) + 120_000,
                    request=request,
                )
            )
        finally:
            self._provider_operation_site_key.reset(token)
        account = self._provider_operation_account_context(messenger_account_id)
        return ApiResponse(
            201 if receipt.created else 200,
            {
                "ok": True,
                "messenger_account_id": account.messenger_account_id,
                "provider": account.provider,
                "contact_reference": receipt.contact_reference,
                "created": receipt.created,
            },
        )

    def _audit_query(
        self,
        session: AuthorizedAppSession | None,
        query: Mapping[str, str],
    ) -> ApiResponse:
        if session is None:
            raise CoordinatorAuthenticationError(
                "An AppUser session is required.", code="app_auth_session_required"
            )
        page = self._require_coordinator_audit().query(
            app_user_id=session.principal.app_user_id,
            global_role=session.principal.global_role,
            messenger_account_id=str(query.get("messenger_account_id") or "").strip() or None,
            provider=str(query.get("provider") or "").strip() or None,
            action_prefix=str(query.get("action_prefix") or "").strip() or None,
            result=str(query.get("result") or "").strip() or None,
            correlation_id=str(query.get("correlation_id") or "").strip() or None,
            from_at=str(query.get("from_at") or "").strip() or None,
            to_at=str(query.get("to_at") or "").strip() or None,
            cursor=str(query.get("cursor") or "").strip() or None,
            limit=self._integer(query.get("limit", 200), "limit", minimum=1, maximum=1000),
        )
        return ApiResponse(200, {"ok": True, **page.safe_summary()})

    def _audit_export(
        self,
        session: AuthorizedAppSession | None,
        payload: Mapping[str, Any],
    ) -> ApiResponse:
        if session is None:
            raise CoordinatorAuthenticationError(
                "An AppUser session is required.", code="app_auth_session_required"
            )
        result = self._require_coordinator_audit().export_jsonl(
            app_user_id=session.principal.app_user_id,
            global_role=session.principal.global_role,
            output_directory=self.base_directory / "runtime" / "exports" / "audit",
            messenger_account_id=self._payload_text(payload, "messenger_account_id").strip() or None,
            action_prefix=self._payload_text(payload, "action_prefix").strip() or None,
            max_events=self._integer(
                payload.get("max_events", 10_000),
                "max_events",
                minimum=1,
                maximum=100_000,
            ),
        )
        return ApiResponse(200, {"ok": True, "export": result.safe_summary()})

    # ----------------------------------------------------------------------
    # Office Product Handlers (v3) — sections/registry/queue/dossier
    # ----------------------------------------------------------------------
    def _office_sections(self, query: Mapping[str, str]) -> ApiResponse:
        period = (query.get("period") or "1405").strip()
        sections = self._reporting_store.list_sections()
        events = self._reporting_store.list_events(limit=1000)
        payload = []
        for section in sections:
            section_id = section["section_id"]
            facts = self._reporting_store.list_entity_facts(
                entity_type="section", entity_id=f"section:{section_id}", period=period
            )
            plans = self._reporting_store.list_plan_items(period=period, section=section_id)
            if not plans and period == "1405":
                from ..reporting.plans import ALL_PLANS_1405
                plans = [p for p in ALL_PLANS_1405 if p.section == section_id and p.period == period]
            section_events = [
                e for e in events
                if any(k.value in section.get("kinds", []) for k in e.program_kinds)
            ]
            realization = realization_report(plans, section_events, scope="provincial_hq") if plans else []
            gaps = [item for item in realization if item.get("gap")]
            payload.append({
                **section,
                "events_count": len(section_events),
                "facts_count": len(facts),
                "realization": realization,
                "open_gaps": len(gaps),
            })
        return ApiResponse(200, {"ok": True, "period": period, "sections": payload})

    def _office_registry(self, query: Mapping[str, str]) -> ApiResponse:
        kind = (query.get("kind") or "units").strip()
        if kind == "units":
            items = [
                {"unit_id": u.unit_id, "name": u.name, "kind": u.kind, "notes": u.notes}
                for u in self._reporting_store.list_units()
            ]
        elif kind == "imams":
            items = [
                {"imam_id": i.imam_id, "unit_id": i.unit_id, "full_name": i.full_name,
                 "position": i.position, "source_kind": i.source_kind, "status": i.status,
                 "version": i.version}
                for i in self._reporting_store.list_imams()
            ]
        elif kind == "venues":
            items = [
                {"venue_id": v.venue_id, "unit_id": v.unit_id, "name": v.name,
                 "notes": v.notes}
                for v in self._reporting_store.list_venues()
            ]
        elif kind == "nomokalaf":
            items = [
                {"nom_id": n.nom_id, "unit_id": n.unit_id, "year": n.year,
                 "grain": n.grain, "person_count": n.person_count,
                 "full_name": n.full_name}
                for n in self._reporting_store.list_nomokalaf()
            ]
        elif kind == "persons":
            person_kind = (query.get("person_kind") or "").strip() or None
            items = [
                {"person_id": pr.person_id, "kind": pr.kind, "full_name": pr.full_name,
                 "personnel_no": pr.personnel_no, "phone": pr.phone,
                 "relation": pr.relation, "related_personnel_no": pr.related_personnel_no,
                 "notes": pr.notes}
                for pr in self._reporting_store.list_persons(kind=person_kind)
            ]
        else:
            return ApiResponse(400, {"ok": False, "error": f"unknown registry kind: {kind}"})
        return ApiResponse(200, {"ok": True, "kind": kind, "items": items})

    def _office_queue(self) -> ApiResponse:
        candidates = self._reporting_store.list_normalization_candidates(status="pending")
        wp_pending = [
            link for link in self._reporting_store.list_wp_links(limit=1000)
            if link["match_status"] in {"candidate", "unmatched"}
        ]
        return ApiResponse(200, {
            "ok": True,
            "normalization": candidates,
            "wp_links": wp_pending,
        })

    def _office_review_normalization(self, candidate_id: str, payload: Mapping[str, Any]) -> ApiResponse:
        action = (payload.get("action") or "").strip()
        reviewed_by = (payload.get("reviewed_by") or "office-operator").strip()
        if action == "approve":
            coded = str(payload.get("coded_value") or "").strip()
            if not coded:
                return ApiResponse(400, {"ok": False, "error": "coded_value required"})
            fact = self._reporting_store.approve_normalization_candidate(
                candidate_id, coded_value=coded, reviewed_by=reviewed_by,
            )
            full_name = str(payload.get("full_name") or "").strip()
            position = str(payload.get("position") or "").strip()
            source_kind = str(payload.get("source_kind") or "").strip()
            if (full_name or position or source_kind) and fact.entity_type == "unit":
                imams = self._reporting_store.list_imams(unit_id=fact.entity_id)
                if imams:
                    imam = imams[0]
                    if full_name: imam.full_name = full_name
                    if position: imam.position = position
                    if source_kind in {"none", "staff_cleric", "invited_external"}:
                        imam.source_kind = source_kind
                    self._reporting_store.save_imam(imam)
            return ApiResponse(200, {"ok": True, "fact_id": fact.fact_id})
        if action == "reject":
            self._reporting_store.reject_normalization_candidate(
                candidate_id, reviewed_by=reviewed_by,
                reason=str(payload.get("reason") or ""),
            )
            return ApiResponse(200, {"ok": True})
        return ApiResponse(400, {"ok": False, "error": "action must be approve|reject"})

    def _office_dossier(self, query: Mapping[str, str]) -> ApiResponse:
        period = (query.get("period") or "1405").strip()
        dossier = build_prayer_dossier(
            events=self._reporting_store.list_events(limit=1000),
            units=self._reporting_store.list_units(),
            facts=self._reporting_store.list_entity_facts(period=period),
            imams=self._reporting_store.list_imams(),
            period=period,
        )
        return ApiResponse(200, {"ok": True, "dossier": dossier})

    def _office_bimonthly(self, query: Mapping[str, str]) -> ApiResponse:
        period = (query.get("period") or "1405-P1").strip()
        facts = self._reporting_store.list_entity_facts(
            entity_type="section", period=period
        )
        grouped: dict[str, list[dict[str, Any]]] = {}
        for fact in facts:
            grouped.setdefault(fact.entity_id, []).append({
                "metric": fact.metric,
                "value": fact.value,
                "text_value": fact.text_value,
                "unit": fact.unit_of_measure,
                "note": fact.note,
            })
        return ApiResponse(200, {"ok": True, "period": period, "sections": grouped})

    def _office_wp_links(self, query: Mapping[str, str]) -> ApiResponse:
        status = (query.get("status") or "").strip() or None
        section = (query.get("section") or "").strip() or None
        links = self._reporting_store.list_wp_links(status=status, section=section, limit=1000)
        return ApiResponse(200, {"ok": True, "links": links})

    # ----------------------------------------------------------------------
    # Reporting Endpoints Handlers
    # ----------------------------------------------------------------------

    def _office_manage_wp_link(
        self, link_id: str, action: str, payload: Mapping[str, Any]
    ) -> ApiResponse:
        if action == "unlink":
            with self._reporting_store._connect() as conn:
                conn.execute(
                    "UPDATE wp_post_links SET event_id = '', match_status = 'unmatched' WHERE link_id = ?",
                    (link_id,),
                )
            return ApiResponse(200, {"ok": True, "link_id": link_id, "action": "unlink"})
        if action == "link":
            event_id = str(payload.get("event_id") or "").strip()
            section = str(payload.get("section") or "").strip()
            with self._reporting_store._connect() as conn:
                if section:
                    conn.execute(
                        "UPDATE wp_post_links SET section = ? WHERE link_id = ?",
                        (section, link_id),
                    )
            if event_id:
                self._reporting_store.link_wp_post_to_event(
                    link_id, event_id, match_status="confirmed"
                )
            elif section:
                link_row = None
                with self._reporting_store._connect() as conn:
                    row = conn.execute("SELECT * FROM wp_post_links WHERE link_id = ?", (link_id,)).fetchone()
                    if row:
                        link_row = dict(row)
                if link_row:
                    from ..reporting.office_import import _KIND_BY_SECTION
                    from ..reporting.model import ReportedEvent, UnitScope
                    from datetime import date
                    import uuid as _uuid
                    kinds = _KIND_BY_SECTION.get(section, ())
                    pub_str = link_row.get("published_on") or ""
                    try:
                        occurred = date.fromisoformat(pub_str) if pub_str else date.today()
                    except ValueError:
                        occurred = date.today()
                    ev_id = f"wp-manual-{_uuid.uuid4().hex[:8]}"
                    ev = ReportedEvent(
                        event_id=ev_id,
                        program_kinds=kinds,
                        occurred_on=occurred,
                        unit=UnitScope.PROVINCIAL_HQ,
                        notes=link_row.get("title") or "تأیید دستی بخش",
                        created_by="manual-linking",
                    )
                    self._reporting_store.save_event(ev)
                    self._reporting_store.link_wp_post_to_event(link_id, ev_id, match_status="confirmed")
            return ApiResponse(200, {"ok": True, "link_id": link_id, "action": "link"})
        return ApiResponse(400, {"ok": False, "error": f"unknown action: {action}"})

    def _reporting_get_config(self) -> ApiResponse:
        config = self._reporting_store.get_config()
        targets = [
            {
                "label": t.label,
                "match_keywords": list(t.match_keywords),
                "enabled": t.enabled,
            }
            for t in self._reporting_store.list_targets()
        ]
        return ApiResponse(200, {"ok": True, "config": config, "targets": targets})

    def _reporting_set_config(self, payload: Mapping[str, Any]) -> ApiResponse:
        settings = payload.get("config") or {}
        if isinstance(settings, dict) and settings:
            self._reporting_store.set_config(settings)
        targets = payload.get("targets")
        if isinstance(targets, list):
            for t in targets:
                if isinstance(t, dict) and "label" in t:
                    cfg = DialogWatchConfig(
                        label=str(t["label"]),
                        match_keywords=tuple(str(k) for k in t.get("match_keywords", ())),
                        enabled=bool(t.get("enabled", True)),
                    )
                    self._reporting_store.save_target(cfg)
        return self._reporting_get_config()

    def _reporting_scan(self, payload: Mapping[str, Any]) -> ApiResponse:
        messages = payload.get("messages")
        if isinstance(messages, list) and messages:
            tuples: list[tuple[str, str, str]] = []
            for item in messages:
                if isinstance(item, (list, tuple)) and len(item) == 3:
                    tuples.append((str(item[0]), str(item[1]), str(item[2])))
            result = self._reporting_service.scan_and_record_texts(tuples)
            return ApiResponse(200, {"ok": True, "result": result.summary()})

        limit = int(payload.get("limit_per_dialog", 50))
        runtime = self._request_runtime.get() or self._v1_runtime
        if runtime is not None and hasattr(runtime, "core") and runtime.core is not None:
            result = self._reporting_service.scan_and_record_provider(runtime.core, limit_per_dialog=limit)
            return ApiResponse(200, {"ok": True, "result": result.summary()})

        return ApiResponse(
            200,
            {
                "ok": True,
                "result": {
                    "scanned": 0,
                    "event_reports": 0,
                    "informational": 0,
                    "promotional": 0,
                    "candidates": [],
                },
                "note": "runtime_not_available",
            },
        )

    def _reporting_list_candidates(self, query: Mapping[str, str]) -> ApiResponse:
        status = query.get("status", "pending")
        limit = int(query.get("limit", 100))
        candidates = self._reporting_service.list_review_candidates(
            status=status if status != "all" else None, limit=limit
        )
        return ApiResponse(200, {"ok": True, "candidates": candidates})

    def _reporting_review_candidate(
        self,
        candidate_id: str,
        payload: Mapping[str, Any],
        *,
        app_session: Any = None,
    ) -> ApiResponse:
        action = str(payload.get("action", "")).strip().lower()
        operator = (
            app_session.principal.display_name
            if app_session and hasattr(app_session, "principal")
            else "central_staff"
        )
        if action == "approve":
            event_id = str(payload.get("event_id") or f"evt-{uuid.uuid4().hex[:10]}")
            raw_date = payload.get("occurred_on")
            if raw_date:
                try:
                    occurred = date.fromisoformat(str(raw_date))
                except ValueError:
                    occurred = date.today()
            else:
                occurred = date.today()
            unit_str = str(payload.get("unit", "provincial_hq"))
            unit = (
                UnitScope(unit_str)
                if unit_str in {u.value for u in UnitScope}
                else UnitScope.PROVINCIAL_HQ
            )
            unit_name = str(payload.get("unit_name", ""))
            official_present = payload.get("official_present")
            if official_present is not None:
                official_present = bool(official_present)

            program_id = payload.get("program_id") or payload.get("program_kind")
            program_kinds = None
            if program_id:
                try:
                    program_kinds = (ProgramKind(str(program_id)),)
                except ValueError:
                    pass

            attendee_count = payload.get("attendee_count")
            if attendee_count is not None and str(attendee_count).strip():
                try:
                    attendee_count = float(attendee_count)
                except (ValueError, TypeError):
                    attendee_count = None
            else:
                attendee_count = None

            is_ashura_pilgrimage = payload.get("is_ashura_pilgrimage")
            if is_ashura_pilgrimage is not None:
                is_ashura_pilgrimage = bool(is_ashura_pilgrimage)

            is_standalone_titled = bool(payload.get("is_standalone_titled", True))
            occasion_class = payload.get("occasion_class")
            notes = str(payload.get("notes", ""))
            dimension_facts = payload.get("dimension_facts")
            if not isinstance(dimension_facts, Mapping):
                dimension_facts = None

            event = self._reporting_service.approve_candidate_to_event(
                candidate_id,
                event_id=event_id,
                occurred_on=occurred,
                unit=unit,
                unit_name=unit_name,
                official_present=official_present,
                staff_member=operator,
                program_kinds=program_kinds,
                attendee_count=attendee_count,
                is_ashura_pilgrimage=is_ashura_pilgrimage,
                is_standalone_titled=is_standalone_titled,
                occasion_class=occasion_class,
                dimension_facts=dimension_facts,
                notes=notes,
            )
            if event is None:
                return ApiResponse(
                    404, {"ok": False, "error": {"message": "Candidate not found."}}
                )
            return ApiResponse(
                200, {"ok": True, "status": "approved", "event_id": event.event_id}
            )

        elif action == "reject":
            reason = str(payload.get("reason", ""))
            ok = self._reporting_service.reject_candidate(
                candidate_id, staff_member=operator, reason=reason
            )
            if not ok:
                return ApiResponse(
                    404, {"ok": False, "error": {"message": "Candidate not found."}}
                )
            return ApiResponse(200, {"ok": True, "status": "rejected"})

        return ApiResponse(
            400,
            {
                "ok": False,
                "error": {"message": "Invalid action; must be 'approve' or 'reject'."},
            },
        )

    def _reporting_suggest_candidate(
        self,
        candidate_id: str,
        payload: Mapping[str, Any] | None,
    ) -> ApiResponse:
        body = payload or {}
        text = str(body.get("text", ""))
        label = str(body.get("dialog_label", ""))
        suggestion = self._reporting_service.suggest_candidate_review(
            candidate_id=candidate_id,
            text=text,
            dialog_label=label,
        )
        if suggestion is None:
            return ApiResponse(
                404, {"ok": False, "error": {"message": "Candidate not found."}}
            )
        return ApiResponse(200, {"ok": True, "suggestion": suggestion.to_dict()})


    def _reporting_v3_dispatch(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, Any] | None = None,
        query: Mapping[str, Any] | None = None,
        app_session: Any = None,
    ):
        """Delegate /api/v3/reporting/* to the phase-2 transactional core.

        Actor and roles derive from the app session when present; the
        unauthenticated desktop-loopback fallback keeps the historical
        central_staff operator, which bootstraps its own roles through the
        audited empty-table path.
        """
        principal = getattr(app_session, "principal", None) if app_session else None
        if principal is not None and getattr(principal, "app_user_id", None):
            actor = str(principal.app_user_id)
        elif principal is not None and getattr(principal, "display_name", None):
            actor = str(principal.display_name)
        else:
            actor = "central_staff"
        if principal is not None and getattr(principal, "global_role", None) == "admin":
            roles = ["editor", "approver", "admin"]
        else:
            roles = self._reporting_store.get_user_roles(actor)
        return _reporting_v3_route_dispatch(
            self._reporting_store, actor, roles, method, path,
            payload=payload, query=query,
        )

    def _reporting_create_event(
        self,
        payload: Mapping[str, Any],
        *,
        app_session: Any = None,
    ) -> ApiResponse:
        operator = (
            app_session.principal.display_name
            if app_session and hasattr(app_session, "principal")
            else "central_staff"
        )
        event_id = str(payload.get("event_id") or f"evt-{uuid.uuid4().hex[:10]}")
        raw_date = payload.get("occurred_on")
        if raw_date:
            try:
                occurred = date.fromisoformat(str(raw_date))
            except ValueError:
                occurred = date.today()
        else:
            occurred = date.today()

        program_id = payload.get("program_id") or payload.get("program_kind") or "ceremony"
        try:
            program_kinds = (ProgramKind(str(program_id)),)
        except ValueError:
            program_kinds = (ProgramKind.CEREMONY,)

        unit_str = str(payload.get("unit", "provincial_hq"))
        unit = (
            UnitScope(unit_str)
            if unit_str in {u.value for u in UnitScope}
            else UnitScope.PROVINCIAL_HQ
        )
        unit_name = str(payload.get("unit_name", ""))
        official_present = payload.get("official_present")
        if official_present is not None:
            official_present = bool(official_present)

        attendee_count = payload.get("attendee_count")
        if attendee_count is not None and str(attendee_count).strip():
            try:
                attendee_count = float(attendee_count)
            except (ValueError, TypeError):
                attendee_count = None
        else:
            attendee_count = None

        is_ashura_pilgrimage = bool(payload.get("is_ashura_pilgrimage", False))
        is_standalone_titled = bool(payload.get("is_standalone_titled", True))
        occasion_class = payload.get("occasion_class")
        notes = str(payload.get("notes", ""))
        dimension_facts = payload.get("dimension_facts")
        if not isinstance(dimension_facts, Mapping):
            dimension_facts = None

        event = self._reporting_service.create_manual_event(
            event_id=event_id,
            program_kinds=program_kinds,
            occurred_on=occurred,
            unit=unit,
            unit_name=unit_name,
            official_present=official_present,
            attendee_count=attendee_count,
            is_ashura_pilgrimage=is_ashura_pilgrimage,
            is_standalone_titled=is_standalone_titled,
            occasion_class=occasion_class,
            dimension_facts=dimension_facts,
            notes=notes,
            staff_member=operator,
        )

        return ApiResponse(
            201,
            {
                "ok": True,
                "event_id": event.event_id,
                "event": {
                    "event_id": event.event_id,
                    "program_kinds": [k.value for k in event.program_kinds],
                    "occurred_on": event.occurred_on.isoformat(),
                    "unit": event.unit.value,
                    "unit_name": event.unit_name,
                    "facts_count": len(event.facts),
                },
            },
        )

    def _reporting_list_events(self, query: Mapping[str, str]) -> ApiResponse:
        limit = int(query.get("limit", 100))
        events = self._reporting_service.get_stored_events(limit=limit)
        serialized = []
        for ev in events:
            serialized.append(
                {
                    "event_id": ev.event_id,
                    "program_kinds": [k.value for k in ev.program_kinds],
                    "occurred_on": ev.occurred_on.isoformat(),
                    "unit": ev.unit.value,
                    "unit_name": ev.unit_name,
                    "occasion": ev.occasion,
                    "occasion_class": ev.occasion_class.value if ev.occasion_class else None,
                    "official_present": ev.official_present,
                    "is_ashura_pilgrimage": ev.is_ashura_pilgrimage,
                    "created_by": ev.created_by,
                    "facts": [
                        {
                            "metric": f.metric,
                            "value": f.value,
                            "value_kind": f.value_kind.value,
                            "source": f.source.value,
                            "created_by": f.created_by,
                        }
                        for f in ev.facts
                    ],
                }
            )
        return ApiResponse(200, {"ok": True, "events": serialized})

    def _reporting_list_forms(self, query: Mapping[str, Any] | None = None) -> ApiResponse:
        include_all = False
        if query:
            raw_all = query.get("all")
            raw_narrative = query.get("include_narrative")
            val_all = raw_all[0] if isinstance(raw_all, (list, tuple)) else str(raw_all or "")
            val_narrative = raw_narrative[0] if isinstance(raw_narrative, (list, tuple)) else str(raw_narrative or "")
            include_all = val_all in ("true", "1") or val_narrative in ("true", "1")
        definitions = self._reporting_service.definitions(include_narrative=include_all)
        saved = self._reporting_service.load_filled_forms()
        forms_list = []
        for defn in definitions:
            prog_id = "narrative" if defn.program_code == "80000" else defn.program_id.value
            f = saved.get(prog_id)
            questions_data = [
                {
                    "key": q.key,
                    "label": q.label,
                    "qtype": q.qtype,
                    "star": q.star,
                    "human_gate": q.human_gate,
                    "choices": list(q.choices),
                    "auto_from": q.auto_from,
                    "current_value": (
                        f.answers[q.key].value if f and q.key in f.answers else None
                    ),
                }
                for q in defn.questions
            ]
            forms_list.append(
                {
                    "program_id": prog_id,
                    "program_code": defn.program_code,
                    "title": defn.title,
                    "operational_description": defn.operational_description,
                    "monitoring_criteria": list(defn.monitoring_criteria),
                    "policy_framework": defn.policy_framework,
                    "questions": questions_data,
                    "unresolved_star": (
                        list(f.unresolved_star_keys(defn)) if f else list(defn.star_keys())
                    ),
                    "unresolved_human_gate": (
                        list(f.unresolved_human_gates(defn))
                        if f
                        else list(defn.human_gate_keys())
                    ),
                }
            )
        return ApiResponse(200, {"ok": True, "forms": forms_list})

    def _reporting_get_form(self, program_id: str) -> ApiResponse:
        from ..reporting.forms import EXTENDED_FORMS_BY_PROGRAM
        if program_id not in EXTENDED_FORMS_BY_PROGRAM:
            return ApiResponse(
                404, {"ok": False, "error": {"message": f"Unknown program {program_id!r}"}}
            )
        defn = EXTENDED_FORMS_BY_PROGRAM[program_id]
        saved = self._reporting_service.load_filled_forms()
        f = saved.get(program_id)
        questions_data = [
            {
                "key": q.key,
                "label": q.label,
                "qtype": q.qtype,
                "star": q.star,
                "human_gate": q.human_gate,
                "choices": list(q.choices),
                "auto_from": q.auto_from,
                "current_value": (
                    f.answers[q.key].value if f and q.key in f.answers else None
                ),
            }
            for q in defn.questions
        ]
        return ApiResponse(
            200,
            {
                "ok": True,
                "form": {
                    "program_id": defn.program_id.value,
                    "program_code": defn.program_code,
                    "title": defn.title,
                    "operational_description": defn.operational_description,
                    "monitoring_criteria": list(defn.monitoring_criteria),
                    "policy_framework": defn.policy_framework,
                    "questions": questions_data,
                    "unresolved_star": (
                        list(f.unresolved_star_keys(defn))
                        if f
                        else list(defn.star_keys())
                    ),
                    "unresolved_human_gate": (
                        list(f.unresolved_human_gates(defn))
                        if f
                        else list(defn.human_gate_keys())
                    ),
                },
            },
        )

    def _reporting_list_mandates(self, query: Mapping[str, Any] | None = None) -> ApiResponse:
        program_code = None
        if query and "program_code" in query:
            raw = query["program_code"]
            program_code = raw[0] if isinstance(raw, (list, tuple)) else str(raw)
        mandates = self._reporting_service.list_mandates(program_code=program_code)
        return ApiResponse(
            200,
            {
                "ok": True,
                "mandates": [
                    {
                        "mandate_id": m.mandate_id,
                        "program_code": m.program_code,
                        "kind": m.kind,
                        "title": m.title,
                        "number": m.number,
                        "issued_on": m.issued_on,
                        "document_ref": m.document_ref,
                        "notes": m.notes,
                    }
                    for m in mandates
                ],
            },
        )

    def _reporting_create_mandate(self, payload: Any) -> ApiResponse:
        from ..reporting.plans import Mandate
        import uuid

        if not isinstance(payload, dict):
            return ApiResponse(400, {"ok": False, "error": {"message": "Invalid payload; object expected"}})

        title = str(payload.get("title", "")).strip()
        if not title:
            return ApiResponse(400, {"ok": False, "error": {"message": "Title is required"}})

        kind = str(payload.get("kind", "circular")).strip()
        mandate_id = str(payload.get("mandate_id", "")).strip() or f"mnd-{uuid.uuid4().hex[:8]}"
        program_code = str(payload.get("program_code", "")).strip()
        number = str(payload.get("number", "")).strip()
        issued_on = str(payload.get("issued_on", "")).strip()
        document_ref = str(payload.get("document_ref", "")).strip()
        notes = str(payload.get("notes", "")).strip()

        mandate = Mandate(
            mandate_id=mandate_id,
            program_code=program_code,
            kind=kind,
            title=title,
            number=number,
            issued_on=issued_on,
            document_ref=document_ref,
            notes=notes,
        )
        try:
            self._reporting_service.save_mandate(mandate)
        except Exception as exc:
            return ApiResponse(400, {"ok": False, "error": {"message": str(exc)}})

        return ApiResponse(
            201,
            {
                "ok": True,
                "mandate": {
                    "mandate_id": mandate.mandate_id,
                    "program_code": mandate.program_code,
                    "kind": mandate.kind,
                    "title": mandate.title,
                    "number": mandate.number,
                    "issued_on": mandate.issued_on,
                    "document_ref": mandate.document_ref,
                    "notes": mandate.notes,
                },
            },
        )

    def _reporting_delete_mandate(self, mandate_id: str) -> ApiResponse:
        deleted = self._reporting_service.delete_mandate(mandate_id)
        if not deleted:
            return ApiResponse(404, {"ok": False, "error": {"message": f"Mandate {mandate_id!r} not found"}})
        return ApiResponse(200, {"ok": True, "deleted": mandate_id})


    def _reporting_save_form(
        self,
        program_id: str,
        payload: Mapping[str, Any],
        *,
        app_session: Any = None,
    ) -> ApiResponse:
        from ..reporting.forms import EXTENDED_FORMS_BY_PROGRAM
        if program_id not in EXTENDED_FORMS_BY_PROGRAM:
            return ApiResponse(
                404, {"ok": False, "error": {"message": f"Unknown program {program_id!r}"}}
            )
        defn = EXTENDED_FORMS_BY_PROGRAM[program_id]
        answers_raw = payload.get("answers") or {}
        form = FilledForm(program_id=defn.program_id if program_id != "narrative" else "narrative")
        operator = (
            app_session.principal.display_name
            if app_session and hasattr(app_session, "principal")
            else "central_staff"
        )
        for k, val in answers_raw.items():
            form.set(k, val, answered_by=operator)
        self._reporting_service.save_filled_form(form, updated_by=operator)
        return ApiResponse(
            200,
            {
                "ok": True,
                "program_id": program_id,
                "unresolved_star": list(form.unresolved_star_keys(defn)),
            },
        )

    def _reporting_export(
        self,
        payload: Mapping[str, Any],
        *,
        app_session: Any = None,
    ) -> ApiResponse:
        operator = (
            app_session.principal.display_name
            if app_session and hasattr(app_session, "principal")
            else "central_staff"
        )
        province = str(payload.get("province_name", "مازندران"))
        period = str(payload.get("report_period", "۱۴۰۵"))
        allow_unresolved = bool(payload.get("allow_unresolved_star", False))
        dest_str = payload.get("destination")
        dest = (
            Path(dest_str)
            if dest_str
            else self.base_directory
            / "data"
            / "reporting"
            / f"report_{period}_{uuid.uuid4().hex[:6]}.xlsx"
        )

        try:
            out_path = self._reporting_service.export_with_audit(
                destination=dest,
                province_name=province,
                report_period=period,
                allow_unresolved_star=allow_unresolved,
                exported_by=operator,
            )
        except UnresolvedStarCellsError as exc:
            return ApiResponse(
                400,
                {
                    "ok": False,
                    "error": {
                        "code": "unresolved_star_cells",
                        "message": "Export blocked: required star cells are unfilled.",
                        "blockers": exc.blockers,
                    },
                },
            )
        except ReportingExportError as exc:
            return ApiResponse(
                500,
                {
                    "ok": False,
                    "error": {"code": exc.code, "message": str(exc)},
                },
            )

        return ApiResponse(
            200,
            {
                "ok": True,
                "export_path": str(out_path),
                "file_name": out_path.name,
            },
        )

    def _reporting_list_exports(self, query: Mapping[str, str]) -> ApiResponse:
        limit = int(query.get("limit", 50))
        exports = self._reporting_store.list_exports(limit=limit)
        return ApiResponse(200, {"ok": True, "exports": exports})

    @staticmethod
    def _payload_text(payload: Mapping[str, Any], key: str) -> str:
        value = payload.get(key)
        return value if isinstance(value, str) else ""

    @staticmethod
    def _untrusted_account_context_fields(value: Any) -> set[str]:
        """Find client-writable account selectors at any bounded JSON depth."""

        rejected: set[str] = set()
        pending: list[tuple[Any, int]] = [(value, 0)]
        visited = 0
        while pending:
            current, depth = pending.pop()
            visited += 1
            if visited > 10_000 or depth > 32:
                break
            if isinstance(current, Mapping):
                for key, item in current.items():
                    normalized = str(key).strip().casefold()
                    if normalized in {"messenger_account_id", "account_id"}:
                        rejected.add(normalized)
                    pending.append((item, depth + 1))
            elif isinstance(current, (list, tuple)):
                pending.extend((item, depth + 1) for item in current)
        return rejected

    def _session_cookie(self, token: str) -> str:
        max_age = self.config.features.app_user_auth.absolute_timeout_hours * 60 * 60
        cookie = (
            f"{APP_USER_SESSION_COOKIE}={token}; Path=/; "
            f"HttpOnly; SameSite=Strict; Max-Age={max_age}"
        )
        return cookie + ("; Secure" if self.config.deployment.secure_cookie else "")

    def _clear_session_cookie(self) -> str:
        cookie = (
            f"{APP_USER_SESSION_COOKIE}=; Path=/; "
            "HttpOnly; SameSite=Strict; Max-Age=0"
        )
        return cookie + ("; Secure" if self.config.deployment.secure_cookie else "")

    def _issued_session_response(
        self,
        issued: IssuedAppSession,
        *,
        status: int = 200,
    ) -> ApiResponse:
        auth = self._require_app_auth_service()
        payload = dict(issued.safe_payload())
        principal = dict(payload["principal"])
        principal["permissions"] = {
            **dict(principal.get("permissions", {})),
            "use_legacy_workspace": auth.can_use_legacy_workspace(issued.principal),
        }
        payload["principal"] = principal
        return ApiResponse(
            status,
            payload,
            headers={"Set-Cookie": self._session_cookie(issued.token)},
        )

    def _client_diagnostics_report(
        self,
        app_session: AuthorizedAppSession | None,
        payload: Mapping[str, Any],
        *,
        client_kind: str,
        request_id: str | None,
    ) -> ApiResponse:
        """Accept only a tiny allowlisted client-error envelope.

        Messages, stacks, URLs, DOM state, storage and arbitrary metadata are
        deliberately rejected instead of being sanitized after receipt.
        """

        allowed_keys = {"event", "level", "error_type", "safe_context"}
        rejected_keys = sorted(str(key) for key in payload if key not in allowed_keys)
        if rejected_keys:
            raise CompositionValidationError(
                "Client diagnostics contain unsupported fields.",
                code="client_diagnostic_fields_rejected",
                safe_context={"rejected_fields": rejected_keys},
            )
        event = str(payload.get("event") or "").strip().lower()
        if event not in _CLIENT_DIAGNOSTIC_EVENTS:
            raise CompositionValidationError(
                "Client diagnostic event is not allowed.",
                code="client_diagnostic_event_invalid",
            )
        level = str(payload.get("level") or "error").strip().lower()
        if level not in {"warning", "error"}:
            raise CompositionValidationError(
                "Client diagnostic level is invalid.",
                code="client_diagnostic_level_invalid",
            )
        error_type = str(payload.get("error_type") or "Error").strip()
        if not _SAFE_CLIENT_ERROR_TYPE.fullmatch(error_type):
            raise CompositionValidationError(
                "Client diagnostic error type is invalid.",
                code="client_diagnostic_error_type_invalid",
            )
        raw_context = payload.get("safe_context")
        if raw_context is None:
            raw_context = {}
        if not isinstance(raw_context, Mapping):
            raise CompositionValidationError(
                "Client diagnostic context is invalid.",
                code="client_diagnostic_context_invalid",
            )
        allowed_context = {
            "component_stack_present",
            "document_visible",
            "online",
            "surface",
        }
        rejected_context = sorted(str(key) for key in raw_context if key not in allowed_context)
        if rejected_context:
            raise CompositionValidationError(
                "Client diagnostic context contains unsupported fields.",
                code="client_diagnostic_context_rejected",
                safe_context={"rejected_fields": rejected_context},
            )
        surface = str(raw_context.get("surface") or "renderer").strip().lower()
        if surface not in {"renderer", "browser"}:
            raise CompositionValidationError(
                "Client diagnostic surface is invalid.",
                code="client_diagnostic_surface_invalid",
            )
        safe_context = {
            "surface": surface,
            "component_stack_present": bool(raw_context.get("component_stack_present", False)),
            "document_visible": bool(raw_context.get("document_visible", True)),
            "online": bool(raw_context.get("online", True)),
        }
        actor_id = (
            app_session.principal.app_user_id
            if app_session is not None
            else "legacy-local-client"
        )
        now = time.monotonic()
        with self._client_diagnostic_lock:
            recent = [
                observed
                for observed in self._client_diagnostic_windows.get(actor_id, [])
                if now - observed < 60.0
            ]
            if len(recent) >= 20:
                self._client_diagnostic_windows[actor_id] = recent
                raise CoordinatorAuthRateLimitError(
                    "Client diagnostic rate limit is active.",
                    code="client_diagnostic_rate_limited",
                    safe_context={"retry_after_seconds": 60},
                )
            recent.append(now)
            self._client_diagnostic_windows[actor_id] = recent
        self._application_logger.emit(
            "renderer_error_reported",
            level=level,
            result="failed" if level == "error" else "degraded",
            reason_code=event,
            correlation_id=request_id,
            fields={
                "client_event": event,
                "client_kind": client_kind,
                "error_type": error_type,
                "app_user_id": (
                    app_session.principal.app_user_id
                    if app_session is not None
                    else None
                ),
                **safe_context,
            },
        )
        return ApiResponse(202, {"ok": True, "accepted": True})

    def _app_auth_status(
        self,
        app_session_token: str | None,
        *,
        request_id: str | None,
    ) -> ApiResponse:
        if not self.app_user_auth_enabled:
            return ApiResponse(
                200,
                {
                    "ok": True,
                    "enabled": False,
                    "setup_required": False,
                    "authenticated": False,
                },
            )
        auth = self._require_app_auth_service()
        setup_required = auth.setup_required()
        if setup_required:
            return ApiResponse(
                200,
                {
                    "ok": True,
                    "enabled": True,
                    "setup_required": True,
                    "authenticated": False,
                    "self_registration_enabled": False,
                },
                headers={"Set-Cookie": self._clear_session_cookie()},
            )
        if not app_session_token:
            return ApiResponse(
                200,
                {
                    "ok": True,
                    "enabled": True,
                    "setup_required": False,
                    "authenticated": False,
                    "self_registration_enabled": self.app_user_self_registration_enabled,
                },
            )
        try:
            session = auth.authorize(
                app_session_token,
                rotate_csrf=True,
                request_id=request_id,
            )
        except CoordinatorAuthenticationError as exc:
            if exc.code not in {"app_auth_required", "app_auth_session_invalid"}:
                raise
            return ApiResponse(
                200,
                {
                    "ok": True,
                    "enabled": True,
                    "setup_required": False,
                    "authenticated": False,
                    "session_invalid": True,
                    "self_registration_enabled": self.app_user_self_registration_enabled,
                },
                headers={"Set-Cookie": self._clear_session_cookie()},
            )
        principal = session.principal.safe_summary()
        principal["permissions"] = {
            **dict(principal.get("permissions", {})),
            "use_legacy_workspace": auth.can_use_legacy_workspace(session.principal),
        }
        return ApiResponse(
            200,
            {
                "ok": True,
                "enabled": True,
                "setup_required": False,
                "authenticated": True,
                "self_registration_enabled": self.app_user_self_registration_enabled,
                "principal": principal,
                "csrf_token": session.csrf_token,
                "idle_expires_at": session.idle_expires_at,
                "absolute_expires_at": session.absolute_expires_at,
            },
        )

    def _app_auth_setup(
        self,
        payload: Mapping[str, Any],
        *,
        client_kind: str,
        request_id: str | None,
    ) -> ApiResponse:
        issued = self._require_app_auth_service().bootstrap_admin(
            username=self._payload_text(payload, "username"),
            password=self._payload_text(payload, "password"),
            display_name=self._payload_text(payload, "display_name"),
            client_kind=client_kind,
            request_id=request_id,
        )
        return self._issued_session_response(issued, status=201)

    def _app_auth_login(
        self,
        payload: Mapping[str, Any],
        *,
        client_kind: str,
        client_address: str | None,
        request_id: str | None,
    ) -> ApiResponse:
        issued = self._require_app_auth_service().authenticate(
            username=self._payload_text(payload, "username"),
            password=self._payload_text(payload, "password"),
            client_kind=client_kind,
            client_address=client_address,
            request_id=request_id,
        )
        return self._issued_session_response(issued)

    def _app_auth_register(
        self,
        payload: Mapping[str, Any],
        *,
        client_kind: str,
        request_id: str | None,
    ) -> ApiResponse:
        if not self.app_user_self_registration_enabled:
            raise CoordinatorAuthorizationError(
                "ثبت‌نام خودکار در این شیوهٔ استقرار فعال نیست.",
                code="app_auth_registration_unavailable",
            )
        issued = self._require_app_auth_service().register_user(
            username=self._payload_text(payload, "username"),
            password=self._payload_text(payload, "password"),
            display_name=self._payload_text(payload, "display_name"),
            client_kind=client_kind,
            request_id=request_id,
        )
        return self._issued_session_response(issued, status=201)

    def _require_authorized_session(
        self,
        session: AuthorizedAppSession | None,
    ) -> AuthorizedAppSession:
        if session is None:
            raise CoordinatorAuthenticationError(
                "برای ادامه وارد نرم‌افزار شوید.",
                code="app_auth_required",
            )
        return session

    def _app_auth_me(
        self,
        app_session: AuthorizedAppSession | None,
    ) -> ApiResponse:
        session = self._require_authorized_session(app_session)
        auth = self._require_app_auth_service()
        principal = session.principal.safe_summary()
        principal["permissions"] = {
            **dict(principal.get("permissions", {})),
            "use_legacy_workspace": auth.can_use_legacy_workspace(session.principal),
        }
        return ApiResponse(200, {"ok": True, "principal": principal})

    def _app_auth_logout(
        self,
        app_session: AuthorizedAppSession | None,
        *,
        request_id: str | None,
    ) -> ApiResponse:
        session = self._require_authorized_session(app_session)
        self._require_app_auth_service().logout(session, request_id=request_id)
        return ApiResponse(
            200,
            {"ok": True, "authenticated": False},
            headers={"Set-Cookie": self._clear_session_cookie()},
        )

    def _app_auth_logout_all(
        self,
        app_session: AuthorizedAppSession | None,
        *,
        request_id: str | None,
    ) -> ApiResponse:
        session = self._require_authorized_session(app_session)
        revoked = self._require_app_auth_service().logout_all(
            session,
            request_id=request_id,
        )
        return ApiResponse(
            200,
            {
                "ok": True,
                "authenticated": False,
                "sessions_revoked": revoked,
            },
            headers={"Set-Cookie": self._clear_session_cookie()},
        )

    def _app_auth_sessions_list(
        self,
        app_session: AuthorizedAppSession | None,
    ) -> ApiResponse:
        session = self._require_authorized_session(app_session)
        sessions = self._require_app_auth_service().list_own_sessions(session)
        return ApiResponse(200, {"ok": True, "sessions": sessions})

    def _app_auth_session_revoke(
        self,
        app_session: AuthorizedAppSession | None,
        session_id: str,
        *,
        request_id: str | None,
    ) -> ApiResponse:
        session = self._require_authorized_session(app_session)
        revoked = self._require_app_auth_service().revoke_own_session(
            session,
            session_id,
            request_id=request_id,
        )
        current = session.principal.session_id == session_id
        return ApiResponse(
            200,
            {
                "ok": True,
                "session_revoked": revoked,
                "current_session_revoked": current,
                "session_invalid": current,
            },
            headers={"Set-Cookie": self._clear_session_cookie()} if current else {},
        )

    def _app_auth_change_password(
        self,
        app_session: AuthorizedAppSession | None,
        payload: Mapping[str, Any],
        *,
        request_id: str | None,
    ) -> ApiResponse:
        session = self._require_authorized_session(app_session)
        self._require_app_auth_service().change_password(
            session,
            current_password=self._payload_text(payload, "current_password"),
            new_password=self._payload_text(payload, "new_password"),
            request_id=request_id,
        )
        return ApiResponse(200, {"ok": True, "password_changed": True})

    def _app_users_list(
        self,
        app_session: AuthorizedAppSession | None,
    ) -> ApiResponse:
        session = self._require_authorized_session(app_session)
        return ApiResponse(
            200,
            {
                "ok": True,
                "users": self._require_app_auth_service().list_users(session.principal),
            },
        )

    def _app_users_create(
        self,
        app_session: AuthorizedAppSession | None,
        payload: Mapping[str, Any],
        *,
        request_id: str | None,
    ) -> ApiResponse:
        session = self._require_authorized_session(app_session)
        created = self._require_app_auth_service().create_user(
            session.principal,
            username=self._payload_text(payload, "username"),
            password=self._payload_text(payload, "password"),
            display_name=self._payload_text(payload, "display_name"),
            global_role=self._payload_text(payload, "global_role"),
            request_id=request_id,
        )
        return ApiResponse(201, {"ok": True, "user": created})

    def _app_users_update(
        self,
        app_session: AuthorizedAppSession | None,
        app_user_id: str,
        payload: Mapping[str, Any],
        *,
        request_id: str | None,
    ) -> ApiResponse:
        session = self._require_authorized_session(app_session)
        role_value = payload.get("global_role")
        status_value = payload.get("status")
        updated = self._require_app_auth_service().update_user(
            session.principal,
            app_user_id,
            global_role=role_value if isinstance(role_value, str) else None,
            status=status_value if isinstance(status_value, str) else None,
            request_id=request_id,
        )
        return ApiResponse(200, {"ok": True, "user": updated})

    def _app_users_revoke_sessions(
        self,
        app_session: AuthorizedAppSession | None,
        app_user_id: str,
        *,
        request_id: str | None,
    ) -> ApiResponse:
        session = self._require_authorized_session(app_session)
        revoked = self._require_app_auth_service().revoke_user_sessions(
            session.principal,
            app_user_id,
            request_id=request_id,
        )
        return ApiResponse(
            200,
            {"ok": True, "sessions_revoked": revoked},
        )

    def _phone_accounts_list(
        self,
        app_session: AuthorizedAppSession | None,
    ) -> ApiResponse:
        session = self._require_authorized_session(app_session)
        accounts = self._require_app_auth_service().list_phone_accounts(
            session.principal
        )
        return ApiResponse(200, {"ok": True, "phone_accounts": accounts})

    def _phone_account_membership_update(
        self,
        app_session: AuthorizedAppSession | None,
        phone_account_id: str,
        payload: Mapping[str, Any],
        *,
        request_id: str | None,
    ) -> ApiResponse:
        session = self._require_authorized_session(app_session)
        membership = self._require_app_auth_service().update_phone_account_membership(
            session.principal,
            phone_account_id=phone_account_id,
            app_user_id=self._payload_text(payload, "app_user_id"),
            role=self._payload_text(payload, "role"),
            status=self._payload_text(payload, "status"),
            request_id=request_id,
        )
        return ApiResponse(200, {"ok": True, "membership": membership})

    def _app_integrations_list(
        self,
        app_session: AuthorizedAppSession | None,
    ) -> ApiResponse:
        session = self._require_authorized_session(app_session)
        is_admin = session.principal.global_role == "admin"
        records = self._require_coordinator().list_app_integrations(
            app_user_id=session.principal.app_user_id,
            include_inactive=is_admin,
        )
        return ApiResponse(
            200,
            {
                "ok": True,
                "integrations": [record.safe_summary() for record in records],
                "can_manage": is_admin,
            },
        )

    def _app_integration_update(
        self,
        app_session: AuthorizedAppSession | None,
        integration_id: str,
        payload: Mapping[str, Any],
        *,
        request_id: str | None,
    ) -> ApiResponse:
        session = self._require_authorized_session(app_session)
        record = self._require_coordinator().update_app_integration(
            integration_id,
            app_user_id=session.principal.app_user_id,
            global_role=session.principal.global_role,
            status=self._payload_text(payload, "status"),
            request_id=request_id,
        )
        return ApiResponse(200, {"ok": True, "integration": record.safe_summary()})

    def _messenger_accounts_list(
        self,
        app_session: AuthorizedAppSession | None,
    ) -> ApiResponse:
        session = self._require_authorized_session(app_session)
        accounts = self._require_app_auth_service().list_messenger_accounts(
            session.principal
        )
        return ApiResponse(
            200,
            {
                "ok": True,
                "feature_enabled": self.config.features.multi_session.enabled,
                "default_messenger_account_id": (
                    self.config.features.multi_session.legacy_default_messenger_account_id
                    if self.config.features.multi_session.enabled
                    else None
                ),
                "accounts": accounts,
                "provider_adapters": {
                    key: descriptor.safe_payload()
                    for key, descriptor in self._provider_registry.descriptor_catalog().items()
                },
            },
        )

    def _messenger_account_status(
        self,
        app_session: AuthorizedAppSession | None,
        messenger_account_id: str,
    ) -> ApiResponse:
        session = self._require_authorized_session(app_session)
        account = self._require_app_auth_service().require_messenger_account_access(
            session.principal,
            messenger_account_id,
            operation="view",
        )
        return ApiResponse(200, {"ok": True, "account": account})

    def _messenger_account_capabilities(
        self,
        app_session: AuthorizedAppSession | None,
        messenger_account_id: str,
    ) -> ApiResponse:
        session = self._require_authorized_session(app_session)
        self._require_app_auth_service().require_messenger_account_access(
            session.principal,
            messenger_account_id,
            operation="view",
        )
        snapshot = self._require_provider_capability_service().snapshot(
            messenger_account_id
        )
        return ApiResponse(200, {"ok": True, **snapshot.safe_summary()})

    def _messenger_account_onboard(
        self,
        app_session: AuthorizedAppSession | None,
        payload: Mapping[str, Any],
        *,
        request_id: str | None,
    ) -> ApiResponse:
        if not self.config.features.multi_session.enabled:
            raise CoordinatorAuthorizationError(
                "Account onboarding is not enabled.",
                code="multi_session_onboarding_disabled",
            )
        session = self._require_authorized_session(app_session)
        allowed_keys = {"provider", "phone", "label"}
        rejected_keys = sorted(str(key) for key in payload if key not in allowed_keys)
        if rejected_keys:
            raise CompositionValidationError(
                "Account onboarding contains unsupported fields.",
                code="messenger_account_onboarding_fields_rejected",
                safe_context={"rejected_fields": rejected_keys},
            )
        
        provider_value = payload.get("provider")
        phone_value = payload.get("phone")
        
        if not isinstance(provider_value, str):
            raise CompositionValidationError(
                "Account onboarding provider field is invalid.",
                code="messenger_account_onboarding_identity_fields_invalid",
            )
        
        if phone_value is None:
            raise CompositionValidationError(
                "Account onboarding requires a phone identity field.",
                code="messenger_account_onboarding_identity_fields_invalid",
            )
            
        if phone_value is not None and not isinstance(phone_value, str):
            raise CompositionValidationError(
                "Account onboarding identity fields are invalid.",
                code="messenger_account_onboarding_identity_fields_invalid",
            )
            
        if payload.get("label") is not None and not isinstance(payload.get("label"), str):
            raise CompositionValidationError(
                "Account onboarding label is invalid.",
                code="messenger_account_onboarding_label_invalid",
            )
        provider = self._payload_text(payload, "provider").strip().lower()
        descriptor = self._provider_registry.descriptor_catalog().get(provider)
        if descriptor is None or not descriptor.onboarding_enabled:
            raise CompositionValidationError(
                "Account onboarding is unavailable for this provider.",
                code=(
                    descriptor.reason_code
                    if descriptor is not None and descriptor.reason_code
                    else "provider_onboarding_unavailable"
                ),
                safe_context={"provider": provider or "unknown"},
            )
        if descriptor.account_identity_kind != "phone_e164":
            raise CompositionValidationError(
                "Account onboarding does not support this provider identity kind.",
                code="provider_onboarding_identity_kind_unsupported",
                safe_context={"provider": provider},
            )
        identity = validate_canonical_e164(self._payload_text(payload, "phone"))
        label_value = payload.get("label")
        label = label_value if isinstance(label_value, str) else None
        self._application_logger.emit(
            "messenger_account_onboarding_started",
            result="started",
            correlation_id=request_id,
            fields={
                "provider": provider,
                "actor_app_user_id": session.principal.app_user_id,
            },
        )
        try:
            result = self._require_app_auth_service().onboard_messenger_account(
                session.principal,
                provider=provider,
                canonical_phone=identity,
                label=label,
                request_id=request_id,
            )
        except BridgeError as exc:
            self._application_logger.emit(
                "messenger_account_onboarding_rejected",
                level="warning",
                result="rejected",
                reason_code=exc.code,
                correlation_id=request_id,
                fields={"provider": provider, "error_type": type(exc).__name__},
            )
            raise
        account = self._require_app_auth_service().require_messenger_account_access(
            session.principal,
            result.messenger_account_id,
            operation="view",
        )
        self._application_logger.emit(
            (
                "messenger_account_onboarding_succeeded"
                if result.created
                else "messenger_account_onboarding_reused"
            ),
            result="succeeded",
            correlation_id=request_id,
            fields={
                "provider": provider,
                "messenger_account_id": result.messenger_account_id,
                "created": result.created,
                "identity_record_created": result.phone_account_created,
                "owner_membership_created": result.membership_created,
            },
        )
        return ApiResponse(
            201 if result.created else 200,
            {
                "ok": True,
                "account": account,
                "onboarding": result.safe_summary(),
            },
        )

    def _messenger_account_worker_action(
        self,
        app_session: AuthorizedAppSession | None,
        messenger_account_id: str,
        *,
        action: str,
        request_id: str | None,
    ) -> ApiResponse:
        if not self.config.features.multi_session.enabled:
            raise CoordinatorAuthorizationError(
                "Account worker management is not enabled.",
                code="multi_session_worker_management_disabled",
            )
        session = self._require_authorized_session(app_session)
        self._require_app_auth_service().require_messenger_account_access(
            session.principal,
            messenger_account_id,
            operation="manage_worker",
        )
        if action == "start":
            self._runtime_registry.start_account(
                messenger_account_id,
                actor_app_user_id=session.principal.app_user_id,
                actor_global_role=session.principal.global_role,
                request_id=request_id,
            )
            account = self._require_app_auth_service().require_messenger_account_access(
                session.principal,
                messenger_account_id,
                operation="view",
            )
            return ApiResponse(
                200,
                {
                    "ok": True,
                    "account": account,
                    "worker": account.get("worker"),
                },
            )
        if action == "stop":
            record = self._runtime_registry.stop_account(
                messenger_account_id,
                actor_app_user_id=session.principal.app_user_id,
                actor_global_role=session.principal.global_role,
                request_id=request_id,
            )
            return ApiResponse(
                200,
                {"ok": True, "account": record.safe_summary(), "worker": None},
            )
        raise CompositionValidationError(
            "The worker action is invalid.",
            code="worker_action_invalid",
        )

    def _authorize(self, authorization: str | None) -> None:
        if self.bearer_token is None:
            return
        prefix = "Bearer "
        supplied = authorization[len(prefix):] if authorization and authorization.startswith(prefix) else ""
        if not supplied or not hmac.compare_digest(supplied, self.bearer_token):
            raise CredentialError("A valid local API bearer token is required.", code="api_unauthorized")

    def _health(self) -> dict[str, Any]:
        return {
            "ok": True,
            "service": "eitaa-bridge-api",
            "status": "alive",
            "api_version": self.API_VERSION,
            "bridge_version": __version__,
            "core_product": "0.6.0-core7.4.5-gmi1",
            "core_package": "0.6.0.dev19",
        }

    def _observability_health(self) -> dict[str, Any]:
        return {
            "ok": True,
            "runtime_logger": self._application_logger.health_summary(),
            "disk": observability_disk_health(self.base_directory),
            "retention_policy": {
                "rotation_keep_newest": 5,
                "max_age_days": 30,
                "max_total_bytes": 100 * 1024 * 1024,
            },
        }

    def _readiness(self) -> dict[str, Any]:
        return {
            "ok": True,
            "service": "eitaa-bridge-api",
            "status": "ready",
            "deployment_mode": self.config.deployment.mode,
        }

    def _schema(self) -> dict[str, Any]:
        return {
            "ok": True,
            "api_version": self.API_VERSION,
            "routes": [
                {"method": "GET", "path": "/api/v1/health"},
                {"method": "GET", "path": "/api/v1/readiness"},
                {"method": "GET", "path": "/api/v1/schema"},
                {"method": "GET", "path": "/api/v2/app-auth/status"},
                {"method": "POST", "path": "/api/v2/app-auth/setup"},
                {"method": "POST", "path": "/api/v2/app-auth/login"},
                {"method": "POST", "path": "/api/v2/app-auth/register"},
                {"method": "GET", "path": "/api/v2/app-auth/me"},
                {"method": "GET", "path": "/api/v2/observability/events"},
                {"method": "GET", "path": "/api/v2/observability/health"},
                {"method": "POST", "path": "/api/v2/client-diagnostics"},
                {"method": "POST", "path": "/api/v2/app-auth/logout"},
                {"method": "POST", "path": "/api/v2/app-auth/logout-all"},
                {"method": "GET", "path": "/api/v2/app-auth/sessions"},
                {
                    "method": "POST",
                    "path": "/api/v2/app-auth/sessions/{session_id}/revoke",
                },
                {"method": "POST", "path": "/api/v2/app-auth/change-password"},
                {"method": "GET", "path": "/api/v2/app-users"},
                {"method": "POST", "path": "/api/v2/app-users"},
                {
                    "method": "POST",
                    "path": "/api/v2/app-users/{app_user_id}/update",
                },
                {
                    "method": "POST",
                    "path": "/api/v2/app-users/{app_user_id}/revoke-sessions",
                },
                {"method": "GET", "path": "/api/v2/phone-accounts"},
                {
                    "method": "POST",
                    "path": "/api/v2/phone-accounts/{phone_account_id}/memberships",
                },
                {"method": "GET", "path": "/api/v2/app-integrations"},
                {
                    "method": "POST",
                    "path": "/api/v2/app-integrations/{integration_id}/update",
                },
                {"method": "GET", "path": "/api/v2/messenger-accounts"},
                {"method": "POST", "path": "/api/v2/messenger-accounts"},
                {
                    "method": "GET",
                    "path": "/api/v2/messenger-accounts/{messenger_account_id}",
                },
                {
                    "method": "GET",
                    "path": "/api/v2/messenger-accounts/{messenger_account_id}/capabilities",
                },
                {
                    "method": "POST",
                    "path": "/api/v2/messenger-accounts/{messenger_account_id}/worker/start",
                },
                {
                    "method": "POST",
                    "path": "/api/v2/messenger-accounts/{messenger_account_id}/worker/stop",
                },
                {
                    "method": "POST",
                    "path": "/api/v2/messenger-accounts/{messenger_account_id}/dialogs/query",
                },
                {
                    "method": "POST",
                    "path": "/api/v2/messenger-accounts/{messenger_account_id}/history/query",
                },
                {
                    "method": "POST",
                    "path": "/api/v2/messenger-accounts/{messenger_account_id}/messages/send-text",
                },
                {
                    "method": "POST",
                    "path": "/api/v2/messenger-accounts/{messenger_account_id}/media/read",
                },
                {
                    "method": "POST",
                    "path": "/api/v2/messenger-accounts/{messenger_account_id}/contacts/query",
                },
                {
                    "method": "POST",
                    "path": "/api/v2/messenger-accounts/{messenger_account_id}/contacts/upsert",
                },
                {"method": "GET", "path": "/api/v1/scheduler/status"},
                {"method": "GET", "path": "/api/v1/auth/status"},
                {"method": "POST", "path": "/api/v1/auth/request-code"},
                {"method": "POST", "path": "/api/v1/auth/submit-code"},
                {"method": "POST", "path": "/api/v1/auth/submit-password"},
                {"method": "POST", "path": "/api/v1/auth/logout"},
                {"method": "POST", "path": "/api/v1/auth/reset-local-session"},
                {"method": "POST", "path": "/api/v1/auth/recover-phone-identity"},
                {"method": "GET", "path": "/api/v1/sites"},
                {"method": "GET", "path": "/api/v1/settings/sites"},
                {"method": "GET", "path": "/api/v2/settings/deployment"},
                {
                    "method": "POST",
                    "path": "/api/v2/settings/deployment/port",
                },
                {"method": "POST", "path": "/api/v1/settings/sites/upsert"},
                {"method": "POST", "path": "/api/v1/settings/sites/default"},
                {"method": "POST", "path": "/api/v1/settings/sites/delete"},
                {"method": "POST", "path": "/api/v1/settings/sites/test"},
                {"method": "GET", "path": "/api/v1/capabilities"},
                {"method": "GET", "path": "/api/v1/compositions"},
                {"method": "GET", "path": "/api/v1/wordpress/categories"},
                {"method": "GET", "path": "/api/v1/wordpress/tags"},
                {"method": "POST", "path": "/api/v1/wordpress/tags"},
                {"method": "POST", "path": "/api/v1/wordpress/post"},
                {"method": "GET", "path": "/api/v2/audit"},
                {"method": "POST", "path": "/api/v2/audit/export"},
                {"method": "POST", "path": "/api/v1/dialogs/list"},
                {"method": "POST", "path": "/api/v1/dialogs/live-sync"},
                {"method": "POST", "path": "/api/v1/dialogs/sync"},
                {"method": "POST", "path": "/api/v1/dialogs/sync/start"},
                {"method": "GET", "path": "/api/v1/dialogs/sync/status"},
                {"method": "POST", "path": "/api/v1/dialogs/avatar"},
                {"method": "POST", "path": "/api/v1/dialogs/manual"},
                {"method": "POST", "path": "/api/v1/dialogs/favorite"},
                {"method": "POST", "path": "/api/v1/dialogs/display-kind"},
                {"method": "POST", "path": "/api/v1/community/members/sync"},
                {"method": "POST", "path": "/api/v1/community/members/list"},
                {"method": "POST", "path": "/api/v1/community/members/sync/start"},
                {"method": "POST", "path": "/api/v1/community/members/remove/start"},
                {"method": "POST", "path": "/api/v1/community/members/invite/start"},
                {"method": "POST", "path": "/api/v1/community/bulk/preview"},
                {"method": "POST", "path": "/api/v1/community/bulk/validate"},
                {"method": "POST", "path": "/api/v1/community/bulk/create"},
                {"method": "POST", "path": "/api/v1/community/bulk/run"},
                {"method": "POST", "path": "/api/v1/community/bulk/jobs"},
                {"method": "POST", "path": "/api/v1/community/bulk/recipients"},
                {"method": "POST", "path": "/api/v1/community/bulk/action"},
                {"method": "POST", "path": "/api/v1/phone-lists/import"},
                {"method": "GET", "path": "/api/v1/phone-lists"},
                {"method": "POST", "path": "/api/v1/phone-lists/status"},
                {"method": "POST", "path": "/api/v1/phone-lists/resolve"},
                {"method": "POST", "path": "/api/v1/phone-lists/preview"},
                {"method": "POST", "path": "/api/v1/phone-lists/bulk/create"},
                {"method": "POST", "path": "/api/v1/membership/preview"},
                {"method": "POST", "path": "/api/v1/membership/create"},
                {"method": "POST", "path": "/api/v1/membership/run"},
                {"method": "POST", "path": "/api/v1/membership/jobs"},
                {"method": "POST", "path": "/api/v1/membership/action"},
                {"method": "GET", "path": "/api/v1/background/status"},
                {"method": "POST", "path": "/api/v1/messages/list"},
                {"method": "POST", "path": "/api/v1/messages/media-preview"},
                {"method": "POST", "path": "/api/v1/messages/send"},
                {"method": "POST", "path": "/api/v1/messages/read"},
                {"method": "POST", "path": "/api/v1/messages/read/enqueue"},
                {"method": "POST", "path": "/api/v1/messages/sync"},
                {"method": "POST", "path": "/api/v1/messages/date-range/sync"},
                {"method": "POST", "path": "/api/v1/messages/usage"},
                {"method": "POST", "path": "/api/v1/messages/index/start"},
                {"method": "GET", "path": "/api/v1/messages/index/status"},
                {"method": "POST", "path": "/api/v1/messages/index/cancel"},
                {"method": "POST", "path": "/api/v1/messages/index/results"},
                {"method": "POST", "path": "/api/v1/messages/index/feedback"},
                {"method": "POST", "path": "/api/v1/eitaa-contacts/list"},
                {"method": "POST", "path": "/api/v1/eitaa-contacts/add"},
                {"method": "POST", "path": "/api/v1/eitaa-contacts/remove"},
                {"method": "POST", "path": "/api/v1/eitaa-contacts/categorize"},
                {"method": "POST", "path": "/api/v1/eitaa-contacts/import-local/start"},
                {"method": "POST", "path": "/api/v1/contacts/list"},
                {"method": "POST", "path": "/api/v1/contacts/upsert"},
                {"method": "POST", "path": "/api/v1/contacts/archive"},
                {"method": "GET", "path": "/api/v1/contacts/categories"},
                {"method": "POST", "path": "/api/v1/contacts/categories/save"},
                {"method": "POST", "path": "/api/v1/contacts/categories/delete"},
                {"method": "POST", "path": "/api/v1/contacts/import/preview"},
                {"method": "POST", "path": "/api/v1/contacts/import/start"},
                {"method": "POST", "path": "/api/v1/contacts/import/community/start"},
                {"method": "POST", "path": "/api/v1/contacts/import/phone-list/start"},
                {"method": "GET", "path": "/api/v1/contacts/import/status"},
                {"method": "POST", "path": "/api/v1/contacts/import/cancel"},
                {"method": "POST", "path": "/api/v1/contacts/targets/preview"},
                {"method": "POST", "path": "/api/v1/contacts/add-to-messenger/start"},
                {"method": "POST", "path": "/api/v1/contacts/audit"},
                {"method": "POST", "path": "/api/v1/compositions/preview"},
                {"method": "POST", "path": "/api/v1/compositions/status"},
                {"method": "POST", "path": "/api/v1/compositions/publish"},
                {"method": "POST", "path": "/api/v1/compositions/update"},
            ],
            "composer": {
                "allowed_post_statuses": ["draft", "publish"],
                "publish_requires": {"post_status": "publish", "confirm_publish": True},
                "max_sources": 100,
            },
        }

    def _run_eitaa(
        self,
        *,
        priority: EitaaPriority,
        kind: str,
        callback: Any,
        timeout: float | None = None,
    ) -> Any:
        return self._runtime.run_sync(
            priority=priority,
            kind=kind,
            callback=self._runtime_bound_target(callback),
            timeout=timeout,
        )

    @staticmethod
    def _aware_datetime(value: Any, name: str) -> datetime:
        raw = str(value or "").strip()
        if not raw:
            raise CompositionValidationError(
                f"{name} is required.", code=f"api_{name}_required"
            )
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise CompositionValidationError(
                f"{name} must be an ISO-8601 datetime.",
                code=f"api_invalid_{name}",
            ) from exc
        if parsed.tzinfo is None:
            raise CompositionValidationError(
                f"{name} must include a timezone.",
                code=f"api_invalid_{name}",
            )
        return parsed.astimezone(timezone.utc)

    def _core_config(self) -> EitaaCoreConfig:
        if isinstance(self._runtime, EitaaProcessRuntime):
            raise EitaaRuntimeError(
                "Provider authentication must execute inside the Eitaa Child process.",
                code="eitaa_process_auth_ipc_required",
            )
        config = self._runtime.ownership.core
        return EitaaCoreConfig(
            session_file=config.session_file,
            database_file=config.database_file,
            media_directory=config.media_directory,
            diagnostics_root=config.diagnostics_root,
            diagnostics_enabled=config.diagnostics_enabled,
            timeout_seconds=config.timeout_seconds,
        )

    @staticmethod
    def _account_auth_actor(
        app_session: AuthorizedAppSession | None,
    ) -> tuple[str | None, str | None]:
        if app_session is None:
            return None, None
        return (
            app_session.principal.app_user_id,
            app_session.principal.global_role,
        )

    @staticmethod
    def _account_auth_fields(record: Any) -> dict[str, object]:
        return {
            "messenger_account_id": record.messenger_account_id,
            "provider": record.provider,
            "auth_state": record.auth_state,
            "session_generation": record.session_generation,
        }

    def _process_auth_request(
        self,
        runtime: EitaaProcessRuntime,
        method: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Forward one v1 auth route to the account Child RPC boundary."""

        response = runtime.auth_operation_request(
            method,
            payload,
            timeout_seconds=self.config.features.worker_process.request_timeout_seconds,
        )
        result = dict(response)
        result.pop("ok", None)
        if "session_snapshot" in result:
            result["session"] = result.pop("session_snapshot")
        return {"ok": True, **result}

    def _account_session_file(self) -> Path:
        """Account session path readable from the parent without opening Core."""

        return self._runtime.ownership.core.session_file

    def _close_auth_attempt(self) -> None:
        if self._auth_runtime is not None:
            try:
                self._auth_runtime.close()
            finally:
                self._auth_runtime = None
        self._auth_challenge = None

    def _archive_uncoordinated_session(self) -> str | None:
        """Fail closed if Core saved a token but Coordinator did not accept it."""

        session_file = self._core_config().session_file
        if not session_file.is_file():
            return None
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        archive = session_file.with_name(
            f"{session_file.name}.uncoordinated.{timestamp}.bak"
        )
        try:
            os.replace(session_file, archive)
        except OSError as exc:
            self._runtime_logger.emit(
                "auth_uncoordinated_session_archive_failed",
                level="error",
                fields={"error_type": type(exc).__name__},
            )
            return None
        self._runtime_logger.emit(
            "auth_uncoordinated_session_archived",
            level="warning",
            fields={"archive_name": archive.name},
        )
        return archive.name

    def _archive_account_session_file(self, marker: str) -> str | None:
        session_file = self._core_config().session_file
        if not session_file.is_file():
            return None
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        archive = session_file.with_name(
            f"{session_file.name}.{marker}.{timestamp}.bak"
        )
        try:
            os.replace(session_file, archive)
        except OSError as exc:
            raise AuthenticationRuntimeError(
                "بایگانی امن نشست حساب ناموفق بود.",
                safe_context={"error_type": type(exc).__name__},
                code="auth_session_archive_failed",
            ) from exc
        if session_file.exists():
            raise AuthenticationRuntimeError(
                "فایل نشست حساب پس از بایگانی همچنان فعال است.",
                code="auth_session_archive_verification_failed",
            )
        return archive.name

    def _audit_account_auth_failure(
        self,
        *,
        action: str,
        reason_code: str,
        app_session: AuthorizedAppSession | None,
        request_id: str | None,
        safe_metadata: Mapping[str, Any] | None = None,
        result: str = "failed",
    ) -> None:
        actor_id, actor_role = self._account_auth_actor(app_session)
        try:
            self._runtime.audit_auth_event(
                action=action,
                result=result,
                reason_code=reason_code,
                actor_app_user_id=actor_id,
                actor_global_role=actor_role,
                request_id=request_id,
                safe_metadata=safe_metadata,
            )
        except BridgeError as audit_error:
            self._runtime_logger.emit(
                "auth_audit_write_failed",
                level="error",
                fields={
                    "action": action,
                    "error_code": audit_error.code,
                },
            )

    def _transition_account_auth(
        self,
        record: Any,
        *,
        new_state: str,
        increment_generation: bool,
        reason_code: str,
        action: str,
        app_session: AuthorizedAppSession | None,
        request_id: str | None,
        mark_validated: bool = False,
        audit_when_unchanged: bool = True,
        safe_metadata: Mapping[str, Any] | None = None,
    ) -> Any:
        actor_id, actor_role = self._account_auth_actor(app_session)
        updated = self._runtime.transition_auth(
            expected_states={record.auth_state},
            expected_generation=record.session_generation,
            new_state=new_state,
            increment_generation=increment_generation,
            reason_code=reason_code,
            action=action,
            mark_validated=mark_validated,
            audit_when_unchanged=audit_when_unchanged,
            actor_app_user_id=actor_id,
            actor_global_role=actor_role,
            request_id=request_id,
            safe_metadata=safe_metadata,
        )
        self._runtime_logger.emit(
            "auth_state_transition",
            fields={
                "from_auth_state": record.auth_state,
                "to_auth_state": updated.auth_state,
                "from_session_generation": record.session_generation,
                "to_session_generation": updated.session_generation,
                "reason": reason_code,
            },
        )
        return updated

    def _auth_status(
        self,
        *,
        app_session: AuthorizedAppSession | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        runtime = self._runtime
        if isinstance(runtime, EitaaProcessRuntime):
            return self._process_auth_request(
                runtime,
                "eitaa.auth.status",
                {},
            )
        if runtime.is_account_scoped:
            return self._auth_status_account(
                app_session=app_session,
                request_id=request_id,
            )
        return self._auth_status_legacy()

    def _auth_status_account(
        self,
        *,
        app_session: AuthorizedAppSession | None,
        request_id: str | None,
    ) -> dict[str, Any]:
        core_config = self._core_config()
        core = None
        with self._eitaa_lock, self._auth_lock:
            record = self._runtime.refresh_auth_record()
            challenge = (
                self._auth_challenge
                if isinstance(self._auth_challenge, AccountAuthChallenge)
                else None
            )
            if challenge is not None:
                challenge_valid = (
                    challenge.messenger_account_id == record.messenger_account_id
                    and challenge.session_generation == record.session_generation
                    and record.auth_state == "challenge_pending"
                )
                if not challenge_valid or challenge.is_expired():
                    reason = (
                        "challenge_expired"
                        if challenge.is_expired()
                        else "challenge_context_mismatch"
                    )
                    self._close_auth_attempt()
                    if record.auth_state == "challenge_pending":
                        record = self._transition_account_auth(
                            record,
                            new_state="expired",
                            increment_generation=False,
                            reason_code=reason,
                            action="eitaa.auth.challenge.expired",
                            app_session=app_session,
                            request_id=request_id,
                            safe_metadata={"challenge_stage": challenge.stage},
                        )
                    challenge = None
            elif record.auth_state == "challenge_pending":
                record = self._transition_account_auth(
                    record,
                    new_state="expired",
                    increment_generation=False,
                    reason_code="challenge_runtime_missing",
                    action="eitaa.auth.challenge.expired",
                    app_session=app_session,
                    request_id=request_id,
                    safe_metadata={"challenge_stage": "unknown"},
                )

            if challenge is not None:
                return {
                    "ok": True,
                    "authenticated": False,
                    "session_present": core_config.session_file.is_file(),
                    "password_pending": challenge.stage == "password",
                    "fresh_login_available": False,
                    "challenge": challenge.safe_summary(),
                    **self._account_auth_fields(record),
                }

            if not core_config.session_file.is_file():
                if record.auth_state == "authenticated":
                    record = self._transition_account_auth(
                        record,
                        new_state="invalid",
                        increment_generation=True,
                        reason_code="local_session_missing",
                        action="eitaa.auth.session.invalidated",
                        app_session=app_session,
                        request_id=request_id,
                        safe_metadata={"session_file_present": False},
                    )
                return {
                    "ok": True,
                    "authenticated": False,
                    "session_present": False,
                    "password_pending": False,
                    "fresh_login_available": True,
                    **self._account_auth_fields(record),
                }

            if record.auth_state in {"revoked", "invalid"}:
                return {
                    "ok": True,
                    "authenticated": False,
                    "session_present": True,
                    "session_error": True,
                    "session_invalid": True,
                    "session_error_code": "auth_metadata_rejects_active_session",
                    "password_pending": False,
                    "fresh_login_available": True,
                    **self._account_auth_fields(record),
                }

            try:
                core = EitaaCore.open(core_config)
            except Exception as exc:
                return {
                    "ok": True,
                    "authenticated": False,
                    "session_present": True,
                    "session_error": True,
                    "session_error_code": "auth_session_open_failed",
                    "session_error_type": type(exc).__name__,
                    "password_pending": False,
                    "fresh_login_available": True,
                    **self._account_auth_fields(record),
                }
            try:
                session_summary = core.session.safe_summary()
                try:
                    core.discovery.list_dialogs(limit=1)
                except Exception as exc:
                    if self._is_invalid_session_error(exc):
                        if record.auth_state != "invalid":
                            record = self._transition_account_auth(
                                record,
                                new_state="invalid",
                                increment_generation=True,
                                reason_code="remote_session_invalid",
                                action="eitaa.auth.session.invalidated",
                                app_session=app_session,
                                request_id=request_id,
                                safe_metadata={
                                    "error_type": type(exc).__name__,
                                    "remote_status": 401,
                                    "session_file_present": True,
                                },
                            )
                        return {
                            "ok": True,
                            "authenticated": False,
                            "session_present": True,
                            "session": session_summary,
                            "session_error": True,
                            "session_invalid": True,
                            "session_error_code": "auth_session_invalid",
                            "session_error_type": type(exc).__name__,
                            "password_pending": False,
                            "fresh_login_available": True,
                            "remote_probe": False,
                            "remote_warning": False,
                            "remote_error_code": 401,
                            **self._account_auth_fields(record),
                        }
                    return {
                        "ok": True,
                        "authenticated": record.auth_state == "authenticated",
                        "session_present": True,
                        "session": session_summary,
                        "password_pending": False,
                        "fresh_login_available": record.auth_state != "authenticated",
                        "remote_probe": False,
                        "remote_warning": True,
                        "remote_error_type": type(exc).__name__,
                        "remote_error_code": getattr(exc, "code", None),
                        **self._account_auth_fields(record),
                    }
                record = self._transition_account_auth(
                    record,
                    new_state="authenticated",
                    increment_generation=False,
                    reason_code="remote_session_validated",
                    action="eitaa.auth.session.validated",
                    app_session=app_session,
                    request_id=request_id,
                    mark_validated=True,
                    audit_when_unchanged=False,
                    safe_metadata={"session_file_present": True},
                )
                return {
                    "ok": True,
                    "authenticated": True,
                    "session_present": True,
                    "session": session_summary,
                    "password_pending": False,
                    "fresh_login_available": False,
                    "remote_probe": True,
                    "remote_warning": False,
                    **self._account_auth_fields(record),
                }
            finally:
                core.close()

    def _auth_status_legacy(self) -> dict[str, Any]:
        core_config = self._core_config()
        if not core_config.session_file.exists():
            return {
                "ok": True, "authenticated": False, "session_present": False,
                "password_pending": self._auth_challenge is not None, "fresh_login_available": True,
            }
        core = None
        try:
            with self._eitaa_lock:
                try:
                    core = EitaaCore.open(core_config)
                except Exception as exc:
                    return {
                        "ok": True, "authenticated": False, "session_present": True,
                        "session_error": True, "session_error_code": "auth_session_open_failed",
                        "session_error_type": type(exc).__name__,
                        "password_pending": self._auth_challenge is not None,
                        "fresh_login_available": True,
                    }
                session_summary = core.session.safe_summary()
                try:
                    core.discovery.list_dialogs(limit=1)
                except Exception as exc:
                    if self._is_invalid_session_error(exc):
                        self._runtime_logger.emit(
                            "auth_session_invalid_detected",
                            level="warning",
                            fields={
                                "error_type": type(exc).__name__,
                                "remote_code": 401,
                                "recovery_available": True,
                            },
                        )
                        return {
                            "ok": True,
                            "authenticated": False,
                            "session_present": True,
                            "session": session_summary,
                            "session_error": True,
                            "session_invalid": True,
                            "session_error_code": "auth_session_invalid",
                            "session_error_type": type(exc).__name__,
                            "password_pending": False,
                            "fresh_login_available": True,
                            "remote_probe": False,
                            "remote_warning": False,
                            "remote_error_code": 401,
                        }
                    return {
                        "ok": True, "authenticated": True, "session_present": True,
                        "session": session_summary, "password_pending": False,
                        "fresh_login_available": False, "remote_probe": False,
                        "remote_warning": True, "remote_error_type": type(exc).__name__,
                        "remote_error_code": getattr(exc, "code", None),
                    }
                return {
                    "ok": True, "authenticated": True, "session_present": True,
                    "session": session_summary, "password_pending": False,
                    "fresh_login_available": False, "remote_probe": True, "remote_warning": False,
                }
        finally:
            if core is not None:
                core.close()

    def _auth_reset_local_session(
        self,
        payload: Mapping[str, Any],
        *,
        app_session: AuthorizedAppSession | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        runtime = self._runtime
        if isinstance(runtime, EitaaProcessRuntime):
            automatic_recovery = payload.get("automatic_recovery") is True
            if payload.get("confirm") is not True and not automatic_recovery:
                raise CompositionValidationError(
                    "Explicit confirmation is required to archive the local session.",
                    code="api_session_reset_confirmation_required",
                )
            return self._process_auth_request(
                runtime,
                "eitaa.auth.reset_local_session",
                {"automatic_recovery": automatic_recovery},
            )
        if runtime.is_account_scoped:
            return self._auth_reset_local_session_account(
                payload,
                app_session=app_session,
                request_id=request_id,
            )
        return self._auth_reset_local_session_legacy(payload)

    def _auth_reset_local_session_account(
        self,
        payload: Mapping[str, Any],
        *,
        app_session: AuthorizedAppSession | None,
        request_id: str | None,
    ) -> dict[str, Any]:
        automatic_recovery = payload.get("automatic_recovery") is True
        if payload.get("confirm") is not True and not automatic_recovery:
            actor_id, actor_role = self._account_auth_actor(app_session)
            self._runtime.audit_auth_event(
                action="eitaa.auth.session.reset.denied",
                result="denied",
                reason_code="explicit_confirmation_missing",
                actor_app_user_id=actor_id,
                actor_global_role=actor_role,
                request_id=request_id,
            )
            raise CompositionValidationError(
                "Explicit confirmation is required to archive the local session.",
                code="api_session_reset_confirmation_required",
            )
        session_file = self._core_config().session_file
        self._runtime.close_shared_core()
        with self._eitaa_lock, self._auth_lock:
            record = self._runtime.refresh_auth_record()
            if automatic_recovery and record.auth_state == "absent" and not session_file.exists():
                return {
                    "ok": True,
                    "session_present": False,
                    "archived": False,
                    "login_ready": True,
                    "recovery_mode": "automatic",
                    **self._account_auth_fields(record),
                }
            if automatic_recovery and record.auth_state != "invalid":
                actor_id, actor_role = self._account_auth_actor(app_session)
                self._runtime.audit_auth_event(
                    action="eitaa.auth.session.reset.denied",
                    result="denied",
                    reason_code="automatic_recovery_state_mismatch",
                    actor_app_user_id=actor_id,
                    actor_global_role=actor_role,
                    request_id=request_id,
                    safe_metadata={"auth_state": record.auth_state},
                )
                raise CompositionValidationError(
                    "Automatic recovery is only available for an invalid provider session.",
                    safe_context={"auth_state": record.auth_state},
                    code="api_session_automatic_recovery_not_allowed",
                )
            had_challenge = self._auth_challenge is not None
            self._close_auth_attempt()
            reset_reason = (
                "automatic_invalid_session_recovery"
                if automatic_recovery
                else "operator_local_session_reset"
            )
            if not session_file.exists():
                if record.auth_state != "absent" or had_challenge:
                    record = self._transition_account_auth(
                        record,
                        new_state="absent",
                        increment_generation=True,
                        reason_code=reset_reason,
                        action="eitaa.auth.session.reset",
                        app_session=app_session,
                        request_id=request_id,
                        safe_metadata={
                            "archive_created": False,
                            "session_file_present": False,
                        },
                    )
                else:
                    actor_id, actor_role = self._account_auth_actor(app_session)
                    self._runtime.audit_auth_event(
                        action="eitaa.auth.session.reset",
                        result="succeeded",
                        reason_code="local_session_already_absent",
                        actor_app_user_id=actor_id,
                        actor_global_role=actor_role,
                        request_id=request_id,
                        safe_metadata={
                            "archive_created": False,
                            "session_file_present": False,
                        },
                    )
                return {
                    "ok": True,
                    "session_present": False,
                    "archived": False,
                    "login_ready": True,
                    "recovery_mode": (
                        "automatic" if automatic_recovery else "confirmed"
                    ),
                    **self._account_auth_fields(record),
                }
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
            archive = session_file.with_name(
                f"{session_file.name}.invalid.{timestamp}.bak"
            )
            try:
                os.replace(session_file, archive)
            except OSError as exc:
                self._audit_account_auth_failure(
                    action="eitaa.auth.session.reset.failed",
                    reason_code="local_session_archive_failed",
                    app_session=app_session,
                    request_id=request_id,
                    safe_metadata={"error_type": type(exc).__name__},
                )
                raise AuthenticationRuntimeError(
                    "بایگانی نشست محلی ناموفق بود. برنامه را ببندید و دوباره تلاش کنید.",
                    safe_context={"error_type": type(exc).__name__},
                    code="auth_session_archive_failed",
                ) from exc
            if session_file.exists():
                raise AuthenticationRuntimeError(
                    "فایل نشست پس از بایگانی همچنان در مسیر فعال باقی مانده است.",
                    safe_context={"session_file_present": True},
                    code="auth_session_archive_verification_failed",
                )
            record = self._transition_account_auth(
                record,
                new_state="absent",
                increment_generation=True,
                reason_code=reset_reason,
                action="eitaa.auth.session.reset",
                app_session=app_session,
                request_id=request_id,
                safe_metadata={
                    "archive_created": True,
                    "session_file_present": False,
                },
            )
        return {
            "ok": True,
            "session_present": False,
            "archived": True,
            "login_ready": True,
            "recovery_mode": "automatic" if automatic_recovery else "confirmed",
            **({} if automatic_recovery else {"archive_name": archive.name}),
            **self._account_auth_fields(record),
        }

    def _auth_reset_local_session_legacy(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Archive an unusable local session and return to a clean login gate.

        This does not call remote logout because the current token may already
        be invalid and the user explicitly chose local recovery. The archived
        file is retained beside the original for manual recovery.
        """
        if payload.get("confirm") is not True:
            raise CompositionValidationError(
                "Explicit confirmation is required to archive the local session.",
                code="api_session_reset_confirmation_required",
            )
        session_file = self._core_config().session_file
        self._runtime.close_shared_core()
        with self._eitaa_lock, self._auth_lock:
            if self._auth_runtime is not None:
                self._auth_runtime.close()
            self._auth_runtime = None
            self._auth_challenge = None
            if not session_file.exists():
                return {"ok": True, "session_present": False, "archived": False, "login_ready": True}
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
            archive = session_file.with_name(f"{session_file.name}.invalid.{timestamp}.bak")
            try:
                os.replace(session_file, archive)
            except OSError as exc:
                raise AuthenticationRuntimeError(
                    "بایگانی نشست محلی ناموفق بود. برنامه را ببندید و دوباره تلاش کنید.",
                    safe_context={"error_type": type(exc).__name__},
                    code="auth_session_archive_failed",
                ) from exc
            if session_file.exists():
                raise AuthenticationRuntimeError(
                    "فایل نشست پس از بایگانی همچنان در مسیر فعال باقی مانده است.",
                    safe_context={"session_file_present": True},
                    code="auth_session_archive_verification_failed",
                )
        return {
            "ok": True,
            "session_present": False,
            "archived": True,
            "archive_name": archive.name,
            "login_ready": True,
        }

    def _auth_recover_phone_identity(
        self,
        payload: Mapping[str, Any],
        *,
        app_session: AuthorizedAppSession | None,
        request_id: str | None,
    ) -> dict[str, Any]:
        """Recover one migrated identity whose old CurrentUser DPAPI key is unavailable."""

        if not self._runtime.is_account_scoped:
            raise CompositionValidationError(
                "Protected phone identity recovery requires an account-scoped runtime.",
                code="api_phone_identity_recovery_account_scope_required",
            )
        if payload.get("confirm") is not True:
            raise CompositionValidationError(
                "Explicit confirmation is required to recover the protected phone identity.",
                code="api_phone_identity_recovery_confirmation_required",
            )
        session = (
            self._require_authorized_session(app_session)
            if self.app_user_auth_enabled
            else None
        )
        if session is not None and session.principal.global_role != "admin":
            raise CoordinatorAuthorizationError(
                "Only an administrator can recover the protected phone identity.",
                code="app_auth_admin_required",
            )
        phone = validate_canonical_e164(str(payload.get("phone") or "").strip())
        account_id = str(self._runtime.ownership.messenger_account_id or "")
        coordinator = self._require_coordinator()
        record = self._runtime.refresh_auth_record()
        session_file = self._account_session_file()
        if session_file.exists() or record.auth_state != "absent":
            raise CompositionValidationError(
                "Archive the active provider session before recovering the phone identity.",
                safe_context={
                    "session_file_present": session_file.exists(),
                    "auth_state": record.auth_state,
                },
                code="api_phone_identity_recovery_session_present",
            )
        current_identity = coordinator.messenger_account_phone_identity(account_id)
        if not current_identity.protected_phone.display_hint.endswith(phone[-2:]):
            self._runtime.audit_auth_event(
                action="eitaa.auth.phone_identity.recovery_denied",
                result="denied",
                reason_code="display_hint_mismatch",
                actor_app_user_id=(session.principal.app_user_id if session else None),
                actor_global_role=(session.principal.global_role if session else None),
                request_id=request_id,
                safe_metadata={"display_hint_match": False},
            )
            raise CompositionValidationError(
                "The supplied phone does not match the selected account hint.",
                code="api_phone_identity_recovery_hint_mismatch",
            )
        try:
            resolved = self._runtime.resolve_login_phone(phone)
        except BridgeError as exc:
            if exc.code not in {
                "phone_unprotection_failed",
                "eitaa_process_auth_ipc_required",
            }:
                raise
        else:
            if not hmac.compare_digest(resolved, phone):
                raise CompositionValidationError(
                    "The supplied phone does not own the selected MessengerAccount.",
                    code="eitaa_account_phone_mismatch",
                )
            return {
                "ok": True,
                "recovered": False,
                "recovery_required": False,
                "login_ready": True,
            }

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        coordinator_root = self.base_directory / "data" / "coordinator"
        recovery_root = coordinator_root / "identity-recovery"
        recovery_root.mkdir(parents=True, exist_ok=True)
        key_file = coordinator_root / "identity.key.dpapi"
        key_backup = recovery_root / f"identity.key.dpapi.{timestamp}.bak"
        database_backup = recovery_root / f"coordinator.{timestamp}.bak.sqlite3"
        temporary_key = coordinator_root / f"identity.key.dpapi.next.{timestamp}"
        restore_key = coordinator_root / f"identity.key.dpapi.restore.{timestamp}"
        if any(path.exists() for path in (key_backup, database_backup, temporary_key, restore_key)):
            raise AuthenticationRuntimeError(
                "A protected identity recovery artifact already exists.",
                code="phone_identity_recovery_artifact_collision",
            )

        with self._eitaa_lock, self._auth_lock:
            key_swapped = False
            database_updated = False
            try:
                shutil.copy2(key_file, key_backup)
                source_uri = f"{coordinator.path.as_uri()}?mode=ro"
                with sqlite3.connect(source_uri, uri=True, timeout=5.0) as source:
                    with sqlite3.connect(database_backup, timeout=5.0) as destination:
                        source.backup(destination)
                replacement_protector = WindowsDpapiPhoneProtector(temporary_key)
                protected_phone = replacement_protector.protect(phone)
                if not hmac.compare_digest(
                    replacement_protector.reveal(protected_phone),
                    phone,
                ):
                    raise AuthenticationRuntimeError(
                        "The replacement protected identity did not pass verification.",
                        code="phone_identity_recovery_verification_failed",
                    )
                os.replace(temporary_key, key_file)
                key_swapped = True
                updated = coordinator.replace_messenger_account_phone_identity(
                    account_id,
                    protected_phone=protected_phone,
                    actor_app_user_id=(
                        session.principal.app_user_id if session else None
                    ),
                    actor_global_role=(
                        session.principal.global_role if session else None
                    ),
                    request_id=request_id,
                )
                database_updated = True
                verified_phone = WindowsDpapiPhoneProtector(key_file).reveal(
                    updated.protected_phone
                )
                if not hmac.compare_digest(verified_phone, phone):
                    raise AuthenticationRuntimeError(
                        "The recovered protected identity did not pass final verification.",
                        code="phone_identity_recovery_final_verification_failed",
                    )
            except Exception as exc:
                rollback_error: Exception | None = None
                try:
                    if database_updated:
                        backup_uri = f"{database_backup.as_uri()}?mode=ro"
                        with sqlite3.connect(backup_uri, uri=True, timeout=5.0) as source:
                            with sqlite3.connect(coordinator.path, timeout=5.0) as destination:
                                source.backup(destination)
                    if key_swapped:
                        shutil.copy2(key_backup, restore_key)
                        os.replace(restore_key, key_file)
                except (OSError, sqlite3.Error) as rollback_exc:
                    rollback_error = rollback_exc
                if rollback_error is not None:
                    raise AuthenticationRuntimeError(
                        "Protected phone identity recovery failed and automatic rollback was incomplete.",
                        safe_context={
                            "error_type": type(exc).__name__,
                            "rollback_error_type": type(rollback_error).__name__,
                            "key_backup": key_backup.name,
                            "database_backup": database_backup.name,
                        },
                        code="phone_identity_recovery_rollback_incomplete",
                    ) from exc
                if isinstance(exc, BridgeError):
                    raise
                if isinstance(exc, (OSError, sqlite3.Error)):
                    raise AuthenticationRuntimeError(
                        "The protected phone identity recovery failed.",
                        safe_context={"error_type": type(exc).__name__},
                        code="phone_identity_recovery_failed",
                    ) from exc
                raise
            finally:
                temporary_key.unlink(missing_ok=True)
                restore_key.unlink(missing_ok=True)
                phone = ""
                if "verified_phone" in locals():
                    verified_phone = ""

        return {
            "ok": True,
            "recovered": True,
            "recovery_required": False,
            "login_ready": True,
            "backups": {
                "key": key_backup.name,
                "database": database_backup.name,
            },
        }

    def _auth_request_code(
        self,
        payload: Mapping[str, Any],
        *,
        app_session: AuthorizedAppSession | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        runtime = self._runtime
        if isinstance(runtime, EitaaProcessRuntime):
            supplied = payload.get("phone")
            return self._process_auth_request(
                runtime,
                "eitaa.auth.request_code",
                {
                    "phone": (
                        supplied
                        if isinstance(supplied, str)
                        else None
                    )
                },
            )
        if runtime.is_account_scoped:
            return self._auth_request_code_account(
                payload,
                app_session=app_session,
                request_id=request_id,
            )
        return self._auth_request_code_legacy(payload)

    def _auth_request_code_account(
        self,
        payload: Mapping[str, Any],
        *,
        app_session: AuthorizedAppSession | None,
        request_id: str | None,
    ) -> dict[str, Any]:
        supplied_phone = payload.get("phone")
        session_file = self._core_config().session_file
        with self._eitaa_lock, self._auth_lock:
            record = self._runtime.refresh_auth_record()
            if session_file.is_file():
                actor_id, actor_role = self._account_auth_actor(app_session)
                self._runtime.audit_auth_event(
                    action="eitaa.auth.request_code.denied",
                    result="denied",
                    reason_code="active_session_reset_required",
                    actor_app_user_id=actor_id,
                    actor_global_role=actor_role,
                    request_id=request_id,
                    safe_metadata={"session_file_present": True},
                )
                raise CompositionValidationError(
                    "Archive or log out the active account session before starting a fresh login.",
                    code="api_auth_session_reset_required",
                )
            if record.auth_state == "challenge_pending":
                self._close_auth_attempt()
                record = self._transition_account_auth(
                    record,
                    new_state="expired",
                    increment_generation=False,
                    reason_code="challenge_replaced",
                    action="eitaa.auth.challenge.expired",
                    app_session=app_session,
                    request_id=request_id,
                    safe_metadata={"challenge_stage": "unknown"},
                )
            else:
                self._close_auth_attempt()
            try:
                phone = self._runtime.resolve_login_phone(
                    str(supplied_phone).strip()
                    if supplied_phone is not None and str(supplied_phone).strip()
                    else None
                )
            except BridgeError as exc:
                self._audit_account_auth_failure(
                    action="eitaa.auth.request_code.denied",
                    reason_code=(
                        "account_phone_mismatch"
                        if exc.code == "eitaa_account_phone_mismatch"
                        else "account_phone_resolution_failed"
                    ),
                    app_session=app_session,
                    request_id=request_id,
                    safe_metadata={"error_type": type(exc).__name__},
                    result=(
                        "denied"
                        if exc.code == "eitaa_account_phone_mismatch"
                        else "failed"
                    ),
                )
                raise
            try:
                self._auth_runtime = EitaaAuth.open(self._core_config())
                provider_challenge = self._auth_runtime.auth.request_code(phone)
                provider_summary = provider_challenge.safe_summary()
                record = self._transition_account_auth(
                    record,
                    new_state="challenge_pending",
                    increment_generation=True,
                    reason_code="login_challenge_issued",
                    action="eitaa.auth.request_code.succeeded",
                    app_session=app_session,
                    request_id=request_id,
                    safe_metadata={
                        "delivery_type": str(
                            provider_summary.get("delivery_type") or "unknown"
                        ),
                        "timeout_seconds": provider_summary.get("timeout_seconds"),
                    },
                )
                self._auth_challenge = AccountAuthChallenge.for_code(
                    messenger_account_id=record.messenger_account_id,
                    session_generation=record.session_generation,
                    provider_challenge=provider_challenge,
                )
                self._runtime_logger.emit(
                    "auth_challenge_created",
                    fields={
                        "session_generation": record.session_generation,
                        "challenge_stage": "code",
                        "expires_at": self._auth_challenge.expires_at.isoformat(
                            timespec="milliseconds"
                        ),
                    },
                )
                return {
                    "ok": True,
                    "step": "code",
                    "challenge": self._auth_challenge.safe_summary(),
                    **self._account_auth_fields(record),
                }
            except BridgeError:
                self._close_auth_attempt()
                raise
            except NetworkError as exc:
                self._close_auth_attempt()
                self._audit_account_auth_failure(
                    action="eitaa.auth.request_code.failed",
                    reason_code="provider_network_unreachable",
                    app_session=app_session,
                    request_id=request_id,
                    safe_metadata={"error_type": type(exc).__name__},
                )
                raise AuthenticationRuntimeError(
                    "ارتباط سرویس محلی با سرور ایتا برقرار نشد. اتصال اینترنت یا دسترسی شبکهٔ سرویس را بررسی و دوباره تلاش کنید.",
                    safe_context={"error_type": type(exc).__name__},
                    code="auth_provider_network_unreachable",
                ) from exc
            except Exception as exc:
                self._close_auth_attempt()
                self._audit_account_auth_failure(
                    action="eitaa.auth.request_code.failed",
                    reason_code="provider_request_failed",
                    app_session=app_session,
                    request_id=request_id,
                    safe_metadata={"error_type": type(exc).__name__},
                )
                raise AuthenticationRuntimeError(
                    "راه‌اندازی ورود ایتا ناموفق بود. سرویس محلی را دوباره راه‌اندازی و مجدداً تلاش کنید.",
                    safe_context={"error_type": type(exc).__name__},
                    code="auth_request_code_failed",
                ) from exc

    def _auth_request_code_legacy(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        phone = str(payload.get("phone") or "").strip()
        if not phone:
            raise CompositionValidationError("phone is required.", code="api_phone_required")
        with self._eitaa_lock, self._auth_lock:
            try:
                if self._auth_runtime is not None:
                    self._auth_runtime.close()
                self._auth_challenge = None
                self._auth_runtime = EitaaAuth.open(self._core_config())
                provider_challenge = self._auth_runtime.auth.request_code(phone)
                self._auth_challenge = LegacyAuthChallenge.for_code(
                    provider_challenge=provider_challenge,
                )
                self._runtime_logger.emit(
                    "auth_challenge_created",
                    fields={
                        "runtime_scope": "legacy",
                        "challenge_stage": "code",
                    },
                )
                return {
                    "ok": True,
                    "step": "code",
                    "challenge": self._auth_challenge.safe_summary(),
                }
            except BridgeError:
                self._close_auth_attempt()
                raise
            except NetworkError as exc:
                if self._auth_runtime is not None:
                    self._auth_runtime.close()
                self._auth_runtime = None
                self._auth_challenge = None
                raise AuthenticationRuntimeError(
                    "ارتباط سرویس محلی با سرور ایتا برقرار نشد. اتصال اینترنت یا دسترسی شبکهٔ سرویس را بررسی و دوباره تلاش کنید.",
                    safe_context={"error_type": type(exc).__name__},
                    code="auth_provider_network_unreachable",
                ) from exc
            except Exception as exc:
                if self._auth_runtime is not None:
                    self._auth_runtime.close()
                self._auth_runtime = None
                self._auth_challenge = None
                raise AuthenticationRuntimeError(
                    "راه‌اندازی ورود ایتا ناموفق بود. سرویس محلی را دوباره راه‌اندازی و مجدداً تلاش کنید.",
                    safe_context={"error_type": type(exc).__name__},
                    code="auth_request_code_failed",
                ) from exc

    def _require_account_challenge(
        self,
        payload: Mapping[str, Any],
        *,
        expected_stage: str,
        app_session: AuthorizedAppSession | None,
        request_id: str | None,
    ) -> tuple[AccountAuthChallenge, Any]:
        challenge_id = str(payload.get("challenge_id") or "").strip()
        if not challenge_id:
            raise CompositionValidationError(
                "challenge_id is required.",
                code="api_auth_challenge_id_required",
            )
        record = self._runtime.refresh_auth_record()
        challenge = self._auth_challenge
        if (
            not isinstance(challenge, AccountAuthChallenge)
            or self._auth_runtime is None
        ):
            missing_stage = (
                challenge.stage
                if isinstance(challenge, AccountAuthChallenge)
                else "unknown"
            )
            self._close_auth_attempt()
            if record.auth_state == "challenge_pending":
                self._transition_account_auth(
                    record,
                    new_state="expired",
                    increment_generation=False,
                    reason_code="challenge_runtime_missing",
                    action="eitaa.auth.challenge.expired",
                    app_session=app_session,
                    request_id=request_id,
                    safe_metadata={"challenge_stage": missing_stage},
                )
            raise CompositionValidationError(
                "No account login challenge is pending.",
                code="api_auth_challenge_missing",
            )
        if challenge.is_expired():
            self._close_auth_attempt()
            if (
                record.auth_state == "challenge_pending"
                and record.session_generation == challenge.session_generation
            ):
                self._transition_account_auth(
                    record,
                    new_state="expired",
                    increment_generation=False,
                    reason_code="challenge_expired",
                    action="eitaa.auth.challenge.expired",
                    app_session=app_session,
                    request_id=request_id,
                    safe_metadata={"challenge_stage": challenge.stage},
                )
            raise CompositionValidationError(
                "The account login challenge expired. Request a new code.",
                code="api_auth_challenge_expired",
            )
        if not challenge.matches(
            challenge_id=challenge_id,
            messenger_account_id=record.messenger_account_id,
            session_generation=record.session_generation,
            stage=expected_stage,
        ) or record.auth_state != "challenge_pending":
            actor_id, actor_role = self._account_auth_actor(app_session)
            self._runtime.audit_auth_event(
                action="eitaa.auth.challenge.denied",
                result="denied",
                reason_code="challenge_context_mismatch",
                actor_app_user_id=actor_id,
                actor_global_role=actor_role,
                request_id=request_id,
                safe_metadata={"challenge_stage": expected_stage},
            )
            raise CompositionValidationError(
                "The account login challenge does not match this session.",
                code="api_auth_challenge_mismatch",
            )
        return challenge, record

    def _require_legacy_challenge(
        self,
        payload: Mapping[str, Any],
        *,
        expected_stage: str,
    ) -> LegacyAuthChallenge:
        challenge_id = str(payload.get("challenge_id") or "").strip()
        if not challenge_id:
            raise CompositionValidationError(
                "challenge_id is required.",
                code="api_auth_challenge_id_required",
            )
        challenge = self._auth_challenge
        if (
            not isinstance(challenge, LegacyAuthChallenge)
            or self._auth_runtime is None
        ):
            raise CompositionValidationError(
                "No single-session login challenge is pending.",
                code="api_auth_challenge_missing",
            )
        if challenge.is_expired():
            expired_stage = challenge.stage
            self._close_auth_attempt()
            self._runtime_logger.emit(
                "auth_challenge_expired",
                level="warning",
                result="rejected",
                reason_code="challenge_expired",
                fields={
                    "runtime_scope": "legacy",
                    "challenge_stage": expired_stage,
                },
            )
            raise CompositionValidationError(
                "The single-session login challenge expired. Request a new code.",
                code="api_auth_challenge_expired",
            )
        if not challenge.matches(
            challenge_id=challenge_id,
            stage=expected_stage,
        ):
            self._runtime_logger.emit(
                "auth_challenge_denied",
                level="warning",
                result="rejected",
                reason_code="challenge_context_mismatch",
                fields={
                    "runtime_scope": "legacy",
                    "expected_stage": expected_stage,
                    "actual_stage": challenge.stage,
                },
            )
            raise CompositionValidationError(
                "The single-session login challenge does not match this flow.",
                code="api_auth_challenge_mismatch",
            )
        return challenge

    def _auth_submit_code(
        self,
        payload: Mapping[str, Any],
        *,
        app_session: AuthorizedAppSession | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        runtime = self._runtime
        if isinstance(runtime, EitaaProcessRuntime):
            return self._process_auth_request(
                runtime,
                "eitaa.auth.submit_code",
                {
                    "challenge_id": str(payload.get("challenge_id") or ""),
                    "code": str(payload.get("code") or ""),
                },
            )
        if runtime.is_account_scoped:
            return self._auth_submit_code_account(
                payload,
                app_session=app_session,
                request_id=request_id,
            )
        return self._auth_submit_code_legacy(payload)

    def _auth_submit_code_account(
        self,
        payload: Mapping[str, Any],
        *,
        app_session: AuthorizedAppSession | None,
        request_id: str | None,
    ) -> dict[str, Any]:
        code = _normalize_login_code(payload.get("code"))
        with self._eitaa_lock, self._auth_lock:
            challenge, record = self._require_account_challenge(
                payload,
                expected_stage="code",
                app_session=app_session,
                request_id=request_id,
            )
            if not re.fullmatch(r"[0-9A-Za-z-]{2,32}", code):
                raise CompositionValidationError(
                    "کد ورود باید فقط شامل رقم یا حروف انگلیسی باشد.",
                    code="auth_code_format_invalid",
                )
            try:
                result = self._auth_runtime.auth.submit_code(
                    challenge.provider_challenge,
                    code,
                )
            except BridgeError:
                raise
            except RpcError as exc:
                error_kind, reason_code, error_code, message = (
                    _provider_login_code_failure(exc)
                )
                self._audit_account_auth_failure(
                    action="eitaa.auth.submit_code.failed",
                    reason_code=reason_code,
                    app_session=app_session,
                    request_id=request_id,
                    safe_metadata={
                        "error_type": type(exc).__name__,
                        "challenge_stage": "code",
                        "provider_error_kind": error_kind,
                    },
                )
                raise AuthenticationRuntimeError(
                    message,
                    safe_context={
                        "error_type": type(exc).__name__,
                        "provider_error_kind": error_kind,
                    },
                    code=error_code,
                ) from exc
            except Exception as exc:
                self._audit_account_auth_failure(
                    action="eitaa.auth.submit_code.failed",
                    reason_code="provider_code_submission_failed",
                    app_session=app_session,
                    request_id=request_id,
                    safe_metadata={
                        "error_type": type(exc).__name__,
                        "challenge_stage": "code",
                    },
                )
                raise AuthenticationRuntimeError(
                    "بررسی کد ورود ایتا ناموفق بود. دوباره تلاش کنید.",
                    safe_context={"error_type": type(exc).__name__},
                    code="auth_submit_code_failed",
                ) from exc
            if result.completed:
                if not self._core_config().session_file.is_file():
                    self._audit_account_auth_failure(
                        action="eitaa.auth.login.failed",
                        reason_code="provider_session_file_missing",
                        app_session=app_session,
                        request_id=request_id,
                        safe_metadata={"session_file_present": False},
                    )
                    self._close_auth_attempt()
                    raise AuthenticationRuntimeError(
                        "ورود ایتا کامل شد اما فایل نشست تأیید نشد.",
                        code="auth_session_file_missing_after_login",
                    )
                try:
                    record = self._transition_account_auth(
                        record,
                        new_state="authenticated",
                        increment_generation=False,
                        reason_code="native_login_completed",
                        action="eitaa.auth.login.completed",
                        app_session=app_session,
                        request_id=request_id,
                        mark_validated=True,
                        safe_metadata={"challenge_stage": "code"},
                    )
                except BridgeError:
                    self._archive_uncoordinated_session()
                    self._close_auth_attempt()
                    raise
                self._close_auth_attempt()
                self._runtime.close_shared_core()
                return {
                    "ok": True,
                    "step": "completed",
                    **result.safe_summary(),
                    **self._account_auth_fields(record),
                }
            if result.password_required:
                self._auth_challenge = challenge.for_password()
                actor_id, actor_role = self._account_auth_actor(app_session)
                self._runtime.audit_auth_event(
                    action="eitaa.auth.submit_code.password_required",
                    result="succeeded",
                    reason_code="second_factor_required",
                    actor_app_user_id=actor_id,
                    actor_global_role=actor_role,
                    request_id=request_id,
                    safe_metadata={"challenge_stage": "password"},
                )
                self._runtime_logger.emit(
                    "auth_challenge_advanced",
                    fields={
                        "session_generation": record.session_generation,
                        "challenge_stage": "password",
                    },
                )
                return {
                    "ok": True,
                    "step": "password",
                    **result.safe_summary(),
                    "challenge": self._auth_challenge.safe_summary(),
                    **self._account_auth_fields(record),
                }
            self._audit_account_auth_failure(
                action="eitaa.auth.submit_code.failed",
                reason_code="provider_result_incomplete",
                app_session=app_session,
                request_id=request_id,
                safe_metadata={"challenge_stage": "code"},
            )
            raise AuthenticationRuntimeError(
                "پاسخ ورود ایتا وضعیت قابل استفاده‌ای نداشت.",
                code="auth_submit_code_result_invalid",
            )

    def _auth_submit_code_legacy(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        code = _normalize_login_code(payload.get("code"))
        with self._eitaa_lock, self._auth_lock:
            challenge = self._require_legacy_challenge(
                payload,
                expected_stage="code",
            )
            if not re.fullmatch(r"[0-9A-Za-z-]{2,32}", code):
                raise CompositionValidationError(
                    "کد ورود باید فقط شامل رقم یا حروف انگلیسی باشد.",
                    code="auth_code_format_invalid",
                )
            try:
                result = self._auth_runtime.auth.submit_code(
                    challenge.provider_challenge,
                    code,
                )
            except BridgeError:
                raise
            except RpcError as exc:
                error_kind, _reason_code, error_code, message = (
                    _provider_login_code_failure(exc)
                )
                raise AuthenticationRuntimeError(
                    message,
                    safe_context={
                        "error_type": type(exc).__name__,
                        "provider_error_kind": error_kind,
                    },
                    code=error_code,
                ) from exc
            except Exception as exc:
                raise AuthenticationRuntimeError(
                    "بررسی کد ورود ایتا ناموفق بود. دوباره تلاش کنید.",
                    safe_context={"error_type": type(exc).__name__},
                    code="auth_submit_code_failed",
                ) from exc
            if result.completed:
                self._auth_runtime.close()
                self._auth_runtime = None
                self._auth_challenge = None
                self._runtime.close_shared_core()
                return {"ok": True, "step": "completed", **result.safe_summary()}
            if result.password_required:
                self._auth_challenge = challenge.for_password()
                self._runtime_logger.emit(
                    "auth_challenge_advanced",
                    fields={
                        "runtime_scope": "legacy",
                        "challenge_stage": "password",
                    },
                )
                return {
                    "ok": True,
                    "step": "password",
                    **result.safe_summary(),
                    "challenge": self._auth_challenge.safe_summary(),
                }
            raise AuthenticationRuntimeError(
                "پاسخ ورود ایتا وضعیت قابل استفاده‌ای نداشت.",
                code="auth_submit_code_result_invalid",
            )

    def _auth_submit_password(
        self,
        payload: Mapping[str, Any],
        *,
        app_session: AuthorizedAppSession | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        runtime = self._runtime
        if isinstance(runtime, EitaaProcessRuntime):
            password = payload.get("password")
            if not isinstance(password, str) or not password:
                raise CompositionValidationError(
                    "password is required.",
                    code="api_password_required",
                )
            return self._process_auth_request(
                runtime,
                "eitaa.auth.submit_password",
                {
                    "challenge_id": str(payload.get("challenge_id") or ""),
                    "credential": password,
                },
            )
        if runtime.is_account_scoped:
            return self._auth_submit_password_account(
                payload,
                app_session=app_session,
                request_id=request_id,
            )
        return self._auth_submit_password_legacy(payload)

    def _auth_submit_password_account(
        self,
        payload: Mapping[str, Any],
        *,
        app_session: AuthorizedAppSession | None,
        request_id: str | None,
    ) -> dict[str, Any]:
        password = payload.get("password")
        if not isinstance(password, str) or not password:
            raise CompositionValidationError(
                "password is required.",
                code="api_password_required",
            )
        with self._eitaa_lock, self._auth_lock:
            _, record = self._require_account_challenge(
                payload,
                expected_stage="password",
                app_session=app_session,
                request_id=request_id,
            )
            try:
                result = self._auth_runtime.auth.submit_password(password)
            except BridgeError:
                raise
            except Exception as exc:
                self._audit_account_auth_failure(
                    action="eitaa.auth.submit_password.failed",
                    reason_code="provider_password_submission_failed",
                    app_session=app_session,
                    request_id=request_id,
                    safe_metadata={
                        "error_type": type(exc).__name__,
                        "challenge_stage": "password",
                    },
                )
                raise AuthenticationRuntimeError(
                    "بررسی رمز دوم ایتا ناموفق بود. دوباره تلاش کنید.",
                    safe_context={"error_type": type(exc).__name__},
                    code="auth_submit_password_failed",
                ) from exc
            if not result.completed or not self._core_config().session_file.is_file():
                self._audit_account_auth_failure(
                    action="eitaa.auth.login.failed",
                    reason_code="provider_session_file_missing",
                    app_session=app_session,
                    request_id=request_id,
                    safe_metadata={
                        "challenge_stage": "password",
                        "session_file_present": self._core_config().session_file.is_file(),
                    },
                )
                self._close_auth_attempt()
                raise AuthenticationRuntimeError(
                    "ورود دومرحله‌ای کامل شد اما فایل نشست تأیید نشد.",
                    code="auth_session_file_missing_after_login",
                )
            try:
                record = self._transition_account_auth(
                    record,
                    new_state="authenticated",
                    increment_generation=False,
                    reason_code="native_second_factor_completed",
                    action="eitaa.auth.login.completed",
                    app_session=app_session,
                    request_id=request_id,
                    mark_validated=True,
                    safe_metadata={"challenge_stage": "password"},
                )
            except BridgeError:
                self._archive_uncoordinated_session()
                self._close_auth_attempt()
                raise
            self._close_auth_attempt()
            self._runtime.close_shared_core()
            return {
                "ok": True,
                "step": "completed",
                **result.safe_summary(),
                **self._account_auth_fields(record),
            }

    def _auth_submit_password_legacy(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        password = payload.get("password")
        if not isinstance(password, str) or not password:
            raise CompositionValidationError("password is required.", code="api_password_required")
        with self._eitaa_lock, self._auth_lock:
            self._require_legacy_challenge(
                payload,
                expected_stage="password",
            )
            try:
                result = self._auth_runtime.auth.submit_password(password)
            except BridgeError:
                raise
            except Exception as exc:
                raise AuthenticationRuntimeError(
                    "بررسی رمز دوم ایتا ناموفق بود. دوباره تلاش کنید.",
                    safe_context={"error_type": type(exc).__name__},
                    code="auth_submit_password_failed",
                ) from exc
            if not result.completed:
                raise AuthenticationRuntimeError(
                    "پاسخ ورود دومرحله‌ای ایتا کامل نبود.",
                    code="auth_submit_password_result_invalid",
                )
            self._auth_runtime.close()
            self._auth_runtime = None
            self._auth_challenge = None
            self._runtime.close_shared_core()
            return {"ok": True, "step": "completed", **result.safe_summary()}

    def _auth_logout(
        self,
        *,
        app_session: AuthorizedAppSession | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        runtime = self._runtime
        if isinstance(runtime, EitaaProcessRuntime):
            return self._process_auth_request(
                runtime,
                "eitaa.auth.logout",
                {},
            )
        if runtime.is_account_scoped:
            return self._auth_logout_account(
                app_session=app_session,
                request_id=request_id,
            )
        return self._auth_logout_legacy()

    def _auth_logout_account(
        self,
        *,
        app_session: AuthorizedAppSession | None,
        request_id: str | None,
    ) -> dict[str, Any]:
        session_file = self._core_config().session_file
        with self._eitaa_lock, self._auth_lock:
            record = self._runtime.refresh_auth_record()
            if not session_file.is_file():
                had_challenge = self._auth_challenge is not None
                self._close_auth_attempt()
                if record.auth_state not in {"absent", "revoked"} or had_challenge:
                    record = self._transition_account_auth(
                        record,
                        new_state="revoked",
                        increment_generation=True,
                        reason_code="logout_without_active_session",
                        action="eitaa.auth.logout.completed",
                        app_session=app_session,
                        request_id=request_id,
                        safe_metadata={
                            "remote_ok": False,
                            "archive_created": False,
                            "session_file_present": False,
                        },
                    )
                else:
                    actor_id, actor_role = self._account_auth_actor(app_session)
                    self._runtime.audit_auth_event(
                        action="eitaa.auth.logout.completed",
                        result="succeeded",
                        reason_code=(
                            "local_session_already_revoked"
                            if record.auth_state == "revoked"
                            else "local_session_already_absent"
                        ),
                        actor_app_user_id=actor_id,
                        actor_global_role=actor_role,
                        request_id=request_id,
                        safe_metadata={
                            "remote_ok": False,
                            "archive_created": False,
                            "session_file_present": False,
                        },
                    )
                return {
                    "ok": True,
                    "logout": {
                        "remote_ok": False,
                        "local_session_archived": False,
                    },
                    "session_present": False,
                    "login_ready": True,
                    **self._account_auth_fields(record),
                }

            if record.auth_state in {"invalid", "revoked"}:
                self._runtime.close_shared_core()
                archive_name = self._archive_account_session_file("invalid")
                self._close_auth_attempt()
                record = self._transition_account_auth(
                    record,
                    new_state="revoked",
                    increment_generation=True,
                    reason_code="invalid_session_revoked_locally",
                    action="eitaa.auth.logout.completed",
                    app_session=app_session,
                    request_id=request_id,
                    safe_metadata={
                        "remote_ok": False,
                        "archive_created": archive_name is not None,
                        "session_file_present": False,
                    },
                )
                return {
                    "ok": True,
                    "logout": {
                        "remote_ok": False,
                        "remote_session_already_invalid": True,
                        "local_session_archived": archive_name is not None,
                        "archive_name": archive_name,
                    },
                    "session_present": False,
                    "login_ready": True,
                    **self._account_auth_fields(record),
                }

            try:
                with self._open_bridge(
                    self.config_path,
                    env_file=self.env_file,
                    open_core=True,
                ) as bridge:
                    result = bridge.core.account.logout(archive_local_session=True)
                    summary = result.safe_summary()
            except Exception as exc:
                if not self._is_invalid_session_error(exc):
                    self._audit_account_auth_failure(
                        action="eitaa.auth.logout.failed",
                        reason_code="provider_logout_failed",
                        app_session=app_session,
                        request_id=request_id,
                        safe_metadata={"error_type": type(exc).__name__},
                    )
                    raise
                self._runtime.close_shared_core()
                archive_name = self._archive_account_session_file("invalid")
                self._close_auth_attempt()
                record = self._transition_account_auth(
                    record,
                    new_state="revoked",
                    increment_generation=True,
                    reason_code="remote_session_already_invalid",
                    action="eitaa.auth.logout.completed",
                    app_session=app_session,
                    request_id=request_id,
                    safe_metadata={
                        "remote_ok": False,
                        "archive_created": archive_name is not None,
                        "session_file_present": False,
                    },
                )
                return {
                    "ok": True,
                    "logout": {
                        "remote_ok": False,
                        "remote_session_already_invalid": True,
                        "local_session_archived": archive_name is not None,
                        "archive_name": archive_name,
                    },
                    "session_present": False,
                    "login_ready": True,
                    **self._account_auth_fields(record),
                }

            self._runtime.close_shared_core()
            archive_name = None
            archived_path = summary.get("archived_path")
            if archived_path:
                archive_name = Path(str(archived_path)).name
            if session_file.is_file():
                archive_name = self._archive_account_session_file("logout")
            self._close_auth_attempt()
            record = self._transition_account_auth(
                record,
                new_state="revoked",
                increment_generation=True,
                reason_code="remote_logout_completed",
                action="eitaa.auth.logout.completed",
                app_session=app_session,
                request_id=request_id,
                safe_metadata={
                    "remote_ok": bool(summary.get("remote_ok", True)),
                    "archive_created": archive_name is not None,
                    "session_file_present": False,
                },
            )
            return {
                "ok": True,
                "logout": {
                    "remote_ok": bool(summary.get("remote_ok", True)),
                    "local_session_archived": archive_name is not None,
                    "archive_name": archive_name,
                },
                "session_present": False,
                "login_ready": True,
                **self._account_auth_fields(record),
            }

    def _auth_logout_legacy(self) -> dict[str, Any]:
        try:
            with self._eitaa_lock, self._open_bridge(
                self.config_path, env_file=self.env_file, open_core=True
            ) as bridge:
                result = bridge.core.account.logout(archive_local_session=True)
                summary = result.safe_summary()
        except Exception as exc:
            if not self._is_invalid_session_error(exc):
                raise
            # Remote logout cannot succeed after Eitaa has already invalidated
            # the token. Preserve the unusable file as a backup and complete a
            # local logout so the user is never trapped inside the workspace.
            self._runtime.close_shared_core()
            recovery = self._auth_reset_local_session({"confirm": True})
            self._runtime_logger.emit(
                "auth_logout_local_fallback_completed",
                level="warning",
                fields={
                    "error_type": type(exc).__name__,
                    "remote_code": 401,
                    "local_session_archived": bool(recovery.get("archived")),
                },
            )
            return {
                "ok": True,
                "logout": {
                    "remote_ok": False,
                    "remote_session_already_invalid": True,
                    "local_session_archived": bool(recovery.get("archived")),
                    "archive_name": recovery.get("archive_name"),
                },
                "session_present": False,
                "login_ready": True,
            }
        self._runtime.close_shared_core()
        return {
            "ok": True,
            "logout": summary,
            "session_present": False,
            "login_ready": True,
        }

    def _sites(self) -> dict[str, Any]:
        config = BridgeConfigLoader.load(self.config_path, env_file=self.env_file)
        EnvLoader.load(config.env_file)
        sites = []
        for site in config.wordpress_sites:
            credentials_configured = bool(os.getenv(site.username_env) and os.getenv(site.application_password_env))
            sites.append(
                site.safe_summary(
                    is_default=site.site_key == config.default_site_key,
                    credentials_configured=credentials_configured,
                )
            )
        return {"ok": True, "default_site_key": config.default_site_key, "sites": sites}

    def _capabilities(self, query: Mapping[str, str]) -> dict[str, Any]:
        site_key = self._site_key(query)
        with self._eitaa_lock, self._open_bridge(
            self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
        ) as bridge:
            return {"ok": True, "capabilities": bridge.application_capabilities()}

    def _compositions(self, query: Mapping[str, str]) -> dict[str, Any]:
        site_key = self._site_key(query)
        limit = self._integer(query.get("limit", "100"), "limit", minimum=1, maximum=1000)
        with self._open_bridge(
            self.config_path, env_file=self.env_file, site_key=site_key, open_core=False
        ) as bridge:
            records = bridge.wordpress_compositions(limit=limit)
            return {
                "ok": True,
                "site_key": site_key,
                "count": len(records),
                "compositions": [
                    {
                        **item.safe_summary(),
                        "title": item.title,
                        "excerpt": item.excerpt,
                        "post_url": item.post_url,
                    }
                    for item in records
                ],
            }

    def _terms(self, query: Mapping[str, str], *, taxonomy: str) -> dict[str, Any]:
        site_key = self._site_key(query)
        per_page = self._integer(query.get("per_page", "100"), "per_page", minimum=1, maximum=100)
        search = query.get("search") or None
        with self._open_bridge(
            self.config_path, env_file=self.env_file, site_key=site_key, open_core=False
        ) as bridge:
            terms = (
                bridge.wordpress_categories(search=search, per_page=per_page)
                if taxonomy == "category"
                else bridge.wordpress_tags(search=search, per_page=per_page)
            )
            return {
                "ok": True,
                "site_key": site_key,
                "taxonomy": taxonomy,
                "count": len(terms),
                "terms": [item.safe_summary() for item in terms],
            }

    def _create_tag(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        name = str(payload.get("name") or "").strip()
        slug = str(payload.get("slug") or "").strip() or None
        if not name:
            raise CompositionValidationError("Tag name is required.", code="api_tag_name_required")
        if len(name) > 200:
            raise CompositionValidationError("Tag name is too long.", code="api_tag_name_too_long")
        with self._open_bridge(
            self.config_path, env_file=self.env_file, site_key=site_key, open_core=False
        ) as bridge:
            term = bridge.create_wordpress_tag(name=name, slug=slug)
        return {"ok": True, "site_key": site_key, "term": term.safe_summary()}

    def _wordpress_post(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        post_id = self._integer(payload.get("post_id"), "post_id", minimum=1)
        with self._open_bridge(
            self.config_path, env_file=self.env_file, site_key=site_key, open_core=False
        ) as bridge:
            post = bridge.wordpress_post(post_id)
        return {
            "ok": True,
            "site_key": site_key,
            "post": {
                **post.safe_summary(),
                "title": post.title_raw or "",
                "excerpt": post.excerpt_raw or "",
                "link": post.link,
                "status": post.status,
                "category_ids": list(post.category_ids),
                "tag_ids": list(post.tag_ids),
            },
        }

    def _dialogs_list(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        refresh_if_empty = bool(payload.get("refresh_if_empty", True))
        current = self.dialog_catalog.list()
        cache_summary: dict[str, Any] | None = {
            "loaded": False,
            "reason": "persistent_catalog_available" if current else "catalog_empty",
        }
        if not current and refresh_if_empty:
            try:
                cache_summary = self._hydrate_dialog_catalog_from_core(site_key=site_key)
            except Exception as exc:
                cache_summary = {"loaded": False, "error_type": type(exc).__name__}
            current = self.dialog_catalog.list()
        sync_summary: dict[str, Any] | None = None
        if refresh_if_empty and not current:
            # A complete 452-dialog synchronization is deliberately not run
            # inside this ordinary list request. The UI starts the explicit
            # background job so a slow server cannot block or restart the API.
            sync_summary = {"deferred": True, "reason": "explicit_background_sync_required"}
        dialogs = self.dialog_catalog.list()
        return {
            "ok": True,
            "site_key": site_key,
            "dialog_count": len(dialogs),
            "dialogs": dialogs,
            "cache": cache_summary,
            "sync": sync_summary,
        }

    def _dialogs_sync(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        page_size = self._integer(payload.get("page_size", 100), "page_size", minimum=1, maximum=100)
        max_pages = self._integer(payload.get("max_pages", 100), "max_pages", minimum=1, maximum=200)
        summary = self._sync_dialog_catalog(site_key=site_key, page_size=page_size, max_pages=max_pages)
        dialogs = self.dialog_catalog.list()
        return {
            "ok": True,
            "site_key": site_key,
            "dialog_count": len(dialogs),
            "dialogs": dialogs,
            "sync": summary,
        }

    def _dialogs_live_sync(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Merge the newest remote dialog page without replacing the catalog.

        The mobile UI calls this lightweight path periodically.  An incomplete
        page must never mark older dialogs inactive, so only the returned peers
        are upserted and the complete-snapshot finalizer remains disabled.
        """

        site_key = self._site_key(payload)

        def operation() -> dict[str, Any]:
            with self._open_bridge(
                self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
            ) as bridge:
                page = bridge.core.discovery.list_dialogs(
                    limit=100,
                    offset_date=0,
                    offset_id=0,
                    offset_peer=None,
                    exclude_pinned=False,
                )
                merged = self._merge_core_dialogs(
                    bridge,
                    page.dialogs,
                    source="remote",
                    complete=False,
                    finalize_snapshot=False,
                )
                return {
                    **merged,
                    "remote_count": len(page.dialogs),
                    "server_total_count": page.total_count,
                    "warning_codes": list(page.parse_warnings),
                    "mode": "first_page_merge",
                }

        summary = self._run_eitaa(
            priority=EitaaPriority.DIALOG_PAGE,
            kind="dialogs.live",
            callback=operation,
        )
        dialogs = self.dialog_catalog.list()
        return {
            "ok": True,
            "site_key": site_key,
            "dialog_count": len(dialogs),
            "dialogs": dialogs,
            "sync": summary,
        }

    def _dialogs_sync_start(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        page_size = self._integer(payload.get("page_size", 100), "page_size", minimum=1, maximum=100)
        max_pages = self._integer(payload.get("max_pages", 100), "max_pages", minimum=1, maximum=200)
        with self._jobs_lock:
            if self._active_dialog_sync_job:
                current = self._dialog_sync_jobs.get(self._active_dialog_sync_job)
                if current and current.get("state") in {"queued", "running"}:
                    return {"ok": True, "job": dict(current), "reused": True}
            job_id = self._persistent_job_create("dialogs.sync")
            job = {
                "job_id": job_id, "kind": "dialog_sync", "site_key": site_key,
                "state": "queued", "created_at": datetime.now(timezone.utc).isoformat(),
                "started_at": None, "completed_at": None, "result": None, "error": None,
            }
            self._dialog_sync_jobs[job_id] = job
            self._active_dialog_sync_job = job_id
        thread = threading.Thread(
            target=self._runtime_bound_target(self._run_dialog_sync_job),
            args=(job_id, site_key, page_size, max_pages),
            name=f"eitaa-dialog-sync-{job_id[:8]}", daemon=True,
        )
        thread.start()
        return {"ok": True, "job": dict(job), "reused": False}

    def _run_dialog_sync_job(self, job_id: str, site_key: str, page_size: int, max_pages: int) -> None:
        with self._jobs_lock:
            job = self._dialog_sync_jobs[job_id]
            job["state"] = "running"
            job["started_at"] = datetime.now(timezone.utc).isoformat()
        try:
            self._persistent_job_begin(job_id)
            summary = self._sync_dialog_catalog(site_key=site_key, page_size=page_size, max_pages=max_pages)
            dialogs = self.dialog_catalog.list()
            result = {"site_key": site_key, "dialog_count": len(dialogs), "dialogs": dialogs, "sync": summary}
            with self._jobs_lock:
                job = self._dialog_sync_jobs[job_id]
                job["state"] = "completed"
                job["result"] = result
                job["completed_at"] = datetime.now(timezone.utc).isoformat()
            self._persistent_job_finish(job_id, state="completed")
            self._runtime_logger.emit(
                "dialog_sync_completed",
                fields={
                    "job_id": job_id,
                    "dialog_count": len(dialogs),
                    "pages_fetched": summary.get("pages_fetched"),
                    "completed": summary.get("completed"),
                },
            )
        except Exception as exc:
            converted = self._error_response(exc)
            error = converted.payload.get("error") or {}
            with self._jobs_lock:
                job = self._dialog_sync_jobs[job_id]
                job["state"] = "failed"
                job["error"] = error
                job["completed_at"] = datetime.now(timezone.utc).isoformat()
            self._persistent_job_finish(
                job_id,
                state="failed",
                error_code=str(error.get("error_code") or "dialog_sync_failed"),
            )
            self._runtime_logger.emit(
                "dialog_sync_failed",
                level="error",
                fields={
                    "job_id": job_id,
                    "component": error.get("component"),
                    "error_code": error.get("error_code"),
                    "error_type": (error.get("safe_context") or {}).get("error_type")
                    or type(exc).__name__,
                },
            )
        finally:
            with self._jobs_lock:
                if self._active_dialog_sync_job == job_id:
                    self._active_dialog_sync_job = None

    def _dialogs_sync_status(self, query: Mapping[str, str]) -> dict[str, Any]:
        job_id = str(query.get("job_id") or "").strip()
        if not job_id:
            raise CompositionValidationError("job_id is required.", code="api_job_id_required")
        with self._jobs_lock:
            job = self._dialog_sync_jobs.get(job_id)
            copied = dict(job) if job else None
        if copied is None:
            copied = self._persistent_job_snapshot(job_id, kind="dialog_sync")
        if copied is None:
            raise CompositionValidationError("Dialog sync job was not found.", code="api_job_not_found")
        return {"ok": True, "job": copied}

    def _dialog_avatar_source(self, bridge: Any, site_key: str, peer_key: str) -> tuple[Any, Any] | None:
        """Resolve a dialog peer/photo pair without rescanning 10k rows per avatar."""

        now = time.monotonic()
        cache_key = self._scoped_cache_key("avatar-source", site_key)
        with self._avatar_source_cache_lock:
            cached = self._avatar_source_cache.get(cache_key)
            valid = bool(cached and now - float(cached[0]) <= self._avatar_source_cache_ttl_seconds)
            sources = cached[1] if valid and cached is not None else None
            source = sources.get(peer_key) if sources is not None else None
        if source is not None:
            return source
        entries = bridge.core.discovery.cached_dialogs(active_only=False, limit=10_000)
        refreshed = {
            f"{item.peer.type.value}:{item.peer.id}": (item.peer, item.photo)
            for item in entries if item.photo is not None
        }
        with self._avatar_source_cache_lock:
            self._avatar_source_cache[cache_key] = (time.monotonic(), refreshed)
        return refreshed.get(peer_key)

    def _dialogs_avatar(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        peer_key = str(payload.get("peer_key") or "").strip()
        if not peer_key:
            raise CompositionValidationError("peer_key is required.", code="api_peer_key_required")
        entry = self.dialog_catalog.get(peer_key)
        if not entry:
            raise CompositionValidationError("Dialog was not found.", code="api_dialog_not_found")
        cached = entry.get("photo_cached_path")
        cached_path = Path(str(cached)).expanduser() if cached else None
        if cached_path and not cached_path.is_absolute():
            cached_path = (self.base_directory / cached_path).resolve()
        if cached_path is not None and not self._valid_avatar_file(cached_path):
            cached_path = None
        if bool(payload.get("cached_only")) and cached_path is None:
            return {"ok": True, "peer_key": peer_key, "avatar_present": False, "cached_only": True}
        if cached_path is None:
            def operation() -> Path | None:
                with self._open_bridge(
                    self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
                ) as bridge:
                    source = self._dialog_avatar_source(bridge, site_key, peer_key)
                    if source is None:
                        return None
                    source_peer, source_photo = source
                    output = bridge.config.core.media_directory / "avatars"
                    output.mkdir(parents=True, exist_ok=True)
                    file_name = f"{source_peer.type.value}_{source_peer.id}_{source_photo.photo_id}.jpg"
                    result = bridge.core.media.download(
                        source_photo,
                        MediaDownloadOptions(output_directory=output, file_name=file_name, overwrite=True, max_bytes=8 * 1024 * 1024),
                    )
                    path = result.path
                    if not self._valid_avatar_file(path):
                        return None
                    bridge.core.discovery.set_cached_photo_path(source_peer, source_photo.photo_id, path)
                    return path

            request_priority = str(payload.get("request_priority") or "background").strip().lower()
            cached_path = self._run_eitaa(
                priority=(
                    EitaaPriority.ACTIVE_AVATAR
                    if request_priority == "active"
                    else EitaaPriority.AVATAR_BACKGROUND
                ),
                kind=("dialogs.avatar.active" if request_priority == "active" else "dialogs.avatar.background"),
                callback=operation,
            )
            if cached_path is None:
                return {"ok": True, "peer_key": peer_key, "avatar_present": False}
            try:
                stored = str(cached_path.resolve().relative_to(self.base_directory))
            except ValueError:
                stored = str(cached_path.resolve())
            entry = self.dialog_catalog.set_photo_cached_path(peer_key, stored)
        if not self._valid_avatar_file(cached_path):
            return {"ok": True, "peer_key": peer_key, "avatar_present": False}
        data = cached_path.read_bytes()
        mime_type = self._avatar_mime_type(data)
        return {
            "ok": True, "peer_key": peer_key, "avatar_present": True,
            "mime_type": mime_type, "bytes": len(data),
            "data_url": f"data:{mime_type};base64,{base64.b64encode(data).decode('ascii')}",
        }

    @staticmethod
    def _avatar_mime_type(data: bytes) -> str:
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if data.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif"
        if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
            return "image/webp"
        return "image/jpeg"

    @classmethod
    def _valid_avatar_file(cls, path: Path) -> bool:
        try:
            if not path.is_file() or not 3 <= path.stat().st_size <= 8 * 1024 * 1024:
                return False
            with path.open("rb") as stream:
                header = stream.read(16)
        except OSError:
            return False
        return (
            header.startswith(b"\xff\xd8\xff")
            or header.startswith(b"\x89PNG\r\n\x1a\n")
            or header.startswith((b"GIF87a", b"GIF89a"))
            or (header.startswith(b"RIFF") and header[8:12] == b"WEBP")
        )

    def _merge_core_dialogs(
        self, bridge: EitaaBridge, entries: Any, *, source: str, complete: bool,
        finalize_snapshot: bool = True, active_keys: set[str] | None = None,
    ) -> dict[str, Any]:
        peer_directory = self._runtime.peer_directory
        peer_directory.mkdir(parents=True, exist_ok=True)
        selected_keys: set[str] = set()
        counts: dict[str, int] = {}
        skipped_unusable = 0
        account_roles = consume_dialog_account_roles()
        for entry in entries:
            peer = entry.peer
            if peer.type in {PeerType.USER, PeerType.CHANNEL} and peer.access_hash is None:
                # Deleted or otherwise incomplete server-side dialogs cannot be
                # converted into a sendable peer file. Keep synchronizing the
                # remaining account instead of failing the whole snapshot.
                skipped_unusable += 1
                continue
            peer_key = f"{peer.type.value}:{peer.id}"
            selected_keys.add(peer_key)
            peer_file = peer_directory / f"{peer.type.value}-{peer.id}.json"
            bridge.core.discovery.save_peer(peer, peer_file)
            technical_kind = entry.kind.value
            counts[technical_kind] = counts.get(technical_kind, 0) + 1
            self.dialog_catalog.upsert(
                peer=peer,
                peer_file=peer_file,
                source=source,
                top_message_id=entry.top_message_id,
                top_message_date=entry.top_message_date,
                unread_count=entry.unread_count,
                unread_mentions_count=entry.unread_mentions_count,
                read_inbox_max_id=entry.read_inbox_max_id,
                pinned=entry.pinned,
                unread_mark=entry.unread_mark,
                folder_id=entry.folder_id,
                technical_kind=technical_kind,
                broadcast=entry.broadcast,
                megagroup=entry.megagroup,
                participants_count=entry.participants_count,
                photo_cached_path=entry.photo_cached_path,
                active=True,
                account_role=account_roles.get(peer_key),
            )
        combined_keys = active_keys if active_keys is not None else selected_keys
        combined_keys.update(selected_keys)
        hidden = (
            self.dialog_catalog.mark_remote_snapshot(combined_keys, complete=complete)
            if finalize_snapshot else 0
        )
        return {
            "merged_count": len(selected_keys),
            "skipped_unusable_count": skipped_unusable,
            "hidden_inactive_count": hidden,
            "counts_by_kind": counts,
        }

    def _hydrate_dialog_catalog_from_core(self, *, site_key: str) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            with self._open_bridge(
                self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
            ) as bridge:
                cached = bridge.core.discovery.cached_dialogs(active_only=True, limit=10_000)
                merged = self._merge_core_dialogs(
                    bridge, cached, source="remote", complete=False
                )
                return {"loaded": True, "cached_count": len(cached), **merged}

        return self._run_eitaa(
            priority=EitaaPriority.BACKGROUND,
            kind="dialogs.cache",
            callback=operation,
        )

    def _sync_dialog_catalog(self, *, site_key: str, page_size: int, max_pages: int) -> dict[str, Any]:
        dialogs: list[Any] = []
        seen: set[tuple[str, int]] = set()
        skipped_unusable_keys: set[tuple[str, int]] = set()
        active_keys: set[str] = set()
        cursor_keys: set[tuple[int, int, str, int]] = set()
        warnings: list[str] = []
        duplicates = 0
        total_count: int | None = None
        cursor: Any | None = None
        complete = False
        pages_fetched = 0
        stabilization_restarts = 0
        counts: dict[str, int] = {}

        while pages_fetched < max_pages:
            page_number = pages_fetched + 1

            def fetch_page() -> tuple[Any, dict[str, Any]]:
                with self._open_bridge(
                    self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
                ) as bridge:
                    page = bridge.core.discovery.list_dialogs(
                        limit=page_size,
                        offset_date=cursor.offset_date if cursor else 0,
                        offset_id=cursor.offset_id if cursor else 0,
                        offset_peer=cursor.offset_peer if cursor else None,
                        exclude_pinned=False,
                    )
                    merged = self._merge_core_dialogs(
                        bridge,
                        page.dialogs,
                        source="remote",
                        complete=False,
                        finalize_snapshot=False,
                        active_keys=active_keys,
                    )
                    return page, merged

            page, merged = self._run_eitaa(
                priority=EitaaPriority.DIALOG_PAGE,
                kind="dialogs.page",
                callback=fetch_page,
            )
            pages_fetched += 1
            for kind, count in merged.get("counts_by_kind", {}).items():
                counts[kind] = counts.get(kind, 0) + int(count)
            warnings.extend(f"page{page_number}:{item}" for item in page.parse_warnings)
            if merged.get("skipped_unusable_count"):
                warnings.append(
                    f"page{page_number}:unusable_peer_missing_access_hash:"
                    f"{int(merged['skipped_unusable_count'])}"
                )
            if page.total_count is not None:
                total_count = max(total_count or 0, page.total_count)
            for item in page.dialogs:
                key = (item.peer.type.value, item.peer.id)
                if (
                    item.peer.type in {PeerType.USER, PeerType.CHANNEL}
                    and item.peer.access_hash is None
                ):
                    skipped_unusable_keys.add(key)
                    continue
                if key in seen:
                    duplicates += 1
                    continue
                seen.add(key)
                dialogs.append(item)

            if total_count is not None and len(dialogs) + len(skipped_unusable_keys) >= total_count:
                complete = True
                break
            if page.response_type != "messages.dialogsSlice":
                if total_count is None:
                    complete = True
                    break
                if stabilization_restarts < 2 and pages_fetched < max_pages:
                    stabilization_restarts += 1
                    warnings.append(f"stabilization_restart:{len(dialogs)}/{total_count}")
                    cursor = None
                    cursor_keys.clear()
                    continue
                warnings.append(f"stable_end_before_total:{len(dialogs)}/{total_count}")
                break
            if not page.dialogs:
                warnings.append(f"page{page_number}:empty_slice_before_total")
                break
            if page.next_cursor is None:
                warnings.append(f"page{page_number}:missing_next_cursor")
                break
            cursor_key = page.next_cursor.key()
            if cursor_key in cursor_keys:
                warnings.append(f"page{page_number}:repeated_next_cursor")
                break
            cursor_keys.add(cursor_key)
            cursor = page.next_cursor
            # Yield between pages so active-message tasks can move ahead of the
            # next background page without overlapping the shared session.
            time.sleep(0.05)

        if pages_fetched >= max_pages and not complete:
            warnings.append("max_pages_reached")

        collection = DialogCollection(
            dialogs=tuple(dialogs),
            total_count=total_count,
            pages_fetched=pages_fetched,
            duplicate_count=duplicates,
            complete=complete,
            parse_warnings=tuple(warnings),
        )

        def persist_snapshot() -> int:
            with self._open_bridge(
                self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
            ) as bridge:
                store = getattr(bridge.core.discovery, "store_dialog_snapshot", None)
                return int(store(collection)) if callable(store) else 0

        stored_count = self._run_eitaa(
            priority=EitaaPriority.BACKGROUND,
            kind="dialogs.persist",
            callback=persist_snapshot,
        )
        hidden = self.dialog_catalog.mark_remote_snapshot(active_keys, complete=complete)
        return {
            "completed": complete,
            "pages_fetched": pages_fetched,
            "remote_unique_count": len(dialogs),
            "catalog_count": len(self.dialog_catalog.list()),
            "server_total_count": total_count,
            "duplicate_count": duplicates,
            "skipped_unusable_count": len(skipped_unusable_keys),
            "stored_count": stored_count,
            "warning_codes": warnings,
            "merged_count": len(active_keys),
            "hidden_inactive_count": hidden,
            "counts_by_kind": counts,
            "cooperative_pagination": True,
        }

    def _dialogs_manual(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        mode = str(payload.get("mode") or "username").strip().lower()
        display_kind = str(payload.get("display_kind") or "").strip().lower() or None
        peer_directory = self._runtime.peer_directory
        peer_directory.mkdir(parents=True, exist_ok=True)
        with self._eitaa_lock, self._open_bridge(
            self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
        ) as bridge:
            if mode == "username":
                username = str(payload.get("username") or "").strip().lstrip("@")
                if not username:
                    raise CompositionValidationError("username is required.", code="api_username_required")
                peer = bridge.core.discovery.resolve_username(username).peer
            elif mode == "peer":
                type_value = str(payload.get("peer_type") or "").strip().lower()
                try:
                    peer_type = PeerType(type_value)
                except ValueError as exc:
                    raise CompositionValidationError(
                        "peer_type must be channel, chat, or user.", code="api_invalid_peer_type"
                    ) from exc
                peer_id = self._integer(payload.get("peer_id"), "peer_id", minimum=1)
                access_raw = payload.get("access_hash")
                try:
                    access_hash = None if access_raw in (None, "") else int(str(access_raw).strip())
                except (TypeError, ValueError) as exc:
                    raise CompositionValidationError(
                        "access_hash must be an integer.", code="api_invalid_access_hash"
                    ) from exc
                peer = Peer(
                    id=peer_id,
                    type=peer_type,
                    access_hash=access_hash,
                    username=str(payload.get("username") or "").strip().lstrip("@") or None,
                    title=str(payload.get("title") or "").strip() or None,
                )
                peer.validate()
            elif mode == "peer_file":
                peer = load_peer_file(self._peer_path(payload))
            else:
                raise CompositionValidationError("Unsupported manual dialog mode.", code="api_invalid_dialog_mode")
            peer_file = peer_directory / f"{peer.type.value}-{peer.id}.json"
            save_peer_file(peer_file, peer)
            entry = self.dialog_catalog.upsert(
                peer=peer,
                peer_file=peer_file,
                source="manual",
                display_kind=display_kind,
            )
            if display_kind:
                entry = self.dialog_catalog.set_display_kind(entry["peer_key"], display_kind)
        return {"ok": True, "site_key": site_key, "dialog": entry}

    def _dialogs_favorite(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._site_key(payload)
        peer_key = str(payload.get("peer_key") or "").strip()
        if not peer_key:
            raise CompositionValidationError("peer_key is required.", code="api_peer_key_required")
        try:
            entry = self.dialog_catalog.set_favorite(peer_key, bool(payload.get("favorite", True)))
        except KeyError as exc:
            raise CompositionValidationError("Dialog was not found.", code="api_dialog_not_found") from exc
        return {"ok": True, "dialog": entry}

    def _dialogs_display_kind(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._site_key(payload)
        peer_key = str(payload.get("peer_key") or "").strip()
        display_kind = str(payload.get("display_kind") or "").strip().lower()
        if not peer_key:
            raise CompositionValidationError("peer_key is required.", code="api_peer_key_required")
        try:
            entry = self.dialog_catalog.set_display_kind(peer_key, display_kind)
        except ValueError as exc:
            raise CompositionValidationError(
                "display_kind must be channel, group, or personal.", code="api_invalid_display_kind"
            ) from exc
        except KeyError as exc:
            raise CompositionValidationError("Dialog was not found.", code="api_dialog_not_found") from exc
        return {"ok": True, "dialog": entry}

    @staticmethod
    def _sender_contact_name(contact: Mapping[str, Any]) -> str:
        joined = " ".join(
            str(contact.get(field) or "").strip()
            for field in ("first_name", "last_name")
            if str(contact.get(field) or "").strip()
        ).strip()
        return joined or str(contact.get("username") or "").strip()

    @staticmethod
    def _sender_contact_name_is_generic_eitaa(name: str) -> bool:
        return name.strip().casefold() in {"eitaa", "ایتا"}

    def _enrich_message_senders(
        self,
        bridge: Any,
        peer: Peer,
        response: dict[str, Any],
    ) -> dict[str, Any]:
        """Attach local, human-readable sender metadata without another Eitaa RPC."""
        messages = response.get("messages")
        if not isinstance(messages, list):
            return response
        sender_ids = sorted({
            int(sender_key.split(":", 1)[1])
            for item in messages
            if isinstance(item, Mapping)
            and isinstance((sender_key := item.get("sender_key")), str)
            and sender_key.startswith("user:")
            and sender_key.split(":", 1)[1].isdigit()
        })
        profiles = self._sender_directory.profiles(sender_ids)

        core = getattr(bridge, "core", None)
        members = getattr(core, "members", None) if core is not None else None
        if members is not None and peer.type in {PeerType.CHAT, PeerType.CHANNEL}:
            try:
                for user_id in sender_ids:
                    if user_id in profiles:
                        continue
                    member = members.get(peer, user_id)
                    if member is None:
                        continue
                    display_name = str(member.user.display_name or "").strip()
                    profiles[user_id] = {
                        "display_name": display_name if display_name != str(user_id) else None,
                        "username": str(member.user.username or "").strip() or None,
                        "is_eitaa_contact": bool(member.user.is_contact),
                        "resolution": "community_member",
                    }
            except Exception as exc:
                self._runtime_logger.emit(
                    "message_sender_member_enrichment_failed",
                    fields={"error_type": type(exc).__name__, "sender_count": len(sender_ids)},
                )

        try:
            local_contacts: list[Mapping[str, Any]] = []
            for start in range(0, len(sender_ids), 500):
                local_contacts.extend(self._contact_store.find_contacts_by_eitaa_identity(
                    eitaa_user_ids=sender_ids[start:start + 500],
                ))
            for contact in local_contacts:
                user_id = contact.get("eitaa_user_id")
                if user_id is None:
                    continue
                selected_id = int(user_id)
                current = profiles.get(selected_id, {})
                contact_name = self._sender_contact_name(contact)
                preferred_contact_name = (
                    ""
                    if self._sender_contact_name_is_generic_eitaa(contact_name)
                    else contact_name
                )
                source = str(contact.get("source") or "").strip()
                profiles[selected_id] = {
                    "display_name": (
                        preferred_contact_name or current.get("display_name")
                    ),
                    "username": str(contact.get("username") or "").strip() or current.get("username"),
                    "is_eitaa_contact": (
                        source.startswith("eitaa_contact")
                        or bool(current.get("is_eitaa_contact"))
                    ),
                    "resolution": (
                        "eitaa_contact"
                        if source.startswith("eitaa_contact")
                        else "local_contact"
                    ),
                }
        except Exception as exc:
            self._runtime_logger.emit(
                "message_sender_contact_enrichment_failed",
                fields={"error_type": type(exc).__name__, "sender_count": len(sender_ids)},
            )

        for item in messages:
            if not isinstance(item, dict):
                continue
            sender_key = item.get("sender_key")
            if sender_key == "self":
                item.update({
                    "sender_display_name": "پیام‌های ارسالی من",
                    "sender_username": None,
                    "sender_is_eitaa_contact": False,
                    "sender_resolution": "self",
                })
                continue
            if not isinstance(sender_key, str) or not sender_key.startswith("user:"):
                continue
            raw_id = sender_key.split(":", 1)[1]
            profile = profiles.get(int(raw_id)) if raw_id.isdigit() else None
            item.update({
                "sender_display_name": profile.get("display_name") if profile else None,
                "sender_username": profile.get("username") if profile else None,
                "sender_is_eitaa_contact": bool(profile and profile.get("is_eitaa_contact")),
                "sender_resolution": profile.get("resolution") if profile else "unknown",
            })
        response["sender_resolution"] = {
            "resolved": sum(bool(item.get("sender_display_name")) for item in messages if isinstance(item, Mapping)),
            "unresolved": sum(
                item.get("sender_resolution") == "unknown"
                for item in messages
                if isinstance(item, Mapping)
            ),
        }
        return response

    def _messages_list(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        peer = load_peer_file(self._peer_path(payload))
        limit = self._integer(payload.get("limit", 100), "limit", minimum=1, maximum=10_000)
        before_raw = payload.get("before_id")
        before_id = None if before_raw in (None, "") else self._integer(before_raw, "before_id", minimum=1)
        date_from_raw = payload.get("date_from")
        date_to_raw = payload.get("date_to")
        date_from = self._aware_datetime(date_from_raw, "date_from") if date_from_raw not in (None, "") else None
        date_to = self._aware_datetime(date_to_raw, "date_to") if date_to_raw not in (None, "") else None
        if (date_from is None) != (date_to is None):
            raise CompositionValidationError(
                "date_from and date_to must be supplied together.",
                code="api_message_date_range_incomplete",
            )
        if date_from and date_to and date_from > date_to:
            raise CompositionValidationError(
                "date_from cannot be after date_to.", code="api_invalid_message_date_range"
            )

        def operation() -> dict[str, Any]:
            with self._open_bridge(
                self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
            ) as bridge:
                if date_from and date_to:
                    response = {
                        "ok": True,
                        **bridge.application_messages_by_date(
                            peer, date_from=date_from, date_to=date_to, limit=limit
                        ),
                    }
                else:
                    response = {
                        "ok": True,
                        **bridge.application_messages(peer, limit=min(limit, 500), before_id=before_id),
                    }
                return self._enrich_message_senders(bridge, peer, response)

        return self._run_eitaa(
            priority=EitaaPriority.ACTIVE_MESSAGES,
            kind="messages.list",
            callback=operation,
        )

    @staticmethod
    def _thumbnail_type(media: Any, *, target_edge: int = 420) -> str | None:
        candidates = [item for item in getattr(media, "photo_sizes", ()) if getattr(item, "type", None)]
        if not candidates:
            return None

        def dimensions(item: Any) -> tuple[int, int, int]:
            width = int(getattr(item, "width", 0) or 0)
            height = int(getattr(item, "height", 0) or 0)
            size = int(getattr(item, "size", 0) or 0)
            return max(width, height), width * height, size

        usable = [item for item in candidates if dimensions(item)[0] > 0]
        if usable:
            large_enough = [item for item in usable if dimensions(item)[0] >= target_edge]
            selected = min(large_enough, key=dimensions) if large_enough else max(usable, key=dimensions)
        else:
            selected = max(candidates, key=lambda item: int(getattr(item, "size", 0) or 0))
        return str(selected.type)

    @staticmethod
    def _cached_media_file(directory: Path, prefix: str) -> Path | None:
        if not directory.exists():
            return None
        candidates = [
            item for item in directory.glob(f"{prefix}.*")
            if item.is_file() and not item.name.endswith(".partial")
        ]
        return max(candidates, key=lambda item: item.stat().st_mtime, default=None)

    def _message_send(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Send text, photo, or file to the selected dialog through the shared scheduler."""

        site_key = self._site_key(payload)
        peer = load_peer_file(self._peer_path(payload))
        text = str(payload.get("text") or "").strip()
        upload_path_raw = str(payload.get("upload_path") or "").strip()
        send_as = str(payload.get("send_as") or "auto").strip().lower()
        if send_as not in {"auto", "photo", "file"}:
            raise CompositionValidationError(
                "send_as must be auto, photo, or file.", code="api_invalid_send_mode"
            )
        if not text and not upload_path_raw:
            raise CompositionValidationError(
                "Message text or an attachment is required.", code="api_message_send_empty"
            )

        upload_path: Path | None = None
        if upload_path_raw:
            upload_root = self._runtime.upload_directory.resolve()
            candidate = Path(upload_path_raw).expanduser().resolve()
            try:
                candidate.relative_to(upload_root)
            except ValueError as exc:
                raise CompositionValidationError(
                    "Attachment must come from the local upload staging directory.",
                    code="api_message_send_invalid_upload",
                ) from exc
            if not candidate.is_file():
                raise CompositionValidationError(
                    "Selected attachment no longer exists.", code="api_message_send_upload_missing"
                )
            upload_path = candidate

        def operation() -> dict[str, Any]:
            with self._open_bridge(
                self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
            ) as bridge:
                if upload_path is None:
                    result = bridge.core.send.send_text(peer, text)
                    kind = "text"
                else:
                    mime = mimetypes.guess_type(upload_path.name)[0] or "application/octet-stream"
                    image = mime.startswith("image/")
                    if send_as == "photo" or (send_as == "auto" and image):
                        result = bridge.core.send.send_photo(peer, upload_path, caption=text)
                        kind = "photo"
                    else:
                        result = bridge.core.send.send_file(
                            peer, upload_path, caption=text, mime_type=mime
                        )
                        kind = "file"
                return {"ok": True, "kind": kind, "result": result.safe_summary()}

        try:
            response = self._run_eitaa(
                priority=EitaaPriority.ACTIVE_MESSAGES,
                kind="messages.send",
                callback=operation,
                timeout=600.0 if upload_path is not None else 90.0,
            )
        finally:
            if upload_path is not None and bool(payload.get("cleanup_upload", True)):
                try:
                    upload_path.unlink(missing_ok=True)
                except OSError:
                    pass
        return response

    def _media_preview(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        peer = load_peer_file(self._peer_path(payload))
        message_id = self._integer(payload.get("message_id"), "message_id", minimum=1)
        quality = str(payload.get("quality") or "thumbnail").strip().lower()
        if quality not in {"thumbnail", "full"}:
            raise CompositionValidationError(
                "quality must be thumbnail or full.", code="api_invalid_media_quality"
            )
        default_max = 6 * 1024 * 1024 if quality == "thumbnail" else 128 * 1024 * 1024
        maximum = 16 * 1024 * 1024 if quality == "thumbnail" else 512 * 1024 * 1024
        max_bytes = self._integer(
            payload.get("max_bytes", default_max),
            "max_bytes",
            minimum=32 * 1024,
            maximum=maximum,
        )

        def operation() -> dict[str, Any]:
            with self._open_bridge(
                self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
            ) as bridge:
                message = bridge.core.messages.get(peer, message_id)
                if message is None:
                    raise CompositionValidationError(
                        "Stored message was not found.",
                        safe_context={"message_id": message_id},
                        code="composition_message_not_found",
                    )
                if message.media is None:
                    return {"ok": True, "message_id": message_id, "media_present": False}
                media = message.media
                media_type = media.type.value
                mime_hint = str(media.mime_type or "").strip().lower()
                is_image = media_type in {"photo", "image_document", "sticker"}
                is_playable = media_type in {"audio", "video"} or mime_hint.startswith(
                    ("audio/", "video/")
                )
                if not is_image and (quality != "full" or not is_playable):
                    return {
                        "ok": True,
                        "message_id": message_id,
                        "media_present": True,
                        "preview_available": False,
                        "media": media.safe_summary(),
                    }

                thumb_type = (
                    self._thumbnail_type(media)
                    if is_image and quality == "thumbnail"
                    else None
                )
                cache_directory = bridge.config.core.media_directory / "ui-cache" / quality
                cache_directory.mkdir(parents=True, exist_ok=True)
                remote_id = int(getattr(media, "remote_id", 0) or 0)
                prefix = f"{peer.type.value}_{peer.id}_{message_id}_{remote_id}"
                cache_path = self._cached_media_file(cache_directory, prefix)
                cache_hit = cache_path is not None
                if cache_path is None:
                    result = bridge.core.media.download(
                        media,
                        MediaDownloadOptions(
                            output_directory=cache_directory,
                            file_name=prefix,
                            overwrite=True,
                            max_bytes=max_bytes if quality == "full" else max(max_bytes, 64 * 1024 * 1024),
                            chunk_size=256 * 1024 if quality == "thumbnail" else 512 * 1024,
                            request_delay_seconds=0.0 if quality == "thumbnail" else 0.15,
                            photo_thumb_type=thumb_type,
                        ),
                    )
                    cache_path = result.path
                file_size = cache_path.stat().st_size
                if file_size > max_bytes:
                    if quality == "thumbnail":
                        cache_path.unlink(missing_ok=True)
                    raise CompositionValidationError(
                        "Media preview exceeds the configured UI limit.",
                        safe_context={"bytes": file_size, "max_bytes": max_bytes, "quality": quality},
                        code="api_media_preview_too_large",
                    )
                fallback_mime = (
                    "image/jpeg"
                    if is_image
                    else "audio/mpeg"
                    if media_type == "audio"
                    else "video/mp4"
                )
                mime_type = (
                    mimetypes.guess_type(cache_path.name)[0]
                    or media.mime_type
                    or fallback_mime
                )
                token = self.register_media_cache_file(cache_path, mime_type)
                self._runtime_logger.emit(
                    "media_cache",
                    fields={
                        "quality": quality,
                        "cache_hit": cache_hit,
                        "bytes": file_size,
                        "media_type": media.type.value,
                        "thumb_type": thumb_type,
                    },
                )
                return {
                    "ok": True,
                    "message_id": message_id,
                    "media_present": True,
                    "preview_available": True,
                    "quality": quality,
                    "cache_hit": cache_hit,
                    "thumb_type": thumb_type,
                    "mime_type": mime_type,
                    "bytes": file_size,
                    "media_url": f"/api/v1/media-cache/{token}",
                }

        return self._run_eitaa(
            priority=EitaaPriority.MEDIA_PREVIEW,
            kind=f"messages.media-{quality}",
            callback=operation,
        )

    def _messages_read(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        peer = load_peer_file(self._peer_path(payload))
        max_id = self._integer(payload.get("max_id"), "max_id", minimum=1)
        remaining_raw = payload.get("remaining_unread_count")
        remaining = None if remaining_raw in (None, "") else self._integer(
            remaining_raw, "remaining_unread_count", minimum=0, maximum=1_000_000
        )

        def operation() -> Any:
            with self._open_bridge(
                self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
            ) as bridge:
                return bridge.core.history.mark_read(
                    peer, max_id, remaining_unread_count=remaining
                )

        result = self._run_eitaa(
            priority=EitaaPriority.READ_RECEIPT,
            kind="messages.read",
            callback=operation,
        )
        peer_key = f"{peer.type.value}:{peer.id}"
        dialog = None
        if result.accepted:
            try:
                dialog = self.dialog_catalog.mark_read(
                    peer_key, max_id=max_id, remaining_unread_count=remaining
                )
            except KeyError:
                pass
        return {"ok": True, "site_key": site_key, "read": result.safe_summary(), "dialog": dialog}

    def _messages_read_enqueue(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        peer_path = self._peer_path(payload)
        peer = load_peer_file(peer_path)
        max_id = self._integer(payload.get("max_id"), "max_id", minimum=1)
        remaining_raw = payload.get("remaining_unread_count")
        remaining = None if remaining_raw in (None, "") else self._integer(
            remaining_raw, "remaining_unread_count", minimum=0, maximum=1_000_000
        )
        peer_key = f"{peer.type.value}:{peer.id}"
        receipt_key = self._scoped_cache_key("read-receipt", peer_key)
        due_at = time.monotonic() + self._read_receipt_delay_seconds
        with self._read_queue_lock:
            previous = self._pending_read_receipts.get(receipt_key)
            if previous is None or max_id >= int(previous["max_id"]):
                self._pending_read_receipts[receipt_key] = {
                    "site_key": site_key,
                    "peer_path": str(peer_path),
                    "peer_key": peer_key,
                    "max_id": max_id,
                    "remaining_unread_count": remaining,
                    "due_at": due_at,
                }
            else:
                previous["due_at"] = due_at
                if remaining is not None:
                    previous_remaining = previous.get("remaining_unread_count")
                    previous["remaining_unread_count"] = (
                        remaining if previous_remaining is None else min(int(previous_remaining), remaining)
                    )
            if not self._read_worker_active:
                self._read_worker_active = True
                threading.Thread(
                    target=self._runtime_bound_target(self._run_read_receipt_worker),
                    name="eitaa-bridge-read-receipts",
                    daemon=True,
                ).start()
        return {
            "ok": True,
            "queued": True,
            "site_key": site_key,
            "peer_key": peer_key,
            "max_id": max_id,
            "remaining_unread_count": remaining,
            "delay_seconds": self._read_receipt_delay_seconds,
        }

    def _run_read_receipt_worker(self) -> None:
        while True:
            with self._read_queue_lock:
                if not self._pending_read_receipts:
                    self._read_worker_active = False
                    return
                receipt_key, task = min(
                    self._pending_read_receipts.items(),
                    key=lambda item: float(item[1].get("due_at", 0.0)),
                )
                wait_seconds = max(0.0, float(task.get("due_at", 0.0)) - time.monotonic())
            if wait_seconds:
                time.sleep(min(wait_seconds, 0.5))
                continue
            if self._scheduler.has_higher_priority_work(EitaaPriority.READ_RECEIPT):
                with self._read_queue_lock:
                    if receipt_key in self._pending_read_receipts:
                        self._pending_read_receipts[receipt_key]["due_at"] = time.monotonic() + 1.0
                time.sleep(0.2)
                continue
            with self._read_queue_lock:
                task = self._pending_read_receipts.pop(receipt_key, None)
            if task is None:
                continue
            try:
                peer = load_peer_file(Path(str(task["peer_path"])))

                def operation() -> Any:
                    with self._open_bridge(
                        self.config_path,
                        env_file=self.env_file,
                        site_key=str(task["site_key"]),
                        open_core=True,
                    ) as bridge:
                        return bridge.core.history.mark_read(
                            peer,
                            int(task["max_id"]),
                            remaining_unread_count=task.get("remaining_unread_count"),
                        )

                result = self._run_eitaa(
                    priority=EitaaPriority.READ_RECEIPT,
                    kind="messages.read",
                    callback=operation,
                )
                if result.accepted:
                    try:
                        self.dialog_catalog.mark_read(
                            str(task["peer_key"]),
                            max_id=int(task["max_id"]),
                            remaining_unread_count=task.get("remaining_unread_count"),
                        )
                    except KeyError:
                        pass
            except Exception as exc:
                # A read receipt is best-effort and must never delay active
                # retrieval, but its failure remains support-visible.
                self._runtime_logger.emit(
                    "read_receipt_failed",
                    level="warning",
                    reason_code="read_receipt_background_operation_failed",
                    operation="messages.read",
                    fields={"error_type": type(exc).__name__},
                )
                continue

    def _messages_sync(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        peer = load_peer_file(self._peer_path(payload))
        pages = self._integer(payload.get("pages", 1), "pages", minimum=1, maximum=100)
        page_size = self._integer(payload.get("page_size", 20), "page_size", minimum=1, maximum=100)
        offset_id = self._integer(payload.get("offset_id", 0), "offset_id", minimum=0)
        stop_when_unchanged = bool(payload.get("stop_when_unchanged", True))

        def operation() -> dict[str, Any]:
            with self._open_bridge(
                self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
            ) as bridge:
                result = bridge.sync_application_messages(
                    peer,
                    pages=pages,
                    page_size=page_size,
                    offset_id=offset_id,
                    stop_when_unchanged=stop_when_unchanged,
                )
                return {"ok": True, "site_key": site_key, "sync": result}

        return self._run_eitaa(
            priority=EitaaPriority.ACTIVE_MESSAGES,
            kind="messages.sync",
            callback=operation,
        )

    def _messages_date_range_sync(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        peer = load_peer_file(self._peer_path(payload))
        date_from = self._aware_datetime(payload.get("date_from"), "date_from")
        date_to = self._aware_datetime(payload.get("date_to"), "date_to")
        if date_from > date_to:
            raise CompositionValidationError(
                "date_from cannot be after date_to.", code="api_invalid_message_date_range"
            )
        pages = self._integer(payload.get("pages", 100), "pages", minimum=1, maximum=200)
        page_size = self._integer(payload.get("page_size", 100), "page_size", minimum=1, maximum=100)

        def operation() -> dict[str, Any]:
            with self._open_bridge(
                self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
            ) as bridge:
                result = bridge.sync_application_messages_date_range(
                    peer,
                    date_from=date_from,
                    date_to=date_to,
                    pages=pages,
                    page_size=page_size,
                )
                return {"ok": True, "site_key": site_key, "sync": result}

        return self._run_eitaa(
            priority=EitaaPriority.ACTIVE_MESSAGES,
            kind="messages.date-range",
            callback=operation,
        )

    def _message_usage(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        peer = load_peer_file(self._peer_path(payload))
        message_id = self._integer(payload.get("message_id"), "message_id", minimum=1)
        def operation() -> dict[str, Any]:
            with self._open_bridge(
                self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
            ) as bridge:
                return {"ok": True, "usage": bridge.wordpress_message_usage_details(peer, message_id)}

        return self._run_eitaa(
            priority=EitaaPriority.ACTIVE_MESSAGES,
            kind="messages.usage",
            callback=operation,
        )

    @staticmethod
    def _content_index_labels(payload: Mapping[str, Any]) -> tuple[IndexLabel, ...]:
        raw = payload.get("labels")
        if not isinstance(raw, list) or not 1 <= len(raw) <= 200:
            raise CompositionValidationError(
                "labels must contain 1 to 200 WordPress categories.",
                code="api_content_index_labels_required",
            )
        selected: list[IndexLabel] = []
        for item in raw:
            if not isinstance(item, Mapping):
                raise CompositionValidationError(
                    "Each content-index label must be an object.",
                    code="api_invalid_content_index_label",
                )
            aliases_raw = item.get("aliases", [])
            if not isinstance(aliases_raw, list):
                raise CompositionValidationError(
                    "Content-index label aliases must be a list.",
                    code="api_invalid_content_index_label",
                )
            try:
                label = IndexLabel(
                    id=int(item.get("id")),
                    name=str(item.get("name") or "").strip(),
                    aliases=tuple(str(value).strip() for value in aliases_raw),
                    is_primary=bool(item.get("is_primary")),
                )
                label.validate()
            except (TypeError, ValueError) as exc:
                raise CompositionValidationError(
                    "Content-index label is invalid.",
                    code="api_invalid_content_index_label",
                ) from exc
            selected.append(label)
        if len({item.id for item in selected}) != len(selected):
            raise CompositionValidationError(
                "Content-index label IDs must be unique.",
                code="api_duplicate_content_index_label",
            )
        return tuple(selected)

    @staticmethod
    def _content_index_job_copy(job: Mapping[str, Any]) -> dict[str, Any]:
        copied = dict(job)
        if isinstance(copied.get("progress"), Mapping):
            copied["progress"] = dict(copied["progress"])
        if isinstance(copied.get("result"), Mapping):
            copied["result"] = dict(copied["result"])
        if isinstance(copied.get("error"), Mapping):
            copied["error"] = dict(copied["error"])
        return copied

    def _content_index_start(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        peer_path = self._peer_path(payload)
        peer = load_peer_file(peer_path)
        labels = self._content_index_labels(payload)
        max_messages = self._integer(
            payload.get("max_messages", 20_000),
            "max_messages",
            minimum=1,
            maximum=50_000,
        )
        threshold = self._number(
            payload.get("score_threshold", DEFAULT_SCORE_THRESHOLD),
            "score_threshold",
            minimum=0.05,
            maximum=0.95,
        )
        scope = self._scoped_cache_key(
            "content-index-active",
            site_key,
            peer.type.value,
            peer.id,
        )
        with self._content_index_lock:
            active_id = self._content_index_active.get(scope)
            if active_id:
                active = self._content_index_jobs.get(active_id)
                if active and active.get("state") in {"queued", "running", "cancelling"}:
                    return {
                        "ok": True,
                        "reused": True,
                        "job": self._content_index_job_copy(active),
                    }
            job_id = self._persistent_job_create("content.index")
            cancellation = threading.Event()
            job: dict[str, Any] = {
                "job_id": job_id,
                "kind": "local_content_index",
                "site_key": site_key,
                "peer_key": f"{peer.type.value}:{peer.id}",
                "state": "queued",
                "local_only": True,
                "max_messages": max_messages,
                "score_threshold": threshold,
                "label_count": len(labels),
                "progress": {
                    "processed_messages": 0,
                    "target_messages": 0,
                    "indexed_messages": 0,
                    "prediction_count": 0,
                },
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            self._content_index_jobs[job_id] = job
            self._content_index_active[scope] = job_id
            self._content_index_cancellations[job_id] = cancellation
        threading.Thread(
            target=self._runtime_bound_target(self._run_content_index_job),
            args=(
                job_id,
                scope,
                site_key,
                peer,
                labels,
                max_messages,
                threshold,
                cancellation,
            ),
            name=f"local-content-index-{job_id[:8]}",
            daemon=True,
        ).start()
        return {"ok": True, "reused": False, "job": self._content_index_job_copy(job)}

    def _run_content_index_job(
        self,
        job_id: str,
        scope: str,
        site_key: str,
        peer: Peer,
        labels: tuple[IndexLabel, ...],
        max_messages: int,
        threshold: float,
        cancellation: threading.Event,
    ) -> None:
        with self._content_index_lock:
            job = self._content_index_jobs[job_id]
            job["state"] = "running"
            job["started_at"] = datetime.now(timezone.utc).isoformat()
        self._runtime_logger.emit(
            "content_index_job_started",
            result="started",
            operation="content.index",
            fields={"job_id": job_id},
        )

        def update_progress(summary: Mapping[str, object]) -> None:
            with self._content_index_lock:
                current = self._content_index_jobs.get(job_id)
                if current is not None:
                    current["progress"] = dict(summary)

        try:
            self._persistent_job_begin(job_id)
            # This worker deliberately bypasses the Eitaa scheduler: it opens a
            # thread-owned Core and calls public local message-store methods only.
            with self._open_bridge(
                self.config_path,
                env_file=self.env_file,
                site_key=site_key,
                open_core=True,
            ) as bridge:
                result = LocalContentIndexService(self._content_index_store).run(
                    bridge,
                    job_id=job_id,
                    site_key=site_key,
                    peer=peer,
                    labels=labels,
                    cancel_event=cancellation,
                    progress=update_progress,
                    max_messages=max_messages,
                    score_threshold=threshold,
                )
            with self._content_index_lock:
                job = self._content_index_jobs[job_id]
                job["state"] = str(result.get("state") or "completed")
                job["result"] = dict(result)
                job["completed_at"] = datetime.now(timezone.utc).isoformat()
            self._persistent_job_finish(
                job_id,
                state=str(result.get("state") or "completed"),
            )
            final_state = str(result.get("state") or "completed")
            self._runtime_logger.emit(
                (
                    "content_index_job_cancelled"
                    if final_state == "cancelled"
                    else "content_index_job_succeeded"
                ),
                result="cancelled" if final_state == "cancelled" else "succeeded",
                operation="content.index",
                fields={"job_id": job_id, "state": final_state},
            )
        except Exception as exc:
            safe_context = dict(exc.safe_context) if isinstance(exc, LocalContentIndexError) else {}
            try:
                self._content_index_store.initialize()
                self._content_index_store.discard_staged_results(job_id=job_id)
                self._content_index_store.finish_run(
                    job_id=job_id,
                    state="failed",
                    model_version=None,
                    summary={
                        "state": "failed",
                        "error_code": getattr(exc, "code", "content_index_job_failed"),
                    },
                )
            except LocalContentIndexError as cleanup_exc:
                # Preserve the original failure. A staging cleanup problem is
                # never allowed to promote incomplete rows.
                self._runtime_logger.emit(
                    "content_index_job_cleanup_failed",
                    level="warning",
                    reason_code=str(
                        getattr(cleanup_exc, "code", "content_index_cleanup_failed")
                    ),
                    operation="content.index.cleanup",
                    fields={"job_id": job_id, "error_type": type(cleanup_exc).__name__},
                )
            with self._content_index_lock:
                job = self._content_index_jobs[job_id]
                job["state"] = "failed"
                job["error"] = {
                    "error_code": getattr(exc, "code", "content_index_job_failed"),
                    "message": (
                        exc.message
                        if isinstance(exc, LocalContentIndexError)
                        else "Local content indexing failed."
                    ),
                    "error_type": type(exc).__name__,
                    "safe_context": safe_context,
                }
                job["completed_at"] = datetime.now(timezone.utc).isoformat()
            self._persistent_job_finish(
                job_id,
                state="failed",
                error_code=str(getattr(exc, "code", "content_index_job_failed")),
            )
            self._runtime_logger.emit(
                "content_index_job_failed",
                level="error",
                reason_code=str(getattr(exc, "code", "content_index_job_failed")),
                operation="content.index",
                fields={"job_id": job_id, "error_type": type(exc).__name__},
            )
        finally:
            with self._content_index_lock:
                if self._content_index_active.get(scope) == job_id:
                    self._content_index_active.pop(scope, None)
                self._content_index_cancellations.pop(job_id, None)

    def _content_index_status(self, query: Mapping[str, Any]) -> dict[str, Any]:
        job_id = str(query.get("job_id") or "").strip()
        if not job_id:
            raise CompositionValidationError(
                "job_id is required.", code="api_job_id_required"
            )
        with self._content_index_lock:
            job = self._content_index_jobs.get(job_id)
            copied = self._content_index_job_copy(job) if job is not None else None
        if copied is None:
            copied = self._persistent_job_snapshot(job_id, kind="local_content_index")
        if copied is None:
            raise CompositionValidationError(
                "Content-index job was not found.",
                code="api_content_index_job_not_found",
            )
        return {"ok": True, "job": copied}

    def _content_index_cancel(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        job_id = str(payload.get("job_id") or "").strip()
        if not job_id:
            raise CompositionValidationError(
                "job_id is required.", code="api_job_id_required"
            )
        self._persistent_job_cancel(job_id)
        with self._content_index_lock:
            job = self._content_index_jobs.get(job_id)
            if job is not None:
                cancellation = self._content_index_cancellations.get(job_id)
                if cancellation is not None and job.get("state") in {"queued", "running"}:
                    cancellation.set()
                    job["state"] = "cancelling"
                copied = self._content_index_job_copy(job)
            else:
                copied = None
        if copied is None:
            copied = self._persistent_job_snapshot(job_id, kind="local_content_index")
        if copied is None:
            raise CompositionValidationError(
                "Content-index job was not found.",
                code="api_content_index_job_not_found",
            )
        return {"ok": True, "job": copied}

    def _content_index_results(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        peer = load_peer_file(self._peer_path(payload))
        limit = self._integer(
            payload.get("limit", 50_000), "limit", minimum=1, maximum=50_000
        )
        self._content_index_store.initialize()
        stored_results = self._content_index_store.list_results(
            site_key=site_key,
            peer_type=peer.type.value,
            peer_id=peer.id,
            limit=limit,
        )
        # Manual corrections are an operator-owned overlay.  Keep the
        # classifier's immutable result set for auditability, but expose the
        # latest accept/reject decision immediately in the UI and filters.
        source_prefix = f"{peer.type.value}:{peer.id}:"
        latest_feedback: dict[tuple[int, int], Mapping[str, object]] = {}
        for feedback in self._content_index_store.list_feedback(
            site_key=site_key, limit=10_000, newest_first=True
        ):
            source_key = str(feedback.get("source_key") or "")
            if not source_key.startswith(source_prefix):
                continue
            try:
                message_id = int(source_key[len(source_prefix) :])
                label_id = int(feedback["label_id"])
            except (TypeError, ValueError):
                continue
            latest_feedback.setdefault((message_id, label_id), feedback)

        results: list[dict[str, object]] = []
        result_by_message: dict[int, dict[str, object]] = {}
        for stored in stored_results:
            item = dict(stored)
            item["predictions"] = [
                dict(prediction)
                for prediction in item.get("predictions", [])
                if isinstance(prediction, Mapping)
            ]
            message_id = int(item["message_id"])
            result_by_message[message_id] = item
            results.append(item)

        for (message_id, label_id), feedback in latest_feedback.items():
            item = result_by_message.get(message_id)
            if item is None:
                item = {
                    "message_id": message_id,
                    "text_hash": "",
                    "model_version": "manual-feedback-v1",
                    "predictions": [],
                    "indexed_at": str(feedback.get("created_at") or ""),
                }
                result_by_message[message_id] = item
                results.append(item)
            predictions = [
                prediction
                for prediction in item["predictions"]
                if int(prediction.get("label_id", 0)) != label_id
            ]
            if str(feedback.get("decision")) == "accept":
                predictions.append(
                    {
                        "label_id": label_id,
                        "label_name": str(feedback.get("label_name") or label_id),
                        "score": 1.0,
                        "evidence": ["اصلاح دستی اپراتور"],
                        "accepted": True,
                        "manual": True,
                    }
                )
            item["predictions"] = predictions

        results.sort(key=lambda item: int(item["message_id"]), reverse=True)
        labels: dict[int, str] = {}
        for item in results:
            for prediction in item.get("predictions", []):
                if isinstance(prediction, Mapping):
                    labels[int(prediction["label_id"])] = str(prediction["label_name"])
        return {
            "ok": True,
            "site_key": site_key,
            "peer_key": f"{peer.type.value}:{peer.id}",
            "result_count": len(results),
            "results": results,
            "labels": [
                {"id": label_id, "name": labels[label_id]}
                for label_id in sorted(labels)
            ],
        }

    def _content_index_feedback(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        peer = load_peer_file(self._peer_path(payload))
        message_id = self._integer(payload.get("message_id"), "message_id", minimum=1)
        label_id = self._integer(payload.get("label_id"), "label_id", minimum=1)
        label_name = str(payload.get("label_name") or "").strip()
        if not label_name or len(label_name) > 200:
            raise CompositionValidationError(
                "label_name must contain 1 to 200 characters.",
                code="api_invalid_content_index_label",
            )
        decision = str(payload.get("decision") or "").strip().lower()
        if decision not in {"accept", "reject"}:
            raise CompositionValidationError(
                "decision must be accept or reject.",
                code="api_invalid_content_index_feedback",
            )
        self._content_index_store.initialize()
        feedback_id = self._content_index_store.add_feedback(
            site_key=site_key,
            source_key=f"{peer.type.value}:{peer.id}:{message_id}",
            label_id=label_id,
            label_name=label_name,
            decision=decision,
        )
        return {
            "ok": True,
            "feedback_id": feedback_id,
            "message_id": message_id,
            "label_id": label_id,
            "decision": decision,
            "applies_on_next_run": False,
        }

    @staticmethod
    def _eitaa_contact_status(user: Any) -> dict[str, Any] | None:
        status = getattr(user, "status", None)
        return status.safe_summary() if status is not None else None

    def _eitaa_contact_peer_file(self, user: Any) -> str | None:
        peer = getattr(user, "peer", None)
        if peer is None or getattr(peer, "access_hash", None) is None:
            return None
        directory = self._runtime.contact_peers_directory
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"user-{int(peer.id)}.json"
        save_peer_file(path, peer)
        return str(path.relative_to(self.base_directory))

    def _eitaa_contact_payload(self, contact: Any) -> dict[str, Any]:
        user = contact.user
        phone = str(user.phone) if getattr(user, "phone", None) is not None else ""
        return {
            "user_id": int(user.peer.id),
            "peer_key": f"{user.peer.type.value}:{int(user.peer.id)}",
            "first_name": str(user.first_name or ""),
            "last_name": str(user.last_name or ""),
            "display_name": " ".join(
                item for item in [str(user.first_name or "").strip(), str(user.last_name or "").strip()] if item
            ) or str(user.username or "") or phone or f"کاربر {int(user.peer.id)}",
            "username": str(user.username or ""),
            "phone": phone,
            "mutual": bool(getattr(contact, "mutual", False)),
            "is_contact": bool(getattr(user, "is_contact", True)),
            "is_mutual_contact": bool(getattr(user, "is_mutual_contact", False)),
            "access_hash_present": getattr(user.peer, "access_hash", None) is not None,
            "peer_file": self._eitaa_contact_peer_file(user),
            "status": self._eitaa_contact_status(user),
        }

    def _invalidate_eitaa_contacts_cache(self, site_key: str) -> None:
        cache_key = self._scoped_cache_key("eitaa-contacts", site_key)
        with self._eitaa_contacts_cache_lock:
            self._eitaa_contacts_cache.pop(cache_key, None)

    def _contact_mutation_context(self) -> ContactMutationContext:
        """Build contact audit context only from trusted server-side selection."""

        account_id = self._runtime.ownership.messenger_account_id
        return ContactMutationContext(
            actor_app_user_id=self._request_actor_app_user_id.get(),
            messenger_account_id=account_id,
            provider="eitaa" if account_id else None,
            request_id=RuntimeLogger.current_correlation_id(),
        )

    def _upsert_eitaa_local_contact(
        self,
        payload: Mapping[str, Any],
        *,
        duplicate_policy: str = "update",
        category_policy: str = "merge",
        status_policy: str = "preserve",
        safe_reason_code: str = "eitaa_contact_observed",
    ) -> dict[str, Any]:
        """Write shared fields globally and provider identity only for the selected account."""

        row = dict(payload)
        context = self._contact_mutation_context()
        provider_user_id = row.get("eitaa_user_id")
        if context.messenger_account_id:
            # These legacy columns are global and therefore cannot safely hold
            # one of several account-specific identities or access hashes.
            row.pop("eitaa_user_id", None)
            row.pop("access_hash", None)
        saved = self._contact_store.upsert_contact(
            row,
            duplicate_policy=duplicate_policy,
            category_policy=category_policy,
            status_policy=status_policy,
            context=context,
        )
        if context.messenger_account_id and provider_user_id not in (None, ""):
            binding = self._contact_store.record_account_binding(
                contact_id=int(saved["id"]),
                messenger_account_id=context.messenger_account_id,
                provider="eitaa",
                provider_user_id=provider_user_id,
                reachability="reachable",
                safe_reason_code=safe_reason_code,
                last_resolved_at=row.get("last_resolved_at"),
                context=context,
            )
            canonical_id = int(binding["contact_id"])
            if canonical_id != int(saved["id"]):
                refreshed = self._contact_store.get_contacts((canonical_id,))
                if refreshed:
                    saved = refreshed[0]
            saved = dict(saved)
            saved["selected_account_binding"] = binding
        return saved

    def _with_selected_contact_bindings(
        self,
        contacts: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        selected = [dict(item) for item in contacts]
        account_id = self._runtime.ownership.messenger_account_id
        if account_id:
            for item in selected:
                # Legacy provider identity columns are never shared through a
                # multi-account API response. Only the selected binding is.
                item["eitaa_user_id"] = None
                item["access_hash_present"] = False
        if not account_id or not selected:
            for item in selected:
                item["selected_account_binding"] = None
            return selected
        bindings = self._contact_store.selected_account_bindings(
            [int(item["id"]) for item in selected],
            messenger_account_id=account_id,
            provider="eitaa",
        )
        for item in selected:
            item["selected_account_binding"] = bindings.get(int(item["id"]))
        return selected

    def _allow_legacy_contact_identity(self) -> bool:
        account_id = self._runtime.ownership.messenger_account_id
        return bool(
            account_id
            and account_id
            == self.config.features.multi_session.legacy_default_messenger_account_id
        )

    def _eitaa_contacts_list(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        refresh = bool(payload.get("refresh", False))
        search = str(payload.get("search") or "").strip().casefold()
        limit = self._integer(payload.get("limit", 50), "limit", minimum=1, maximum=500)
        offset = self._integer(payload.get("offset", 0), "offset", minimum=0, maximum=1_000_000)
        now = time.monotonic()
        cache_key = self._scoped_cache_key("eitaa-contacts", site_key)

        with self._eitaa_contacts_cache_lock:
            cached = self._eitaa_contacts_cache.get(cache_key)
            cached_valid = bool(
                cached
                and not refresh
                and now - float(cached[0]) <= self._eitaa_contacts_cache_ttl_seconds
            )
            cached_contacts = cached[1] if cached_valid and cached is not None else None
            cached_not_modified = bool(cached[2]) if cached_valid and cached is not None else False

        if cached_contacts is None:
            def operation() -> dict[str, Any]:
                with self._open_bridge(
                    self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
                ) as bridge:
                    snapshot = bridge.core.contacts.list(refresh=refresh)
                    contacts = [self._eitaa_contact_payload(item) for item in snapshot.contacts]
                    contacts.sort(key=lambda item: (item["display_name"].casefold(), item["user_id"]))
                    return {"contacts": tuple(contacts), "not_modified": bool(snapshot.not_modified)}

            loaded = self._run_eitaa(
                priority=EitaaPriority.ACTIVE_MESSAGES,
                kind="contacts.list",
                callback=operation,
                timeout=120.0,
            )
            all_contacts = tuple(loaded["contacts"])
            not_modified = bool(loaded.get("not_modified"))
            with self._eitaa_contacts_cache_lock:
                self._eitaa_contacts_cache[cache_key] = (
                    time.monotonic(),
                    all_contacts,
                    not_modified,
                )
        else:
            all_contacts = cached_contacts
            not_modified = cached_not_modified

        synced_local = 0
        if bool(payload.get("sync_local", False)):
            category_ids = list(self._contact_ids(payload, "category_ids"))
            for item in all_contacts:
                phone = str(item.get("phone") or "").strip()
                if not phone:
                    continue
                self._contact_validation(lambda item=item, phone=phone: self._upsert_eitaa_local_contact(
                    {
                        "phones": [phone],
                        "first_name": item.get("first_name") or "",
                        "last_name": item.get("last_name") or "",
                        "username": item.get("username") or "",
                        "eitaa_user_id": item.get("user_id"),
                        "source": "eitaa_contact_sync",
                        "sendable": True,
                        "category_ids": category_ids,
                    },
                    safe_reason_code="eitaa_contact_sync",
                ))
                synced_local += 1

        filtered = all_contacts
        if search:
            filtered = tuple(
                item for item in all_contacts
                if search in " ".join(
                    str(item.get(key) or "")
                    for key in ("display_name", "phone", "username")
                ).casefold()
            )
        total = len(filtered)
        raw_page = filtered[offset: offset + limit]
        local_contacts = self._contact_validation(
            lambda: self._contact_store.find_contacts_by_eitaa_identity(
                eitaa_user_ids=[int(item["user_id"]) for item in raw_page],
                phones=[item["phone"] for item in raw_page if item.get("phone")],
                messenger_account_id=self._runtime.ownership.messenger_account_id,
                include_legacy_global_identity=self._allow_legacy_contact_identity(),
            )
        )
        local_by_eitaa_id = {
            int(item["eitaa_user_id"]): item
            for item in local_contacts
            if item.get("eitaa_user_id") not in (None, "")
        }
        local_by_phone: dict[str, Mapping[str, Any]] = {}
        for local_contact in local_contacts:
            for phone_value in local_contact.get("phones") or ():
                try:
                    local_by_phone[normalize_phone(phone_value)] = local_contact
                except ValueError:
                    continue

        page: list[dict[str, Any]] = []
        for cached_contact in raw_page:
            item = dict(cached_contact)
            local_contact = local_by_eitaa_id.get(int(item["user_id"]))
            if local_contact is None and item.get("phone"):
                try:
                    local_contact = local_by_phone.get(normalize_phone(item["phone"]))
                except ValueError:
                    local_contact = None
            item["local_contact_id"] = int(local_contact["id"]) if local_contact else None
            item["local_categories"] = list(local_contact.get("categories") or ()) if local_contact else []
            page.append(item)
        return {
            "ok": True,
            "contacts": page,
            "count": len(page),
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": offset + len(page) < total,
            "not_modified": not_modified,
            "source": "eitaa_server_contact_book",
            "synced_local": synced_local,
            "cache_hit": cached_contacts is not None,
        }

    def _eitaa_contacts_add(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        if "messenger_account_id" in payload or "account_id" in payload:
            raise CompositionValidationError(
                "The target account must come from the authenticated account selector.",
                code="api_contact_target_account_not_trusted",
            )
        site_key = self._site_key(payload)
        phone = str(payload.get("phone") or "").strip()
        first_name = str(payload.get("first_name") or "").strip()
        last_name = str(payload.get("last_name") or "").strip()
        if not phone:
            raise CompositionValidationError("phone is required.", code="api_contact_phone_required")
        if not first_name:
            raise CompositionValidationError(
                "first_name is required.", code="api_contact_first_name_required"
            )

        def operation() -> dict[str, Any]:
            with self._open_bridge(
                self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
            ) as bridge:
                contacts = bridge.core.contacts
                normalized_phone = PhoneNumber.parse(phone)
                existing = contacts.find(normalized_phone, refresh=True)
                existing_names = (
                    (
                        str(existing.user.first_name or "").strip(),
                        str(existing.user.last_name or "").strip(),
                    )
                    if existing is not None
                    else None
                )
                requested_names = (first_name, last_name)
                if existing is not None and existing_names != requested_names:
                    # ContactService.resolve() intentionally short-circuits for
                    # an existing phone. That is correct for sending, but it
                    # leaves placeholder names such as "Eitaa" unchanged.
                    # Re-import the same phone explicitly: contacts.importContacts
                    # is an upsert and updates the contact-book name without
                    # creating a second Eitaa user/contact.
                    imported = contacts.repository.import_contact(
                        normalized_phone,
                        first_name=first_name,
                        last_name=last_name,
                    )
                    if imported.retry_client_ids:
                        raise CompositionValidationError(
                            "Eitaa requested a later retry while updating the contact name.",
                            code="api_eitaa_contact_name_update_retry",
                        )
                    refreshed = contacts.find(normalized_phone, refresh=True)
                    if refreshed is None:
                        raise CompositionValidationError(
                            "Eitaa did not return the contact after updating its name.",
                            code="api_eitaa_contact_name_update_missing",
                        )
                    return {
                        "contact": self._eitaa_contact_payload(refreshed),
                        "contact_added": False,
                        "contact_updated": True,
                        "source": "existing_updated",
                        "access_hash": getattr(refreshed.user.peer, "access_hash", None),
                    }
                resolution = contacts.resolve(
                    normalized_phone,
                    first_name=first_name,
                    last_name=last_name,
                    import_if_missing=True,
                    refresh_contacts=False,
                )
                return {
                    "contact": self._eitaa_contact_payload(resolution.contact),
                    "contact_added": bool(resolution.contact_added),
                    "contact_updated": False,
                    "source": resolution.source.value,
                    "access_hash": getattr(resolution.contact.user.peer, "access_hash", None),
                }

        result = self._run_eitaa(
            priority=EitaaPriority.ACTIVE_MESSAGES,
            kind="contacts.add",
            callback=operation,
            timeout=120.0,
        )
        self._invalidate_eitaa_contacts_cache(site_key)
        if bool(payload.get("save_local", True)):
            contact = result["contact"]
            saved_local = self._contact_validation(lambda: self._upsert_eitaa_local_contact(
                {
                    "phones": [contact["phone"]] if contact.get("phone") else [phone],
                    # The spreadsheet/manual name is authoritative. A stale
                    # server response must never replace it with "Eitaa".
                    "first_name": first_name,
                    "last_name": last_name,
                    "username": contact.get("username") or "",
                    "eitaa_user_id": contact.get("user_id"),
                    "access_hash": str(result.get("access_hash") or ""),
                    "source": "eitaa_contact",
                    "sendable": True,
                    "category_ids": list(self._contact_ids(payload, "category_ids")),
                },
                safe_reason_code=(
                    "eitaa_contact_added"
                    if result.get("contact_added")
                    else "eitaa_contact_updated"
                    if result.get("contact_updated")
                    else "eitaa_contact_existing"
                ),
            ))
            result["local_contact_id"] = int(saved_local["id"])
            if saved_local.get("selected_account_binding"):
                result["selected_account_binding"] = saved_local[
                    "selected_account_binding"
                ]
        result.pop("access_hash", None)
        return {"ok": True, **result}

    def _eitaa_contacts_remove(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._site_key(payload)
        if not bool(payload.get("confirm")):
            raise CompositionValidationError(
                "Explicit confirmation is required.", code="api_contact_remove_confirmation_required"
            )
        phone = str(payload.get("phone") or "").strip()
        if not phone:
            raise CompositionValidationError("phone is required.", code="api_contact_phone_required")

        def operation() -> dict[str, Any]:
            with self._open_bridge(
                self.config_path, env_file=self.env_file, site_key=self._site_key(payload), open_core=True
            ) as bridge:
                result = bridge.core.contacts.remove(phone)
                return {"ok": True, "result": result.safe_summary()}

        response = self._run_eitaa(
            priority=EitaaPriority.ACTIVE_MESSAGES,
            kind="contacts.remove",
            callback=operation,
            timeout=120.0,
        )
        self._invalidate_eitaa_contacts_cache(self._site_key(payload))
        return response

    def _eitaa_contacts_categorize(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._site_key(payload)
        operation = str(payload.get("operation") or "add").strip().lower()
        if operation not in {"add", "remove", "replace"}:
            raise CompositionValidationError(
                "Category operation must be add, remove, or replace.",
                code="api_invalid_eitaa_contact_category_operation",
            )
        category_ids = self._contact_ids(payload, "category_ids")
        if not category_ids:
            raise CompositionValidationError(
                "Select at least one local contact category.",
                code="api_eitaa_contact_category_required",
            )
        raw_contacts = payload.get("contacts")
        if not isinstance(raw_contacts, list) or not raw_contacts:
            raise CompositionValidationError(
                "Select at least one Eitaa contact.",
                code="api_eitaa_contact_selection_required",
            )
        if len(raw_contacts) > 500:
            raise CompositionValidationError(
                "At most 500 Eitaa contacts can be categorized at once.",
                code="api_eitaa_contact_category_selection_too_large",
            )

        selected: list[tuple[Mapping[str, Any], int, str]] = []
        for raw_contact in raw_contacts:
            if not isinstance(raw_contact, Mapping):
                raise CompositionValidationError(
                    "Each selected Eitaa contact must be an object.",
                    code="api_invalid_eitaa_contact_selection",
                )
            selected.append((
                raw_contact,
                self._integer(raw_contact.get("user_id"), "user_id", minimum=1),
                str(raw_contact.get("phone") or "").strip(),
            ))

        local_by_user_id: dict[int, dict[str, Any]] = {}
        local_by_phone: dict[str, dict[str, Any]] = {}
        if operation == "remove":
            local_matches = self._contact_store.find_contacts_by_eitaa_identity(
                eitaa_user_ids=[item[1] for item in selected],
                phones=[item[2] for item in selected if item[2]],
                messenger_account_id=self._runtime.ownership.messenger_account_id,
                include_legacy_global_identity=self._allow_legacy_contact_identity(),
            )
            for local_contact in local_matches:
                local_user_id = local_contact.get("eitaa_user_id")
                if local_user_id is not None:
                    local_by_user_id[int(local_user_id)] = local_contact
                for local_phone in local_contact.get("phones") or ():
                    local_by_phone[normalize_phone(local_phone)] = local_contact
            if self._runtime.ownership.messenger_account_id:
                for _, selected_user_id, _ in selected:
                    identity_match = self._contact_store.find_contacts_by_eitaa_identity(
                        eitaa_user_ids=(selected_user_id,),
                        messenger_account_id=self._runtime.ownership.messenger_account_id,
                        include_legacy_global_identity=self._allow_legacy_contact_identity(),
                    )
                    if identity_match:
                        local_by_user_id[selected_user_id] = identity_match[0]

        categorized: list[dict[str, Any]] = []
        updated_count = 0
        for raw_contact, user_id, phone in selected:
            if operation == "remove":
                local_contact = local_by_user_id.get(user_id)
                if local_contact is None and phone:
                    try:
                        local_contact = local_by_phone.get(normalize_phone(phone))
                    except ValueError:
                        local_contact = None
                if local_contact is None:
                    categorized.append({
                        "user_id": user_id,
                        "local_contact_id": None,
                        "local_categories": [],
                    })
                    continue
                saved = self._contact_validation(
                    lambda local_contact=local_contact: self._contact_store.update_contact_categories(
                        int(local_contact["id"]),
                        category_ids,
                        operation="remove",
                        context=self._contact_mutation_context(),
                    )
                )
            else:
                saved = self._contact_validation(
                    lambda raw_contact=raw_contact, user_id=user_id, phone=phone:
                    self._upsert_eitaa_local_contact(
                        {
                            "phones": [phone] if phone else [],
                            "first_name": str(raw_contact.get("first_name") or "").strip(),
                            "last_name": str(raw_contact.get("last_name") or "").strip(),
                            "username": str(raw_contact.get("username") or "").strip(),
                            "eitaa_user_id": user_id,
                            "source": "eitaa_contact_local_category",
                            "sendable": True,
                            "category_ids": list(category_ids),
                        },
                        category_policy="merge" if operation == "add" else "replace",
                        safe_reason_code="eitaa_contact_categorized",
                    )
                )
            updated_count += 1
            categorized.append(
                {
                    "user_id": user_id,
                    "local_contact_id": int(saved["id"]),
                    "local_categories": list(saved.get("categories") or ()),
                }
            )
        return {
            "ok": True,
            "categorized_count": len(categorized),
            "updated_count": updated_count,
            "operation": operation,
            "contacts": categorized,
        }

    def _contacts_add_to_messenger_start(
        self, payload: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Provider-neutral handoff pinned to the server-selected account runtime."""

        if "messenger_account_id" in payload or "account_id" in payload:
            raise CompositionValidationError(
                "The target account must come from the authenticated account selector.",
                code="api_contact_target_account_not_trusted",
            )
        descriptor = provider_adapter_catalog()["eitaa"]
        if not descriptor.configured:
            raise CompositionValidationError(
                "The selected messaging provider is not configured.",
                code=descriptor.reason_code or "provider_adapter_not_configured",
            )
        response = self._eitaa_contacts_import_local_start(payload)
        response["provider"] = "eitaa"
        response["messenger_account_id"] = self._runtime.ownership.messenger_account_id
        return response

    def _eitaa_contacts_import_local_start(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        if "messenger_account_id" in payload or "account_id" in payload:
            raise CompositionValidationError(
                "The target account must come from the authenticated account selector.",
                code="api_contact_target_account_not_trusted",
            )
        site_key = self._site_key(payload)
        contact_ids = self._contact_ids(payload, "contact_ids")
        category_ids = self._contact_ids(payload, "category_ids")
        if not contact_ids and not category_ids:
            raise CompositionValidationError(
                "Select contacts or at least one local category.",
                code="api_eitaa_contact_import_selection_required",
            )
        selected = self._contact_store.get_contacts(contact_ids) if contact_ids else self._contact_store.list_contacts(
            category_ids=category_ids, limit=5_000
        )
        if len(selected) > 5_000:
            raise CompositionValidationError(
                "At most 5000 local contacts can be queued.",
                code="api_eitaa_contact_import_too_large",
            )

        def runner(cancellation: threading.Event, update_progress: Any) -> dict[str, Any]:
            added = updated = existing = failed = skipped = processed = 0
            first_failure: dict[str, Any] | None = None
            update_progress({
                "total": len(selected), "eitaa_added": 0, "eitaa_updated": 0,
                "eitaa_existing": 0, "eitaa_failed": 0,
            })
            for item in selected:
                if cancellation.is_set():
                    return {
                        "processed": processed, "eitaa_added": added,
                        "eitaa_updated": updated, "eitaa_existing": existing,
                        "eitaa_failed": failed, "skipped": skipped,
                        "cancelled": True,
                    }
                phones = list(item.get("phones") or [])
                if not phones:
                    skipped += 1
                    processed += 1
                    continue
                first_name = str(item.get("first_name") or "").strip()
                last_name = str(item.get("last_name") or "").strip()
                if not first_name:
                    skipped += 1
                    processed += 1
                    if processed % 5 == 0 or processed == len(selected):
                        update_progress({
                            "processed": processed, "eitaa_added": added,
                            "eitaa_updated": updated, "eitaa_existing": existing,
                            "eitaa_failed": failed,
                            "skipped": skipped,
                        })
                    continue
                phone = str(phones[0])
                try:
                    result = self._eitaa_contacts_add({
                        "site_key": site_key,
                        "phone": phone,
                        "first_name": first_name,
                        "last_name": last_name,
                        "save_local": True,
                        "category_ids": [int(category["id"]) for category in item.get("categories", [])],
                    })
                    if result.get("contact_added"):
                        added += 1
                    elif result.get("contact_updated"):
                        updated += 1
                    else:
                        existing += 1
                except Exception as exc:
                    failed += 1
                    error = self._contact_job_error(
                        exc, fallback="Adding this contact to Eitaa failed."
                    )
                    if first_failure is None:
                        first_failure = error
                    self._runtime_logger.emit(
                        "eitaa_contact_import_item_failed",
                        level="error",
                        fields={
                            "contact_id": int(item["id"]),
                            "app_user_id": self._request_actor_app_user_id.get(),
                            "messenger_account_id": self._runtime.ownership.messenger_account_id,
                            **{
                                key: value
                                for key, value in error.items()
                                if key != "message"
                            },
                        },
                    )
                    # A rejected session cannot recover by trying the remaining
                    # contacts and must be surfaced immediately to the login UI.
                    if self._is_invalid_session_error(exc):
                        raise
                processed += 1
                if processed % 5 == 0 or processed == len(selected):
                    update_progress({
                        "processed": processed, "eitaa_added": added,
                        "eitaa_updated": updated, "eitaa_existing": existing,
                        "eitaa_failed": failed, "skipped": skipped,
                    })
            if failed and not (added or updated or existing):
                first_failure = first_failure or {
                    "message": "Adding contacts to Eitaa failed.",
                    "error_type": "UnknownError",
                    "error_code": "eitaa_contact_import_failed",
                }
                raise ContactDirectoryError(
                    str(first_failure["message"]),
                    safe_context={
                        "failed_count": failed,
                        "error_type": first_failure.get("error_type"),
                        "error_code": first_failure.get("error_code"),
                    },
                    code="eitaa_contact_import_all_failed",
                )
            return {
                "processed": processed, "eitaa_added": added,
                "eitaa_updated": updated, "eitaa_existing": existing,
                "eitaa_failed": failed, "skipped": skipped, "cancelled": False,
            }

        response = self._start_contact_source_import(
            kind="eitaa_contact_import",
            source_label="local-contact-directory",
            runner=runner,
        )
        with self._contact_import_lock:
            job = self._contact_import_jobs[response["job"]["job_id"]]
            job["local_only"] = False
            job["remote_operation"] = "contacts.importContacts"
            job["provider"] = "eitaa"
            job["messenger_account_id"] = self._runtime.ownership.messenger_account_id
            response["job"] = dict(job)
        return response

    @staticmethod
    def _contact_ids(payload: Mapping[str, Any], field: str) -> tuple[int, ...]:
        raw = payload.get(field, [])
        if raw is None:
            return ()
        if not isinstance(raw, list):
            raise CompositionValidationError(
                f"{field} must be a list.", code="api_invalid_contact_ids"
            )
        try:
            selected = tuple(dict.fromkeys(int(value) for value in raw))
        except (TypeError, ValueError) as exc:
            raise CompositionValidationError(
                f"{field} must contain integers.", code="api_invalid_contact_ids"
            ) from exc
        if any(value <= 0 for value in selected) or len(selected) > 50_000:
            raise CompositionValidationError(
                f"{field} contains an invalid value.", code="api_invalid_contact_ids"
            )
        return selected

    @staticmethod
    def _contact_validation(call: Any) -> Any:
        try:
            return call()
        except ValueError as exc:
            raise CompositionValidationError(
                str(exc), code="api_invalid_contact_directory_request"
            ) from exc

    def _contacts_list(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        search = str(payload.get("search") or "").strip()[:300]
        category_ids = self._contact_ids(payload, "category_ids")
        limit = self._integer(
            payload.get("limit", 250), "limit", minimum=1, maximum=2_000
        )
        offset = self._integer(payload.get("offset", 0), "offset", minimum=0, maximum=1_000_000)
        contacts = self._contact_validation(
            lambda: self._contact_store.list_contacts(
                search=search, category_ids=category_ids, limit=limit, offset=offset
            )
        )
        total = self._contact_validation(
            lambda: self._contact_store.count_contacts(search=search, category_ids=category_ids)
        )
        visible_contacts = self._with_selected_contact_bindings(contacts)
        return {
            "ok": True,
            "contacts": visible_contacts,
            "count": len(visible_contacts),
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": offset + len(contacts) < total,
            "shared_directory": True,
            "categories_shared": True,
        }

    def _contacts_audit(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        contact_id = (
            self._integer(payload.get("contact_id"), "contact_id", minimum=1)
            if payload.get("contact_id") is not None
            else None
        )
        limit = self._integer(payload.get("limit", 100), "limit", minimum=1, maximum=2_000)
        events = self._contact_validation(
            lambda: self._contact_store.list_audit_events(
                contact_id=contact_id,
                limit=limit,
            )
        )
        selected_account_id = self._runtime.ownership.messenger_account_id
        safe_events: list[dict[str, Any]] = []
        for event in events:
            safe_event = dict(event)
            event_account_id = safe_event.get("messenger_account_id")
            if event_account_id and event_account_id != selected_account_id:
                # The shared audit may describe edits made from another
                # workspace, but its account identifier is not shared data.
                safe_event["messenger_account_id"] = None
                safe_event["account_context"] = "different_account"
            elif event_account_id:
                safe_event["account_context"] = "selected_account"
            else:
                safe_event["account_context"] = "shared_directory"
            safe_events.append(safe_event)
        return {
            "ok": True,
            "events": safe_events,
            "count": len(safe_events),
            "chain_valid": self._contact_store.verify_audit_chain(),
        }

    def _contacts_upsert(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        contact = payload.get("contact")
        if not isinstance(contact, Mapping):
            raise CompositionValidationError(
                "contact must be an object.", code="api_contact_required"
            )
        if "eitaa_user_id" in contact or "access_hash" in contact:
            raise CompositionValidationError(
                "Provider-managed identity cannot be written through the shared contact API.",
                code="api_contact_provider_identity_not_writable",
            )
        if bool(payload.get("add_to_eitaa", False)) and (
            "messenger_account_id" in payload or "account_id" in payload
        ):
            raise CompositionValidationError(
                "The target account must come from the authenticated account selector.",
                code="api_contact_target_account_not_trusted",
            )
        saved = self._contact_validation(
            lambda: self._contact_store.upsert_contact(
                contact,
                duplicate_policy=str(payload.get("duplicate_policy") or "skip"),
                context=self._contact_mutation_context(),
            )
        )
        saved = self._with_selected_contact_bindings([saved])[0]
        response: dict[str, Any] = {"ok": True, "contact": saved, "eitaa_added": False}
        if bool(payload.get("add_to_eitaa", False)):
            phones = list(saved.get("phones") or [])
            if not phones:
                raise CompositionValidationError(
                    "A phone number is required to add this person to Eitaa contacts.",
                    code="api_contact_phone_required_for_eitaa",
                )
            remote = self._eitaa_contacts_add({
                "site_key": self._site_key(payload),
                "phone": str(phones[0]),
                "first_name": str(saved.get("first_name") or "").strip() or "مخاطب",
                "last_name": str(saved.get("last_name") or "").strip(),
                "save_local": True,
                "category_ids": [int(item["id"]) for item in saved.get("categories", [])],
            })
            response["eitaa_added"] = bool(remote.get("contact_added"))
            response["eitaa_contact"] = remote.get("contact")
            refreshed = self._contact_store.get_contacts(
                (int(remote.get("local_contact_id") or saved["id"]),)
            )
            if refreshed:
                response["contact"] = self._with_selected_contact_bindings(
                    list(refreshed)
                )[0]
        return response

    def _contacts_archive(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        contact_id = self._integer(payload.get("contact_id"), "contact_id", minimum=1)
        if payload.get("confirm") is not True:
            raise CompositionValidationError(
                "Explicit archive confirmation is required.",
                code="api_contact_archive_confirmation_required",
            )
        self._contact_validation(
            lambda: self._contact_store.archive_contact(
                contact_id,
                context=self._contact_mutation_context(),
            )
        )
        return {"ok": True, "contact_id": contact_id, "archived": True}

    def _contact_categories(self) -> dict[str, Any]:
        categories = self._contact_store.list_categories()
        return {"ok": True, "categories": list(categories)}

    def _contact_category_save(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        category_id = (
            self._integer(payload.get("category_id"), "category_id", minimum=1)
            if payload.get("category_id") is not None
            else None
        )
        category = self._contact_validation(
            lambda: self._contact_store.save_category(
                name=str(payload.get("name") or ""),
                category_id=category_id,
                context=self._contact_mutation_context(),
            )
        )
        return {"ok": True, "category": category}

    def _contact_category_delete(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        category_id = self._integer(payload.get("category_id"), "category_id", minimum=1)
        if payload.get("confirm") is not True:
            raise CompositionValidationError(
                "Explicit category deletion confirmation is required.",
                code="api_contact_category_delete_confirmation_required",
            )
        self._contact_validation(
            lambda: self._contact_store.delete_category(
                category_id,
                context=self._contact_mutation_context(),
            )
        )
        return {
            "ok": True,
            "category_id": category_id,
            "deleted": True,
            "contacts_deleted": 0,
        }

    @staticmethod
    def _contact_import_bytes(payload: Mapping[str, Any]) -> tuple[bytes, str]:
        encoded = payload.get("content_base64")
        file_name = str(payload.get("file_name") or "").strip()
        if not isinstance(encoded, str) or not encoded or not file_name:
            raise CompositionValidationError(
                "file_name and content_base64 are required.",
                code="api_contact_import_file_required",
            )
        try:
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise CompositionValidationError(
                "Contact import content is not valid base64.",
                code="api_invalid_contact_import_content",
            ) from exc
        return content, file_name[:260]

    def _contact_import_preview(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        content, file_name = self._contact_import_bytes(payload)
        headers, rows = self._contact_validation(lambda: parse_tabular(content, file_name))
        return {
            "ok": True,
            "file_name": file_name,
            "headers": headers,
            "rows": rows[:50],
            "row_count": len(rows),
            "preview_truncated": len(rows) > 50,
        }

    def _contact_import_start(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        content, file_name = self._contact_import_bytes(payload)
        mapping = payload.get("mapping")
        if not isinstance(mapping, Mapping):
            raise CompositionValidationError(
                "mapping must be an object.", code="api_contact_import_mapping_required"
            )
        category_ids = self._contact_ids(payload, "category_ids")
        add_to_eitaa = bool(payload.get("add_to_eitaa", False))
        if add_to_eitaa and (
            "messenger_account_id" in payload or "account_id" in payload
        ):
            raise CompositionValidationError(
                "The target account must come from the authenticated account selector.",
                code="api_contact_target_account_not_trusted",
            )
        if add_to_eitaa and mapping.get("first_name") in (None, ""):
            raise CompositionValidationError(
                "Map a first-name column before adding spreadsheet rows to Eitaa.",
                code="api_contact_import_first_name_mapping_required",
            )
        site_key = self._site_key(payload)
        job_id = self._persistent_job_create("contacts.import")
        cancellation = threading.Event()
        job: dict[str, Any] = {
            "job_id": job_id,
            "kind": "local_contact_import",
            "state": "queued",
            "local_only": not add_to_eitaa,
            "remote_operation": "contacts.importContacts" if add_to_eitaa else None,
            "file_name": file_name,
            "progress": {"processed": 0, "imported": 0, "duplicates": 0, "errors": 0},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._contact_import_lock:
            self._contact_import_jobs[job_id] = job
            self._contact_import_cancellations[job_id] = cancellation
        threading.Thread(
            target=self._runtime_bound_target(self._run_contact_import),
            args=(job_id, content, file_name, dict(mapping), category_ids, cancellation, add_to_eitaa, site_key),
            name=f"local-contact-import-{job_id[:8]}",
            daemon=True,
        ).start()
        return {"ok": True, "job": dict(job)}

    def _run_contact_import(
        self,
        job_id: str,
        content: bytes,
        file_name: str,
        mapping: Mapping[str, object],
        category_ids: tuple[int, ...],
        cancellation: threading.Event,
        add_to_eitaa: bool,
        site_key: str,
    ) -> None:
        with self._contact_import_lock:
            self._contact_import_jobs[job_id]["state"] = "running"
        self._runtime_logger.emit(
            "contact_import_started",
            fields={
                "job_id": job_id,
                "file_suffix": Path(file_name).suffix.lower(),
                "file_size_bytes": len(content),
                "category_count": len(category_ids),
                "add_to_eitaa": add_to_eitaa,
            },
        )

        def update_progress(progress: Mapping[str, object]) -> None:
            with self._contact_import_lock:
                current = self._contact_import_jobs.get(job_id)
                if current is not None:
                    current["progress"] = {**current["progress"], **dict(progress)}

        try:
            self._persistent_job_begin(job_id)
            headers, raw_rows = parse_tabular(content, file_name)
            rows = map_contact_rows(headers, raw_rows, mapping)
            category_by_name = {
                str(item["name"]).strip().casefold(): int(item["id"])
                for item in self._contact_store.list_categories()
            }
            for row in rows:
                row_category_ids: list[int] = []
                for name in row.pop("category_names", []):
                    key = str(name).strip().casefold()
                    category_id = category_by_name.get(key)
                    if category_id is None:
                        created = self._contact_store.save_category(
                            name=str(name),
                            context=self._contact_mutation_context(),
                        )
                        category_id = int(created["id"])
                        category_by_name[key] = category_id
                    row_category_ids.append(category_id)
                row["category_ids"] = row_category_ids
            update_progress({"total": len(rows)})
            result = self._contact_store.import_rows(
                rows,
                category_ids=category_ids,
                duplicate_policy="update",
                category_policy="merge",
                status_policy="preserve",
                cancel_event=cancellation,
                progress=update_progress,
                context=self._contact_mutation_context(),
            )
            self._runtime_logger.emit(
                "contact_import_local_completed",
                fields={
                    "job_id": job_id,
                    "processed": int(result.get("processed") or 0),
                    "imported": int(result.get("imported") or 0),
                    "updated": int(result.get("updated") or 0),
                    "duplicates": int(result.get("duplicates") or 0),
                    "errors": int(result.get("errors") or 0),
                    "selected_contact_count": len(result.get("contact_ids") or ()),
                    "cancelled": bool(result.get("cancelled")),
                },
            )
            if add_to_eitaa and not result.get("cancelled"):
                # This value crosses the same validation boundary as a JSON API
                # request, which deliberately accepts arrays (lists) only.
                # Passing a tuple here used to fail after the local import had
                # already succeeded and before the first Eitaa RPC was issued.
                selected_ids = [int(value) for value in result.get("contact_ids", [])]
                remote = self._eitaa_contacts_import_local_start({
                    "site_key": site_key,
                    "contact_ids": selected_ids,
                })
                remote_job_id = str(remote["job"]["job_id"])
                while True:
                    if cancellation.is_set():
                        self._contact_import_cancel({"job_id": remote_job_id})
                    remote_status = self._contact_import_status({"job_id": remote_job_id})["job"]
                    remote_progress = dict(remote_status.get("progress") or {})
                    update_progress({
                        "eitaa_processed": int(remote_progress.get("processed") or 0),
                        "eitaa_total": int(remote_progress.get("total") or len(selected_ids)),
                        "eitaa_added": int(remote_progress.get("eitaa_added") or 0),
                        "eitaa_existing": int(remote_progress.get("eitaa_existing") or 0),
                        "eitaa_failed": int(remote_progress.get("eitaa_failed") or 0),
                    })
                    if remote_status.get("state") in {"completed", "cancelled", "failed"}:
                        result["remote_state"] = remote_status.get("state")
                        result.update({key: value for key, value in remote_progress.items() if key.startswith("eitaa_")})
                        if remote_status.get("state") == "cancelled":
                            result["cancelled"] = True
                        elif remote_status.get("state") == "failed":
                            remote_error = dict(remote_status.get("error") or {})
                            raise ContactDirectoryError(
                                str(remote_error.get("message") or "Adding contacts to Eitaa failed."),
                                safe_context={
                                    "remote_job_id": remote_job_id,
                                    "remote_error_type": remote_error.get("error_type"),
                                    "remote_error_code": remote_error.get("error_code"),
                                },
                                code=str(
                                    remote_error.get("error_code")
                                    or "eitaa_contact_import_failed"
                                ),
                            )
                        break
                    time.sleep(0.25)
            result.pop("contact_ids", None)
            with self._contact_import_lock:
                job = self._contact_import_jobs[job_id]
                job["progress"] = {**job["progress"], **result}
                job["state"] = "cancelled" if result.get("cancelled") else "completed"
                job["completed_at"] = datetime.now(timezone.utc).isoformat()
            self._persistent_job_finish(
                job_id,
                state="cancelled" if result.get("cancelled") else "completed",
            )
            self._runtime_logger.emit(
                "contact_import_completed",
                fields={
                    "job_id": job_id,
                    "state": "cancelled" if result.get("cancelled") else "completed",
                    "processed": int(result.get("processed") or 0),
                    "imported": int(result.get("imported") or 0),
                    "updated": int(result.get("updated") or 0),
                    "errors": int(result.get("errors") or 0),
                    "remote_state": result.get("remote_state"),
                    "eitaa_added": int(result.get("eitaa_added") or 0),
                    "eitaa_updated": int(result.get("eitaa_updated") or 0),
                    "eitaa_existing": int(result.get("eitaa_existing") or 0),
                    "eitaa_failed": int(result.get("eitaa_failed") or 0),
                },
            )
        except Exception as exc:
            error = self._contact_job_error(exc, fallback="Local contact import failed.")
            with self._contact_import_lock:
                job = self._contact_import_jobs[job_id]
                job["state"] = "failed"
                job["error"] = error
                job["completed_at"] = datetime.now(timezone.utc).isoformat()
            self._persistent_job_finish(
                job_id,
                state="failed",
                error_code=str(error.get("error_code") or "contact_import_failed"),
            )
            self._runtime_logger.emit(
                "contact_import_failed",
                level="error",
                fields={
                    "job_id": job_id,
                    **{key: value for key, value in error.items() if key != "message"},
                },
            )
        finally:
            with self._contact_import_lock:
                self._contact_import_cancellations.pop(job_id, None)

    @staticmethod
    def _contact_job_error(
        exc: Exception,
        *,
        fallback: str,
    ) -> dict[str, Any]:
        """Return a user-safe job error plus stable diagnostic identifiers."""

        if isinstance(exc, BridgeError):
            return {
                "message": exc.message,
                "error_type": type(exc).__name__,
                "error_code": exc.code,
                "component": exc.component,
                "safe_context": dict(exc.safe_context),
                "debug_file": exc.debug_file,
            }
        if isinstance(exc, EitaaCoreError):
            return {
                "message": exc.message,
                "error_type": type(exc).__name__,
                "error_code": f"core_{type(exc).__name__.removesuffix('Error').lower()}",
                "component": exc.component,
                "safe_context": dict(exc.safe_context),
                "debug_file": exc.debug_file,
            }
        if isinstance(exc, ValueError):
            return {
                "message": str(exc),
                "error_type": type(exc).__name__,
                "error_code": "contact_import_value_error",
                "component": "contact_directory",
                "safe_context": {},
                "debug_file": None,
            }
        return {
            "message": fallback,
            "error_type": type(exc).__name__,
            "error_code": "contact_import_internal_error",
            "component": "contact_directory",
            "safe_context": {},
            "debug_file": None,
        }

    def _start_contact_source_import(
        self,
        *,
        kind: str,
        source_label: str,
        runner: Any,
    ) -> dict[str, Any]:
        """Start a local SQLite-to-SQLite import without occupying the Eitaa scheduler."""

        job_id = self._persistent_job_create("contacts.source_import")
        cancellation = threading.Event()
        job: dict[str, Any] = {
            "job_id": job_id,
            "kind": kind,
            "state": "queued",
            "local_only": True,
            "source_label": source_label[:260],
            "progress": {
                "processed": 0,
                "imported": 0,
                "updated": 0,
                "duplicates": 0,
                "errors": 0,
                "skipped": 0,
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._contact_import_lock:
            self._contact_import_jobs[job_id] = job
            self._contact_import_cancellations[job_id] = cancellation

        def run() -> None:
            with self._contact_import_lock:
                self._contact_import_jobs[job_id]["state"] = "running"
            self._runtime_logger.emit(
                "contact_source_import_started",
                fields={
                    "job_id": job_id,
                    "kind": kind,
                    "source_label": source_label,
                },
            )

            def update_progress(progress: Mapping[str, object]) -> None:
                with self._contact_import_lock:
                    current = self._contact_import_jobs.get(job_id)
                    if current is not None:
                        current["progress"] = {
                            **current["progress"],
                            **dict(progress),
                        }

            try:
                self._persistent_job_begin(job_id)
                result = runner(cancellation, update_progress)
                with self._contact_import_lock:
                    current = self._contact_import_jobs[job_id]
                    current["progress"] = {**current["progress"], **dict(result)}
                    current["state"] = (
                        "cancelled" if result.get("cancelled") else "completed"
                    )
                    current["completed_at"] = datetime.now(timezone.utc).isoformat()
                self._persistent_job_finish(
                    job_id,
                    state="cancelled" if result.get("cancelled") else "completed",
                )
                self._runtime_logger.emit(
                    "contact_source_import_completed",
                    fields={
                        "job_id": job_id,
                        "kind": kind,
                        "state": (
                            "cancelled" if result.get("cancelled") else "completed"
                        ),
                        "processed": int(result.get("processed") or 0),
                        "eitaa_added": int(result.get("eitaa_added") or 0),
                        "eitaa_updated": int(result.get("eitaa_updated") or 0),
                        "eitaa_existing": int(result.get("eitaa_existing") or 0),
                        "eitaa_failed": int(result.get("eitaa_failed") or 0),
                        "skipped": int(result.get("skipped") or 0),
                    },
                )
            except Exception as exc:
                error = self._contact_job_error(
                    exc, fallback="Local contact source import failed."
                )
                with self._contact_import_lock:
                    current = self._contact_import_jobs[job_id]
                    current["state"] = "failed"
                    current["error"] = error
                    current["completed_at"] = datetime.now(timezone.utc).isoformat()
                self._persistent_job_finish(
                    job_id,
                    state="failed",
                    error_code=str(error.get("error_code") or "contact_source_import_failed"),
                )
                self._runtime_logger.emit(
                    "contact_source_import_failed",
                    level="error",
                    fields={
                        "job_id": job_id,
                        "kind": kind,
                        **{key: value for key, value in error.items() if key != "message"},
                    },
                )
            finally:
                with self._contact_import_lock:
                    self._contact_import_cancellations.pop(job_id, None)

        threading.Thread(
            target=self._runtime_bound_target(run),
            name=f"local-contact-source-{job_id[:8]}",
            daemon=True,
        ).start()
        return {"ok": True, "job": dict(job)}

    @staticmethod
    def _contact_source_row(
        user: Any,
        *,
        phones: list[str],
        source: str,
        sendable: bool,
        category_ids: tuple[int, ...],
        last_resolved_at: str | None = None,
    ) -> dict[str, Any]:
        peer = user.peer
        row: dict[str, Any] = {
            "phones": phones,
            "eitaa_user_id": int(peer.id),
            "source": source,
            "sendable": bool(sendable),
            "category_ids": list(category_ids),
        }
        first_name = str(user.first_name or "").strip()
        last_name = str(user.last_name or "").strip()
        username = str(user.username or peer.username or "").strip()
        if first_name:
            row["first_name"] = first_name
        if last_name:
            row["last_name"] = last_name
        if username:
            row["username"] = username
        if peer.access_hash is not None:
            row["access_hash"] = str(peer.access_hash)
        if last_resolved_at is not None:
            row["last_resolved_at"] = last_resolved_at
        return row

    def _contact_community_import_start(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        community = load_peer_file(self._peer_path(payload))
        if community.type not in {PeerType.CHAT, PeerType.CHANNEL}:
            raise CompositionValidationError(
                "Contact source must be a group or channel.",
                code="api_contact_community_required",
            )
        member_ids = self._member_ids(payload)
        selected_ids = (
            tuple(dict.fromkeys(member_ids)) if member_ids is not None else None
        )
        if selected_ids is not None and len(selected_ids) > 50_000:
            raise CompositionValidationError(
                "Contact member selection exceeds 50000 entries.",
                code="api_contact_member_selection_too_large",
            )
        category_ids = self._contact_ids(payload, "category_ids")
        include_bots = bool(payload.get("include_bots", False))
        source = f"community:{community.type.value}:{community.id}"

        def runner(
            cancellation: threading.Event,
            update_progress: Any,
        ) -> dict[str, Any]:
            imported = updated = duplicates = errors = processed = skipped = 0
            selected = set(selected_ids) if selected_ids is not None else None
            found: set[int] = set()
            offset = 0
            page_size = 1_000
            # search_local and contact upserts are local SQLite operations. They
            # deliberately bypass the single remote-RPC scheduler.
            with self._open_bridge(
                self.config_path,
                env_file=self.env_file,
                site_key=site_key,
                open_core=True,
            ) as bridge:
                while True:
                    if cancellation.is_set():
                        return {
                            "processed": processed,
                            "imported": imported,
                            "updated": updated,
                            "duplicates": duplicates,
                            "errors": errors,
                            "skipped": skipped,
                            "cancelled": True,
                        }
                    page = bridge.core.members.search_local(
                        MemberSearchQuery(
                            community=community,
                            states=(MemberState.ACTIVE,),
                            include_bots=include_bots,
                            offset=offset,
                            limit=page_size,
                        )
                    )
                    if offset == 0:
                        update_progress(
                            {
                                "total": (
                                    len(selected)
                                    if selected is not None
                                    else int(page.total_count)
                                )
                            }
                        )
                    for member in page.members:
                        member_id = int(member.user.peer.id)
                        if selected is not None and member_id not in selected:
                            continue
                        if cancellation.is_set():
                            return {
                                "processed": processed,
                                "imported": imported,
                                "updated": updated,
                                "duplicates": duplicates,
                                "errors": errors,
                                "skipped": skipped,
                                "cancelled": True,
                            }
                        found.add(member_id)
                        processed += 1
                        try:
                            saved = self._upsert_eitaa_local_contact(
                                self._contact_source_row(
                                    member.user,
                                    phones=(
                                        [str(member.user.phone)]
                                        if member.user.phone is not None
                                        else []
                                    ),
                                    source=source,
                                    sendable=member.is_sendable,
                                    category_ids=category_ids,
                                ),
                                category_policy="merge",
                                safe_reason_code="eitaa_community_contact_observed",
                            )
                            if saved.get("duplicate"):
                                duplicates += 1
                            elif saved.get("merged"):
                                updated += 1
                            else:
                                imported += 1
                        except (TypeError, ValueError):
                            errors += 1
                        if processed % 25 == 0:
                            update_progress(
                                {
                                    "processed": processed,
                                    "imported": imported,
                                    "updated": updated,
                                    "duplicates": duplicates,
                                    "errors": errors,
                                    "skipped": skipped,
                                }
                            )
                    if selected is not None and found >= selected:
                        break
                    if not page.members or offset + len(page.members) >= int(page.total_count):
                        break
                    offset += len(page.members)
            if selected is not None:
                skipped += len(selected - found)
            return {
                "processed": processed,
                "imported": imported,
                "updated": updated,
                "duplicates": duplicates,
                "errors": errors,
                "skipped": skipped,
                "cancelled": False,
            }

        return self._start_contact_source_import(
            kind="local_contact_community_import",
            source_label=source,
            runner=runner,
        )

    def _contact_phone_list_import_start(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        list_id = str(payload.get("list_id") or "").strip()
        if not list_id or len(list_id) > 128:
            raise CompositionValidationError(
                "A valid list_id is required.", code="api_list_id_required"
            )
        category_ids = self._contact_ids(payload, "category_ids")
        source = f"phone-list:{list_id}"[:120]

        def runner(
            cancellation: threading.Event,
            update_progress: Any,
        ) -> dict[str, Any]:
            imported = updated = duplicates = errors = processed = skipped = 0
            offset = 0
            page_size = 1_000
            # The public Core entries API is a local SQLite read; no Resolve or
            # other Eitaa RPC is performed by this handoff.
            with self._open_bridge(
                self.config_path,
                env_file=self.env_file,
                site_key=site_key,
                open_core=True,
            ) as bridge:
                phone_list = bridge.core.phone_lists.status(list_id)
                update_progress({"total": int(phone_list.total_rows)})
                while True:
                    if cancellation.is_set():
                        return {
                            "processed": processed,
                            "imported": imported,
                            "updated": updated,
                            "duplicates": duplicates,
                            "errors": errors,
                            "skipped": skipped,
                            "cancelled": True,
                        }
                    entries = bridge.core.phone_lists.entries(
                        list_id, offset=offset, limit=page_size
                    )
                    if not entries:
                        break
                    for entry in entries:
                        if cancellation.is_set():
                            return {
                                "processed": processed,
                                "imported": imported,
                                "updated": updated,
                                "duplicates": duplicates,
                                "errors": errors,
                                "skipped": skipped,
                                "cancelled": True,
                            }
                        processed += 1
                        if entry.user is None or entry.phone is None:
                            skipped += 1
                        else:
                            try:
                                contact_row = self._contact_source_row(
                                    entry.user,
                                    phones=[str(entry.phone)],
                                    source=source,
                                    sendable=(
                                        entry.user.peer.access_hash is not None
                                        and not entry.user.is_deleted
                                    ),
                                    category_ids=category_ids,
                                    last_resolved_at=(
                                        entry.resolved_at.isoformat()
                                        if entry.resolved_at is not None
                                        else None
                                    ),
                                )
                                if not contact_row.get("first_name") and entry.first_name:
                                    contact_row["first_name"] = str(entry.first_name)
                                if not contact_row.get("last_name") and entry.last_name:
                                    contact_row["last_name"] = str(entry.last_name)
                                saved = self._upsert_eitaa_local_contact(
                                    contact_row,
                                    category_policy="merge",
                                    safe_reason_code="eitaa_phone_list_contact_resolved",
                                )
                                if saved.get("duplicate"):
                                    duplicates += 1
                                elif saved.get("merged"):
                                    updated += 1
                                else:
                                    imported += 1
                            except (TypeError, ValueError):
                                errors += 1
                        if processed % 25 == 0:
                            update_progress(
                                {
                                    "processed": processed,
                                    "imported": imported,
                                    "updated": updated,
                                    "duplicates": duplicates,
                                    "errors": errors,
                                    "skipped": skipped,
                                }
                            )
                    offset += len(entries)
                    if len(entries) < page_size:
                        break
            return {
                "processed": processed,
                "imported": imported,
                "updated": updated,
                "duplicates": duplicates,
                "errors": errors,
                "skipped": skipped,
                "cancelled": False,
            }

        return self._start_contact_source_import(
            kind="local_contact_phone_list_import",
            source_label=source,
            runner=runner,
        )

    def _contact_import_status(self, query: Mapping[str, Any]) -> dict[str, Any]:
        job_id = str(query.get("job_id") or "").strip()
        with self._contact_import_lock:
            job = self._contact_import_jobs.get(job_id)
            copied = dict(job) if job is not None else None
            if copied is not None:
                copied["progress"] = dict(job["progress"])
        if copied is None:
            copied = self._persistent_job_snapshot(job_id, kind="contact_import")
        if copied is None:
            raise CompositionValidationError(
                "Contact import job was not found.",
                code="api_contact_import_job_not_found",
            )
        return {"ok": True, "job": copied}

    def _contact_import_cancel(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        job_id = str(payload.get("job_id") or "").strip()
        self._persistent_job_cancel(job_id)
        with self._contact_import_lock:
            job = self._contact_import_jobs.get(job_id)
            if job is not None:
                cancellation = self._contact_import_cancellations.get(job_id)
                if cancellation is not None and job["state"] in {"queued", "running"}:
                    cancellation.set()
                    job["state"] = "cancelling"
                copied = dict(job)
                copied["progress"] = dict(job["progress"])
            else:
                copied = None
        if copied is None:
            copied = self._persistent_job_snapshot(job_id, kind="contact_import")
        if copied is None:
            raise CompositionValidationError(
                "Contact import job was not found.",
                code="api_contact_import_job_not_found",
            )
        return {"ok": True, "job": copied}

    def _contact_targets(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        result = self._contact_validation(
            lambda: self._contact_store.build_targets(
                category_ids=self._contact_ids(payload, "category_ids"),
                include_contact_ids=self._contact_ids(payload, "include_contact_ids"),
                exclude_contact_ids=self._contact_ids(payload, "exclude_contact_ids"),
                max_targets=self._integer(payload.get("max_targets", 10_000), "max_targets", minimum=1, maximum=10_000),
            )
        )
        return {"ok": True, **result}

    def _composition_action(self, payload: Mapping[str, Any], *, action: str) -> dict[str, Any]:
        raw_composition = payload.get("composition", payload)
        if not isinstance(raw_composition, Mapping):
            raise CompositionValidationError(
                "composition must be a JSON object.", code="api_invalid_composition"
            )
        config = BridgeConfigLoader.load(self.config_path, env_file=self.env_file)
        request = CompositionManifestLoader.from_mapping(
            raw_composition,
            base_directory=self.base_directory,
            default_site_key=config.default_site_key,
            site_key_override=None,
        )
        max_media_mb = self._integer(
            payload.get("max_media_mb", 100), "max_media_mb", minimum=1, maximum=self.MAX_MEDIA_MB
        )
        def operation() -> dict[str, Any]:
            with self._open_bridge(
                self.config_path,
                env_file=self.env_file,
                site_key=request.site_key,
                open_core=True,
            ) as bridge:
                if action == "preview":
                    result = bridge.preview_wordpress_composition(request)
                elif action == "status":
                    result = bridge.wordpress_composition_status(request)
                elif action == "update":
                    result = bridge.update_wordpress_composition(
                        request, max_media_bytes=max_media_mb * 1024 * 1024
                    )
                else:
                    result = bridge.publish_wordpress_composition(
                        request, max_media_bytes=max_media_mb * 1024 * 1024
                    )
                return {"ok": True, **result.safe_summary()}

        return self._run_eitaa(
            priority=EitaaPriority.ACTIVE_MESSAGES,
            kind=f"compositions.{action}",
            callback=operation,
        )

    def _site_settings(self) -> WordPressSiteSettings:
        config = BridgeConfigLoader.load(self.config_path, env_file=self.env_file)
        return WordPressSiteSettings(self.config_path, config.env_file)

    def _deployment_port_settings(self) -> DeploymentPortSettings:
        return DeploymentPortSettings(self.config_path)

    def _settings_deployment(
        self,
        *,
        app_session: AuthorizedAppSession | None,
    ) -> dict[str, Any]:
        session = (
            self._require_authorized_session(app_session)
            if self.app_user_auth_enabled
            else None
        )
        can_manage = session is None or session.principal.global_role == "admin"
        return {
            "ok": True,
            "can_manage": can_manage,
            **self._deployment_port_settings().details(),
        }

    def _settings_deployment_port_update(
        self,
        payload: Mapping[str, Any],
        *,
        app_session: AuthorizedAppSession | None,
        request_id: str | None,
    ) -> dict[str, Any]:
        session = (
            self._require_authorized_session(app_session)
            if self.app_user_auth_enabled
            else None
        )
        actor_fields = (
            {"actor_app_user_id": session.principal.app_user_id}
            if session is not None
            else {"actor_kind": "legacy_local"}
        )
        if session is not None and session.principal.global_role != "admin":
            self._application_logger.emit(
                "deployment_port_update_rejected",
                level="warning",
                result="rejected",
                reason_code="app_auth_admin_required",
                correlation_id=request_id,
                fields=actor_fields,
            )
            raise CoordinatorAuthorizationError(
                "Only an administrator can change the internal HTTP port.",
                code="app_auth_admin_required",
            )
        settings = self._deployment_port_settings()
        previous = settings.details()
        try:
            updated = settings.update_port(
                payload.get("port"),
                confirm=payload.get("confirm") is True,
            )
        except BridgeConfigurationError as exc:
            persistence_failure = exc.code in {
                "deployment_settings_backup_failed",
                "deployment_settings_write_failed",
            }
            self._application_logger.emit(
                (
                    "deployment_port_update_failed"
                    if persistence_failure
                    else "deployment_port_update_rejected"
                ),
                level="error" if persistence_failure else "warning",
                result="failed" if persistence_failure else "rejected",
                reason_code=exc.code,
                correlation_id=request_id,
                fields={**actor_fields, "deployment_mode": previous["mode"]},
            )
            raise
        self._application_logger.emit(
            "deployment_port_update_succeeded",
            result="succeeded",
            correlation_id=request_id,
            fields={
                **actor_fields,
                "deployment_mode": updated["mode"],
                "previous_port": previous["bind_port"],
                "new_port": updated["bind_port"],
                "restart_required": True,
                "proxy_update_required": updated["proxy_update_required"],
            },
        )
        return {"ok": True, "can_manage": True, **updated}

    def _settings_sites(self) -> dict[str, Any]:
        return {"ok": True, **self._site_settings().details()}

    def _settings_site_upsert(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return {"ok": True, **self._site_settings().upsert(payload)}

    def _settings_site_default(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = str(payload.get("site_key", "")).strip()
        if not site_key:
            raise CompositionValidationError("site_key is required.", code="api_site_key_required")
        return {"ok": True, **self._site_settings().set_default(site_key)}

    def _settings_site_delete(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = str(payload.get("site_key", "")).strip()
        if not site_key:
            raise CompositionValidationError("site_key is required.", code="api_site_key_required")
        return {
            "ok": True,
            **self._site_settings().delete(site_key, confirm=bool(payload.get("confirm"))),
        }

    def _settings_site_test(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        with self._open_bridge(
            self.config_path, env_file=self.env_file, site_key=site_key, open_core=False
        ) as bridge:
            result = bridge.test_wordpress()
            return {"ok": True, "site_key": site_key, "connection": result.safe_summary()}

    @staticmethod
    def _safe_summary(value: Any) -> Any:
        if hasattr(value, "safe_summary") and callable(value.safe_summary):
            return value.safe_summary()
        if isinstance(value, Mapping):
            return {str(key): BridgeApplicationApi._safe_summary(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [BridgeApplicationApi._safe_summary(item) for item in value]
        if isinstance(value, Path):
            return str(value)
        return value

    def _start_background(
        self,
        *,
        kind: str,
        callback: Any,
        priority: EitaaPriority = EitaaPriority.BACKGROUND,
    ) -> dict[str, Any]:
        task_id = self._persistent_job_create(f"background.{kind}")
        state: dict[str, Any] = {
            "task_id": task_id,
            "kind": kind,
            "status": "queued",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._jobs_lock:
            self._background_tasks[task_id] = state

        def worker() -> None:
            with self._jobs_lock:
                state["status"] = "running"
                state["started_at"] = datetime.now(timezone.utc).isoformat()
            try:
                with self._runtime_logger.observed_operation(
                    f"background.{kind}",
                    fields={"task_id": task_id, "kind": kind},
                ):
                    self._persistent_job_begin(task_id)
                    result = self._run_eitaa(
                        priority=priority,
                        kind=kind,
                        callback=callback,
                    )
            except Exception as exc:
                converted = self._error_response(exc)
                error = converted.payload.get("error") or {}
                with self._jobs_lock:
                    state["status"] = "failed"
                    state["error_type"] = type(exc).__name__
                    state["error"] = error
                    state["finished_at"] = datetime.now(timezone.utc).isoformat()
                self._persistent_job_finish(
                    task_id,
                    state="failed",
                    error_code=str(error.get("error_code") or "background_task_failed"),
                )
                self._runtime_logger.emit(
                    "background_task_failed",
                    level="error",
                    fields={
                        "task_id": task_id,
                        "kind": kind,
                        "component": error.get("component"),
                        "error_code": error.get("error_code"),
                        "error_type": type(exc).__name__,
                    },
                )
            else:
                with self._jobs_lock:
                    state["status"] = "completed"
                    state["result"] = self._safe_summary(result)
                    state["finished_at"] = datetime.now(timezone.utc).isoformat()
                self._persistent_job_finish(task_id, state="completed")

        threading.Thread(
            target=self._runtime_bound_target(worker),
            name=f"bridge-{kind}-{task_id[:8]}",
            daemon=True,
        ).start()
        return {"ok": True, "task": dict(state)}

    def _background_status(self, query: Mapping[str, str]) -> dict[str, Any]:
        task_id = str(query.get("task_id", "")).strip()
        with self._jobs_lock:
            if task_id:
                task = self._background_tasks.get(task_id)
                copied = dict(task) if task is not None else None
                if copied is not None:
                    return {"ok": True, "task": copied}
            tasks = sorted(
                (dict(item) for item in self._background_tasks.values()),
                key=lambda item: str(item.get("created_at", "")),
                reverse=True,
            )[:50]
        if task_id:
            recovered = self._persistent_job_snapshot(
                task_id,
                kind="background",
                identifier_field="task_id",
                state_field="status",
            )
            if recovered is None:
                raise CompositionValidationError(
                    "Background task was not found.", code="api_background_task_not_found"
                )
            return {"ok": True, "task": recovered}
        return {"ok": True, "tasks": tasks}

    def _community_members_sync(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        community = load_peer_file(self._peer_path(payload))
        page_size = self._integer(payload.get("page_size", 200), "page_size", minimum=1, maximum=200)
        max_pages = self._integer(payload.get("max_pages", 10000), "max_pages", minimum=1, maximum=10000)
        expected_total = payload.get("expected_total")
        expected = None if expected_total in (None, "") else self._integer(expected_total, "expected_total", minimum=0)

        def operation() -> dict[str, Any]:
            with self._open_bridge(
                self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
            ) as bridge:
                result = bridge.core.members.sync_all(
                    community, page_size=page_size, max_pages=max_pages, expected_total=expected
                )
                summary = result.safe_summary()
                summary["expected_total"] = expected
                summary["missing_count"] = (
                    max(0, expected - int(summary.get("fetched", 0)))
                    if expected is not None
                    else 0
                )
                return {"ok": True, "sync": summary}

        return self._run_eitaa(
            priority=EitaaPriority.BACKGROUND, kind="community.members.sync", callback=operation
        )

    def _community_members_sync_start(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        community = load_peer_file(self._peer_path(payload))
        page_size = self._integer(payload.get("page_size", 200), "page_size", minimum=1, maximum=200)
        max_pages = self._integer(payload.get("max_pages", 10000), "max_pages", minimum=1, maximum=10000)
        expected_total = payload.get("expected_total")
        expected = None if expected_total in (None, "") else self._integer(expected_total, "expected_total", minimum=0)

        def operation() -> dict[str, Any]:
            with self._open_bridge(
                self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
            ) as bridge:
                result = bridge.core.members.sync_all(
                    community, page_size=page_size, max_pages=max_pages, expected_total=expected
                )
                summary = result.safe_summary()
                summary["expected_total"] = expected
                summary["missing_count"] = (
                    max(0, expected - int(summary.get("fetched", 0)))
                    if expected is not None
                    else 0
                )
                return {"ok": True, "sync": summary}

        return self._start_background(
            kind="community.members.sync", callback=operation, priority=EitaaPriority.BACKGROUND
        )

    def _community_members_list(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        community = load_peer_file(self._peer_path(payload))
        text = str(payload.get("text", "")).strip() or None
        offset = self._integer(payload.get("offset", 0), "offset", minimum=0)
        limit = self._integer(payload.get("limit", 100), "limit", minimum=1, maximum=1000)
        # Local SQLite read: intentionally independent from the remote Eitaa
        # scheduler so member browsing stays responsive during a bulk job.
        with self._open_bridge(
            self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
        ) as bridge:
            page = bridge.core.members.search_local(
                MemberSearchQuery(
                    community=community,
                    text=text,
                    states=(MemberState.ACTIVE,),
                    sendable_only=bool(payload.get("sendable_only", False)),
                    include_bots=bool(payload.get("include_bots", True)),
                    offset=offset,
                    limit=limit,
                )
            )
            # Keep snapshot health independent from the current search/filter.
            # The UI uses this count to detect a partial local snapshot instead
            # of presenting the final filtered page as "all members".
            snapshot_page = bridge.core.members.search_local(
                MemberSearchQuery(
                    community=community,
                    states=(MemberState.ACTIVE,),
                    include_bots=True,
                    offset=0,
                    limit=1,
                )
            )
            member_summaries = [item.safe_summary() for item in page.members]
            user_ids = [int(item.user.peer.id) for item in page.members]
            local_contacts = self._contact_store.find_contacts_by_eitaa_identity(
                eitaa_user_ids=user_ids,
            )
            contacts_by_user_id = {
                int(contact["eitaa_user_id"]): contact
                for contact in local_contacts
                if contact.get("eitaa_user_id") is not None
            }
            for member, summary in zip(page.members, member_summaries):
                user_id = int(member.user.peer.id)
                local_contact = contacts_by_user_id.get(user_id)
                source = str(local_contact.get("source") or "") if local_contact else ""
                is_eitaa_contact = bool(
                    member.user.is_contact or source.startswith("eitaa_contact")
                )
                is_local_contact = local_contact is not None
                summary["contact"] = {
                    "state": (
                        "eitaa"
                        if is_eitaa_contact
                        else "local"
                        if is_local_contact
                        else "none"
                    ),
                    "is_eitaa_contact": is_eitaa_contact,
                    "is_local_contact": is_local_contact,
                    "display_name": (
                        self._sender_contact_name(local_contact)
                        if local_contact is not None
                        else None
                    ),
                    "local_contact_id": (
                        int(local_contact["id"])
                        if local_contact is not None
                        else None
                    ),
                }
            return {
                "ok": True,
                "page": {
                    **page.safe_summary(),
                    "snapshot_total_count": snapshot_page.total_count,
                    "members": member_summaries,
                },
            }

    def _member_ids(self, payload: Mapping[str, Any]) -> list[int] | None:
        raw = payload.get("member_ids")
        if raw is None:
            return None
        if not isinstance(raw, list):
            raise CompositionValidationError("member_ids must be an array.", code="api_invalid_member_ids")
        selected = list(dict.fromkeys(
            self._integer(item, "member_id", minimum=1) for item in raw
        ))
        if len(selected) > 100_000:
            raise CompositionValidationError(
                "Member selection exceeds 100000 entries.",
                code="api_member_selection_too_large",
            )
        return selected

    def _bulk_member_ids(self, payload: Mapping[str, Any]) -> list[int] | None:
        """Resolve an explicit member scope without treating an empty selection as all."""
        member_ids = self._member_ids(payload)
        default_scope = "selected" if member_ids else "all_snapshot"
        scope = str(payload.get("member_scope") or default_scope).strip()
        if scope == "all_snapshot":
            if member_ids:
                raise CompositionValidationError(
                    "all_snapshot scope cannot include member_ids.",
                    code="api_conflicting_member_scope",
                )
            return None
        if scope != "selected":
            raise CompositionValidationError(
                "Unsupported member_scope.",
                code="api_invalid_member_scope",
            )
        if not member_ids:
            raise CompositionValidationError(
                "Selected member scope requires at least one member.",
                code="api_member_selection_required",
            )
        return member_ids

    @staticmethod
    def _member_mutation_error_code(exc: BaseException) -> str:
        if isinstance(exc, RpcError):
            text = exc.text.upper().replace(" ", "_")
            return f"RPC_{exc.code}_{text[:64]}"
        return type(exc).__name__

    @staticmethod
    def _member_mutation_must_stop(exc: BaseException) -> bool:
        if not isinstance(exc, RpcError):
            return False
        text = exc.text.upper()
        return exc.code in {401, 420, 429} or any(
            marker in text
            for marker in (
                "FLOOD",
                "RATE",
                "PEER_FLOOD",
                "CHAT_ADMIN_REQUIRED",
                "CHANNEL_PRIVATE",
                "CHAT_WRITE_FORBIDDEN",
            )
        )

    def _community_members_mutation_start(
        self,
        payload: Mapping[str, Any],
        *,
        action: str,
    ) -> dict[str, Any]:
        if not bool(payload.get("confirm")):
            raise CompositionValidationError(
                "Explicit confirmation is required for member changes.",
                code="api_member_mutation_confirmation_required",
            )
        site_key = self._site_key(payload)
        source_payload = {
            "peer_file": (
                payload.get("source_peer_file")
                if action == "invite"
                else payload.get("peer_file")
            )
        }
        source = load_peer_file(self._peer_path(source_payload))
        if source.type not in {PeerType.CHAT, PeerType.CHANNEL}:
            raise CompositionValidationError(
                "Member source must be a group or channel.",
                code="api_member_source_required",
            )
        member_ids = self._member_ids(payload)
        all_members = bool(payload.get("all_members", False))
        if action == "remove" and all_members:
            raise CompositionValidationError(
                "Removing all members is intentionally unsupported.",
                code="api_remove_all_members_forbidden",
            )
        if not all_members and not member_ids:
            raise CompositionValidationError(
                "Select at least one member.",
                code="api_member_selection_required",
            )
        if all_members and member_ids:
            raise CompositionValidationError(
                "all_members cannot be combined with member_ids.",
                code="api_conflicting_member_scope",
            )
        target = source
        if action == "invite":
            target = load_peer_file(self._peer_path({
                "peer_file": payload.get("target_peer_file"),
            }))
            if target.type not in {PeerType.CHAT, PeerType.CHANNEL}:
                raise CompositionValidationError(
                    "Invitation target must be a group or channel.",
                    code="api_member_target_required",
                )
            if target.type is source.type and target.id == source.id:
                raise CompositionValidationError(
                    "Source and target conversations must differ.",
                    code="api_member_target_matches_source",
                )
        delay_seconds = self._number(
            payload.get("delay_seconds", 2.0),
            "delay_seconds",
            minimum=0,
            maximum=3600,
        )
        include_bots = bool(payload.get("include_bots", False))

        def operation() -> dict[str, Any]:
            with self._open_bridge(
                self.config_path,
                env_file=self.env_file,
                site_key=site_key,
                open_core=True,
            ) as bridge:
                if action == "invite" and all_members:
                    sync = bridge.core.members.sync_all(
                        source,
                        page_size=200,
                        max_pages=10_000,
                        expected_total=None,
                    )
                    if not sync.complete_snapshot:
                        raise CompositionValidationError(
                            "The source member snapshot is incomplete.",
                            safe_context=sync.safe_summary(),
                            code="api_member_snapshot_incomplete",
                        )

                candidates: list[Any] = []
                if member_ids is not None:
                    for user_id in member_ids:
                        member = bridge.core.members.get(source, user_id)
                        if member is not None:
                            candidates.append(member)
                else:
                    offset = 0
                    while True:
                        page = bridge.core.members.search_local(
                            MemberSearchQuery(
                                community=source,
                                states=(MemberState.ACTIVE,),
                                include_bots=include_bots,
                                offset=offset,
                                limit=1_000,
                            )
                        )
                        candidates.extend(page.members)
                        if page.next_offset is None:
                            break
                        offset = page.next_offset

                processed = succeeded = skipped = failed = 0
                stop_reason: str | None = None
                failures: list[dict[str, Any]] = []
                remote = bridge.core.membership.remote
                for member in candidates:
                    if member.user.is_bot and not include_bots:
                        skipped += 1
                        continue
                    user_peer = member.send_peer
                    if user_peer is None:
                        skipped += 1
                        continue
                    processed += 1
                    try:
                        if action == "remove":
                            result = remote.remove_member(
                                source,
                                user_peer,
                                revoke_history=False,
                                release_channel_ban=True,
                            )
                            store = getattr(bridge.core.members, "store", None)
                            if store is not None:
                                store.mark_member_left(source, user_peer.id)
                        else:
                            result = remote.add_member(target, user_peer, fwd_limit=0)
                        if result.accepted:
                            succeeded += 1
                        else:
                            skipped += 1
                    except EitaaCoreError as exc:
                        code = self._member_mutation_error_code(exc)
                        if isinstance(exc, RpcError) and any(
                            marker in exc.text.upper()
                            for marker in (
                                "USER_ALREADY_PARTICIPANT",
                                "USER_NOT_PARTICIPANT",
                                "PARTICIPANT_ID_INVALID",
                            )
                        ):
                            skipped += 1
                        else:
                            failed += 1
                            if len(failures) < 100:
                                failures.append({
                                    "user_id": int(user_peer.id),
                                    "error_code": code,
                                })
                        if self._member_mutation_must_stop(exc):
                            stop_reason = code
                            break
                    if delay_seconds:
                        time.sleep(delay_seconds)

                report = {
                    "action": action,
                    "source": source.safe_summary(),
                    "target": target.safe_summary() if action == "invite" else None,
                    "candidate_count": len(candidates),
                    "processed": processed,
                    "succeeded": succeeded,
                    "skipped": skipped,
                    "failed": failed,
                    "stopped": stop_reason is not None,
                    "stop_reason": stop_reason,
                    "failures": failures,
                }
                self._runtime_logger.emit(
                    "community_member_mutation_completed",
                    level="warning" if failed or stop_reason else "info",
                    fields={
                        key: value
                        for key, value in report.items()
                        if key not in {"failures"}
                    },
                )
                return {"report": report}

        return self._start_background(
            kind=f"community.members.{action}",
            callback=operation,
            priority=EitaaPriority.BACKGROUND,
        )

    def _community_members_remove_start(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._community_members_mutation_start(payload, action="remove")

    def _community_members_invite_start(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._community_members_mutation_start(payload, action="invite")

    def _member_roles(self, payload: Mapping[str, Any]) -> tuple[MemberRole, ...]:
        raw = payload.get("roles")
        if raw in (None, []):
            return ()
        if not isinstance(raw, list):
            raise CompositionValidationError("roles must be an array.", code="api_invalid_member_roles")
        try:
            return tuple(MemberRole(str(item)) for item in raw)
        except ValueError as exc:
            raise CompositionValidationError("Unsupported member role.", code="api_invalid_member_roles") from exc

    def _optional_limit(self, payload: Mapping[str, Any], name: str = "test_limit") -> int | None:
        raw = payload.get(name)
        return None if raw in (None, "", 0, "0") else self._integer(raw, name, minimum=1, maximum=100000)

    def _bulk_spec(self, payload: Mapping[str, Any]) -> BulkMessageSpec:
        kind_raw = str(payload.get("kind", "text")).strip().lower()
        try:
            kind = SendKind(kind_raw)
        except ValueError as exc:
            raise CompositionValidationError("Unsupported message kind.", code="api_invalid_send_kind") from exc
        text = str(payload.get("text", ""))
        caption = str(payload.get("caption", ""))
        file_path: Path | None = None
        if kind is not SendKind.TEXT:
            raw_path = str(payload.get("file_path", "")).strip()
            if not raw_path:
                raise CompositionValidationError("file_path is required for media sends.", code="api_file_path_required")
            file_path = Path(raw_path).expanduser().resolve()
            if not file_path.is_file():
                raise CompositionValidationError("Selected media file was not found.", code="api_media_file_not_found")
        spec = BulkMessageSpec(
            kind=kind,
            text=text,
            file_path=file_path,
            caption=caption,
            mime_type=(str(payload.get("mime_type")).strip() if payload.get("mime_type") else None),
        )
        spec.validate()
        return spec

    def _bulk_options(self, payload: Mapping[str, Any]) -> BulkSendOptions:
        options = BulkSendOptions(
            delay_seconds=self._number(payload.get("delay_seconds", 2.0), "delay_seconds", minimum=0, maximum=3600),
            max_attempts=self._integer(payload.get("max_attempts", 3), "max_attempts", minimum=1, maximum=10),
            retry_delay_seconds=self._number(payload.get("retry_delay_seconds", 5.0), "retry_delay_seconds", minimum=0, maximum=3600),
            test_limit=self._optional_limit(payload),
            stop_on_server_error=bool(payload.get("stop_on_server_error", True)),
        )
        options.validate()
        return options

    def _community_bulk_validate(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        spec = self._bulk_spec(payload)
        file_summary: dict[str, Any] | None = None
        if spec.file_path is not None:
            size = spec.file_path.stat().st_size
            maximum = self.MAX_MEDIA_MB * 1024 * 1024
            if size > maximum:
                raise CompositionValidationError(
                    "Selected media exceeds the local safety limit.",
                    safe_context={"size_bytes": size, "maximum_bytes": maximum},
                    code="api_media_file_too_large",
                )
            guessed_mime = spec.mime_type or mimetypes.guess_type(spec.file_path.name)[0] or "application/octet-stream"
            if spec.kind is SendKind.PHOTO and not guessed_mime.startswith("image/"):
                raise CompositionValidationError(
                    "Photo mode requires an image file.",
                    safe_context={"mime_type": guessed_mime},
                    code="api_photo_requires_image",
                )
            file_summary = {
                "name": spec.file_path.name,
                "size_bytes": size,
                "mime_type": guessed_mime,
                "kind": spec.kind.value,
            }
        return {"ok": True, "message": spec.safe_summary(), "file": file_summary}

    def _community_bulk_preview(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        community = load_peer_file(self._peer_path(payload))
        with self._eitaa_lock, self._open_bridge(
            self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
        ) as bridge:
            result = bridge.core.bulk_send.preview(
                community,
                member_ids=self._bulk_member_ids(payload),
                roles=self._member_roles(payload),
                include_bots=bool(payload.get("include_bots", False)),
                test_limit=self._optional_limit(payload),
                sample_limit=self._integer(payload.get("sample_limit", 10), "sample_limit", minimum=1, maximum=100),
            )
            return {"ok": True, "preview": result.safe_summary()}

    def _community_bulk_create(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        community = load_peer_file(self._peer_path(payload))
        with self._eitaa_lock, self._open_bridge(
            self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
        ) as bridge:
            job = bridge.core.bulk_send.create_job(
                community,
                self._bulk_spec(payload),
                self._bulk_options(payload),
                member_ids=self._bulk_member_ids(payload),
                roles=self._member_roles(payload),
                include_bots=bool(payload.get("include_bots", False)),
            )
            return {"ok": True, "job": job.safe_summary()}

    def _community_bulk_run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        job_id = str(payload.get("job_id", "")).strip()
        if not job_id:
            raise CompositionValidationError("job_id is required.", code="api_job_id_required")

        def operation() -> dict[str, Any]:
            with self._open_bridge(
                self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
            ) as bridge:
                report = bridge.core.bulk_send.run(job_id, confirm=bool(payload.get("confirm")))
                return {"job_id": job_id, "report": report.safe_summary()}

        return self._start_background(kind="community.bulk.run", callback=operation)

    def _community_bulk_jobs(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        limit = self._integer(payload.get("limit", 100), "limit", minimum=1, maximum=1000)
        # Job reports are local SQLite reads and must remain available while the
        # scheduler owns the remote session for a long file upload.
        with self._open_bridge(
            self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
        ) as bridge:
            job_id = str(payload.get("job_id", "")).strip()
            if job_id:
                return {"ok": True, "report": bridge.core.bulk_send.report(job_id).safe_summary()}
            return {"ok": True, "jobs": [job.safe_summary() for job in bridge.core.bulk_send.jobs(limit=limit)]}

    def _community_bulk_recipients(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        job_id = str(payload.get("job_id", "")).strip()
        if not job_id:
            raise CompositionValidationError("job_id is required.", code="api_job_id_required")
        limit = self._integer(payload.get("limit", 100), "limit", minimum=1, maximum=1000)
        status_raw = str(payload.get("status", "")).strip().lower()
        status = None
        if status_raw:
            try:
                status = BulkRecipientStatus(status_raw)
            except ValueError as exc:
                raise CompositionValidationError(
                    "Unsupported recipient status.", code="api_invalid_recipient_status"
                ) from exc
        # Recipient reports are local SQLite reads; do not queue them behind
        # the remote upload loop or progress/error visibility would freeze.
        with self._open_bridge(
            self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
        ) as bridge:
            recipients = bridge.core.bulk_send.recipients(job_id, status=status, limit=limit)
            return {
                "ok": True,
                "job_id": job_id,
                "status": status.value if status else None,
                "recipients": [item.safe_summary() for item in recipients],
            }

    def _community_bulk_action(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        job_id = str(payload.get("job_id", "")).strip()
        action = str(payload.get("action", "report")).strip().lower()
        if not job_id:
            raise CompositionValidationError("job_id is required.", code="api_job_id_required")
        # Pause/resume/cancel mutate only persistent job state. They must not
        # wait for the remote loop, which checks that state between recipients.
        with self._open_bridge(
            self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
        ) as bridge:
            service = bridge.core.bulk_send
            if action == "pause":
                result = service.pause(job_id)
            elif action == "resume":
                result = service.resume(job_id)
            elif action == "cancel":
                result = service.cancel(job_id)
            elif action == "report":
                result = service.report(job_id)
            else:
                raise CompositionValidationError("Unsupported bulk action.", code="api_invalid_bulk_action")
            return {"ok": True, "result": self._safe_summary(result)}

    def _phone_list_import(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        source_file = str(payload.get("source_file", "")).strip()
        if source_file:
            source = Path(source_file).expanduser().resolve()
            if not source.is_file() or source.suffix.lower() not in {".txt", ".csv"}:
                raise CompositionValidationError("Phone source must be an existing TXT or CSV file.", code="api_invalid_phone_source")
        else:
            raw_numbers = payload.get("numbers")
            if isinstance(raw_numbers, str):
                lines = raw_numbers.replace(",", "\n").replace(";", "\n").splitlines()
            elif isinstance(raw_numbers, list):
                lines = [str(item) for item in raw_numbers]
            else:
                raise CompositionValidationError("numbers must be text or an array.", code="api_invalid_phone_numbers")
            normalized = [line.strip() for line in lines if line.strip()]
            if not normalized:
                raise CompositionValidationError("At least one phone number is required.", code="api_phone_numbers_required")
            if len(normalized) > 10000:
                raise CompositionValidationError("Phone list exceeds 10000 rows.", code="api_phone_list_too_large")
            imports = self.base_directory / "data" / "imports"
            imports.mkdir(parents=True, exist_ok=True)
            source = imports / f"phones-{uuid.uuid4().hex}.txt"
            source.write_text("\n".join(normalized) + "\n", encoding="utf-8")
        with self._eitaa_lock, self._open_bridge(
            self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
        ) as bridge:
            phone_list = bridge.core.phone_lists.import_file(
                source,
                name=(str(payload.get("name", "")).strip() or None),
                max_rows=10000,
            )
            return {"ok": True, "phone_list": phone_list.safe_summary()}

    def _phone_lists(self, query: Mapping[str, str]) -> dict[str, Any]:
        site_key = self._site_key(query)
        limit = self._integer(query.get("limit", 100), "limit", minimum=1, maximum=1000)
        # Metadata listing is a local SQLite read and must remain responsive
        # while an unrelated remote Eitaa operation owns the RPC lock.
        with self._open_bridge(
            self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
        ) as bridge:
            return {"ok": True, "phone_lists": [item.safe_summary() for item in bridge.core.phone_lists.lists(limit=limit)]}

    def _phone_list_status(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        list_id = str(payload.get("list_id", "")).strip()
        if not list_id:
            raise CompositionValidationError("list_id is required.", code="api_list_id_required")
        with self._open_bridge(
            self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
        ) as bridge:
            return {"ok": True, "phone_list": bridge.core.phone_lists.status(list_id).safe_summary()}

    def _phone_list_resolve(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        list_id = str(payload.get("list_id", "")).strip()
        if not list_id:
            raise CompositionValidationError("list_id is required.", code="api_list_id_required")
        options = PhoneListResolveOptions(
            import_if_missing=bool(payload.get("import_if_missing", True)),
            delay_seconds=self._number(payload.get("delay_seconds", 1.0), "delay_seconds", minimum=0, maximum=3600),
            max_attempts=self._integer(payload.get("max_attempts", 2), "max_attempts", minimum=1, maximum=10),
            retry_delay_seconds=self._number(payload.get("retry_delay_seconds", 3.0), "retry_delay_seconds", minimum=0, maximum=3600),
            stop_on_server_error=bool(payload.get("stop_on_server_error", True)),
        )
        options.validate()

        def operation() -> dict[str, Any]:
            with self._open_bridge(
                self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
            ) as bridge:
                result = bridge.core.phone_lists.resolve(list_id, options)
                return {"list_id": list_id, "phone_list": result.safe_summary()}

        return self._start_background(kind="phone-lists.resolve", callback=operation)

    def _phone_list_preview(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        list_id = str(payload.get("list_id", "")).strip()
        if not list_id:
            raise CompositionValidationError("list_id is required.", code="api_list_id_required")
        with self._eitaa_lock, self._open_bridge(
            self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
        ) as bridge:
            preview = bridge.core.phone_lists.preview(
                list_id,
                test_limit=self._optional_limit(payload),
                sample_limit=self._integer(payload.get("sample_limit", 10), "sample_limit", minimum=1, maximum=100),
            )
            return {"ok": True, "preview": preview.safe_summary()}

    def _phone_list_bulk_create(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        list_id = str(payload.get("list_id", "")).strip()
        if not list_id:
            raise CompositionValidationError("list_id is required.", code="api_list_id_required")
        with self._eitaa_lock, self._open_bridge(
            self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
        ) as bridge:
            job = bridge.core.phone_lists.create_job(
                list_id, self._bulk_spec(payload), self._bulk_options(payload)
            )
            return {"ok": True, "job": job.safe_summary()}

    def _membership_preview(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        list_id = str(payload.get("list_id", "")).strip()
        target = load_peer_file(self._peer_path(payload))
        if not list_id:
            raise CompositionValidationError("list_id is required.", code="api_list_id_required")
        with self._eitaa_lock, self._open_bridge(
            self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
        ) as bridge:
            preview = bridge.core.membership.preview(
                list_id,
                target,
                test_limit=self._optional_limit(payload),
                sample_limit=self._integer(payload.get("sample_limit", 10), "sample_limit", minimum=1, maximum=100),
            )
            return {"ok": True, "preview": preview.safe_summary()}

    def _membership_create(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        list_id = str(payload.get("list_id", "")).strip()
        target = load_peer_file(self._peer_path(payload))
        if not list_id:
            raise CompositionValidationError("list_id is required.", code="api_list_id_required")
        options = MembershipInviteOptions(
            delay_seconds=self._number(payload.get("delay_seconds", 2.0), "delay_seconds", minimum=0, maximum=3600),
            max_attempts=self._integer(payload.get("max_attempts", 2), "max_attempts", minimum=1, maximum=10),
            retry_delay_seconds=self._number(payload.get("retry_delay_seconds", 5.0), "retry_delay_seconds", minimum=0, maximum=3600),
            test_limit=self._optional_limit(payload),
            stop_on_server_error=bool(payload.get("stop_on_server_error", True)),
            fwd_limit=self._integer(payload.get("fwd_limit", 0), "fwd_limit", minimum=0, maximum=100),
        )
        options.validate()
        with self._eitaa_lock, self._open_bridge(
            self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
        ) as bridge:
            job = bridge.core.membership.create_job(list_id, target, options)
            return {"ok": True, "job": job.safe_summary()}

    def _membership_run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        job_id = str(payload.get("job_id", "")).strip()
        if not job_id:
            raise CompositionValidationError("job_id is required.", code="api_job_id_required")

        def operation() -> dict[str, Any]:
            with self._open_bridge(
                self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
            ) as bridge:
                report = bridge.core.membership.run(job_id, confirm=bool(payload.get("confirm")))
                return {"job_id": job_id, "report": report.safe_summary()}

        return self._start_background(kind="membership.run", callback=operation)

    def _membership_jobs(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        limit = self._integer(payload.get("limit", 100), "limit", minimum=1, maximum=1000)
        with self._eitaa_lock, self._open_bridge(
            self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
        ) as bridge:
            job_id = str(payload.get("job_id", "")).strip()
            if job_id:
                return {"ok": True, "report": bridge.core.membership.report(job_id).safe_summary()}
            return {"ok": True, "jobs": [job.safe_summary() for job in bridge.core.membership.jobs(limit=limit)]}

    def _membership_action(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        job_id = str(payload.get("job_id", "")).strip()
        action = str(payload.get("action", "report")).strip().lower()
        if not job_id:
            raise CompositionValidationError("job_id is required.", code="api_job_id_required")
        with self._eitaa_lock, self._open_bridge(
            self.config_path, env_file=self.env_file, site_key=site_key, open_core=True
        ) as bridge:
            service = bridge.core.membership
            if action == "pause":
                result = service.pause(job_id)
            elif action == "resume":
                result = service.resume(job_id)
            elif action == "cancel":
                result = service.cancel(job_id)
            elif action == "report":
                result = service.report(job_id)
            else:
                raise CompositionValidationError("Unsupported membership action.", code="api_invalid_membership_action")
            return {"ok": True, "result": self._safe_summary(result)}

    @staticmethod
    def _number(
        value: Any,
        field_name: str,
        *,
        minimum: float | None = None,
        maximum: float | None = None,
    ) -> float:
        if isinstance(value, bool):
            raise CompositionValidationError(f"{field_name} must be a number.", code="api_invalid_number")
        try:
            selected = float(value)
        except (TypeError, ValueError) as exc:
            raise CompositionValidationError(f"{field_name} must be a number.", code="api_invalid_number") from exc
        if minimum is not None and selected < minimum:
            raise CompositionValidationError(
                f"{field_name} is below the allowed minimum.",
                safe_context={"field": field_name, "minimum": minimum},
                code="api_number_out_of_range",
            )
        if maximum is not None and selected > maximum:
            raise CompositionValidationError(
                f"{field_name} exceeds the allowed maximum.",
                safe_context={"field": field_name, "maximum": maximum},
                code="api_number_out_of_range",
            )
        return selected

    def _site_key(self, payload: Mapping[str, Any]) -> str:
        config = BridgeConfigLoader.load(self.config_path, env_file=self.env_file)
        raw = payload.get("site_key")
        selected = str(raw).strip() if raw is not None and str(raw).strip() else config.default_site_key
        config.site(selected)  # validate early
        return selected

    def _peer_path(self, payload: Mapping[str, Any]) -> Path:
        raw = payload.get("peer_file")
        if not isinstance(raw, str) or not raw.strip():
            raise CompositionValidationError("peer_file is required.", code="api_peer_file_required")
        path = Path(raw).expanduser()
        resolved = path.resolve() if path.is_absolute() else (self.base_directory / path).resolve()
        account_root = self._runtime.ownership.account_data_directory
        if account_root is not None:
            try:
                resolved.relative_to(account_root)
            except ValueError as exc:
                raise CompositionValidationError(
                    "peer_file is outside the selected MessengerAccount.",
                    code="api_peer_file_account_boundary",
                ) from exc
        return resolved

    @staticmethod
    def _integer(
        value: Any,
        field_name: str,
        *,
        minimum: int | None = None,
        maximum: int | None = None,
    ) -> int:
        if isinstance(value, bool):
            raise CompositionValidationError(
                f"{field_name} must be an integer.", code="api_invalid_integer"
            )
        try:
            selected = int(value)
        except (TypeError, ValueError) as exc:
            raise CompositionValidationError(
                f"{field_name} must be an integer.", code="api_invalid_integer"
            ) from exc
        if minimum is not None and selected < minimum:
            raise CompositionValidationError(
                f"{field_name} is below the allowed minimum.",
                safe_context={"field": field_name, "minimum": minimum},
                code="api_integer_out_of_range",
            )
        if maximum is not None and selected > maximum:
            raise CompositionValidationError(
                f"{field_name} exceeds the allowed maximum.",
                safe_context={"field": field_name, "maximum": maximum},
                code="api_integer_out_of_range",
            )
        return selected

    @staticmethod
    def _is_invalid_session_error(exc: BaseException) -> bool:
        """Return whether an exception chain proves that Eitaa rejected the login.

        Network errors and other transient probe failures deliberately remain
        outside this classification. Only an RPC 401 is strong enough evidence
        to move the UI out of the authenticated workspace.
        """
        current: BaseException | None = exc
        visited: set[int] = set()
        while current is not None and id(current) not in visited:
            visited.add(id(current))
            if isinstance(current, RpcError) and current.code == 401:
                return True
            current = current.__cause__ or current.__context__
        return False

    @staticmethod
    def _error_response(exc: Exception) -> ApiResponse:
        invalid_session = BridgeApplicationApi._is_invalid_session_error(exc)
        if invalid_session:
            status = 401
        elif isinstance(exc, CoordinatorAuthRateLimitError):
            status = 429
        elif isinstance(exc, CoordinatorAuthorizationError):
            status = 403
        elif isinstance(exc, CoordinatorConflictError):
            status = 409
        elif isinstance(exc, CoordinatorAuthenticationError):
            if exc.code in {
                "app_auth_required",
                "app_auth_session_invalid",
                "app_auth_invalid_credentials",
                "app_auth_current_password_invalid",
                "m2m_auth_missing",
                "m2m_auth_invalid",
            }:
                status = 401
            elif exc.code in {
                "app_auth_setup_unavailable",
                "app_auth_setup_conflict",
                "app_auth_username_unavailable",
            }:
                status = 409
            else:
                status = 400
        elif isinstance(exc, CredentialError):
            status = 401
        elif isinstance(exc, (CompositionCollisionError, CompositionBlockedError)):
            status = 409
        elif isinstance(exc, CompositionValidationError):
            status = 404 if exc.code == "composition_message_not_found" else 400
        elif isinstance(exc, (BridgeConfigurationError,)):
            status = 400
        elif isinstance(exc, WordPressAuthenticationError):
            status = 502
        elif isinstance(exc, (WordPressConnectionError, WordPressError)):
            status = 502
        elif isinstance(exc, LocalContentIndexError):
            status = 500
        elif isinstance(exc, BridgeError):
            status = 400
        elif isinstance(exc, EitaaCoreError):
            status = 400 if exc.component in {"domain", "configuration"} else 502
        else:
            status = 500

        if invalid_session:
            component = "authentication"
            code = "auth_session_invalid"
            message = (
                "نشست ایتا دیگر معتبر نیست. از حساب محلی خارج شوید و دوباره وارد شوید."
            )
            safe_context = {
                "error_type": type(exc).__name__,
                "remote_code": 401,
                "recovery_available": True,
            }
            debug_file = getattr(exc, "debug_file", None)
        elif isinstance(exc, BridgeError):
            component = exc.component
            code = exc.code
            message = exc.message
            safe_context = exc.safe_context
            debug_file = exc.debug_file
        elif isinstance(exc, EitaaCoreError):
            component = exc.component
            code = f"core_{type(exc).__name__.removesuffix('Error').lower()}"
            message = exc.message
            safe_context = {**exc.safe_context, "error_type": type(exc).__name__}
            debug_file = exc.debug_file
        else:
            component = "api"
            code = "api_internal_error"
            message = "The local API request failed unexpectedly."
            safe_context = {"error_type": type(exc).__name__}
            debug_file = None
        return ApiResponse(
            status,
            {
                "ok": False,
                "error": {
                    "component": component,
                    "error_code": code,
                    "message": message,
                    "safe_context": safe_context,
                    "debug_file": debug_file,
                },
            },
        )
