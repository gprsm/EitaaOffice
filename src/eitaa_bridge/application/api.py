"""UI-facing local application API independent of any web framework."""

from __future__ import annotations

import atexit
import base64
import hmac
import mimetypes
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
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

from eitaa_core.errors import EitaaCoreError, RpcError

from ..errors import (
    AuthenticationRuntimeError,
    BridgeConfigurationError,
    BridgeError,
    CompositionBlockedError,
    CompositionCollisionError,
    CompositionValidationError,
    ContactDirectoryError,
    CredentialError,
    LocalContentIndexError,
    WordPressAuthenticationError,
    WordPressConnectionError,
    WordPressError,
)
from ..facade import EitaaBridge
from ..infrastructure.composition_manifest import CompositionManifestLoader
from ..infrastructure.content_index_store import SQLiteContentIndexStore
from ..infrastructure.contact_store import SQLiteContactStore, normalize_phone
from ..infrastructure.dialog_catalog import JsonDialogCatalog
from ..infrastructure.eitaa.sender_directory import configure_sender_directory
from ..infrastructure.config import BridgeConfigLoader, EnvLoader, WordPressSiteSettings
from ..infrastructure.diagnostics import (
    BridgeDiagnosticManager,
    RuntimeLogger,
    prune_old_diagnostic_runs,
)
from ..version import __version__
from .content_index import DEFAULT_SCORE_THRESHOLD, IndexLabel
from .content_index_service import LocalContentIndexService
from .contact_import import map_contact_rows, parse_tabular
from .scheduler import EitaaOperationScheduler, EitaaPriority


@dataclass(slots=True, frozen=True)
class ApiResponse:
    status: int
    payload: dict[str, Any]


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
    ) -> None:
        self.config_path = Path(config_path).expanduser().resolve()
        self.env_file = Path(env_file).expanduser().resolve() if env_file else None
        config = BridgeConfigLoader.load(self.config_path, env_file=self.env_file)
        EnvLoader.load(config.env_file)
        configured_token = bearer_token if bearer_token is not None else os.getenv("EITAA_BRIDGE_API_TOKEN")
        self.bearer_token = configured_token.strip() if configured_token and configured_token.strip() else None
        self.base_directory = config.source_file.parent
        self._diagnostics = BridgeDiagnosticManager(
            config.diagnostics.root, enabled=config.diagnostics.enabled
        )
        self._runtime_logger = RuntimeLogger(
            self.base_directory / "runtime" / "logs" / "application.jsonl"
        )
        self._media_cache_lock = threading.RLock()
        self._media_cache_files: dict[str, tuple[Path, str, float]] = {}
        self._avatar_source_cache_lock = threading.RLock()
        self._avatar_source_cache: dict[str, tuple[float, dict[str, tuple[Any, Any]]]] = {}
        self._avatar_source_cache_ttl_seconds = 300.0
        threading.Thread(
            target=self._prune_diagnostics,
            name="bridge-diagnostics-prune",
            daemon=True,
        ).start()
        self._auth_lock = threading.RLock()
        # The HTTP adapter is threaded, but every Eitaa RPC shares one mutable
        # session. A single priority scheduler serializes remote operations and
        # lets active-message work outrank background discovery and read receipts.
        self._eitaa_lock = threading.RLock()
        self._scheduler = EitaaOperationScheduler()
        self._jobs_lock = threading.RLock()
        self._dialog_sync_jobs: dict[str, dict[str, Any]] = {}
        self._active_dialog_sync_job: str | None = None
        self._content_index_lock = threading.RLock()
        self._content_index_jobs: dict[str, dict[str, Any]] = {}
        self._content_index_active: dict[str, str] = {}
        self._content_index_cancellations: dict[str, threading.Event] = {}
        self._content_index_store = SQLiteContentIndexStore(
            self.base_directory / "data" / "content_index.sqlite3"
        )
        self._contact_store = SQLiteContactStore(
            self.base_directory / "data" / "contacts.sqlite3"
        )
        self._sender_directory = configure_sender_directory(
            self.base_directory / "data" / "sender_directory.sqlite3"
        )
        self._contact_import_lock = threading.RLock()
        self._contact_import_jobs: dict[str, dict[str, Any]] = {}
        self._contact_import_cancellations: dict[str, threading.Event] = {}
        # The server contact book is fetched through one serialized Eitaa RPC.
        # Keep a short-lived, process-local safe-summary cache so UI paging and
        # searches do not refetch or reserialize thousands of contacts.
        self._eitaa_contacts_cache_lock = threading.RLock()
        self._eitaa_contacts_cache: dict[str, tuple[float, tuple[dict[str, Any], ...], bool]] = {}
        self._eitaa_contacts_cache_ttl_seconds = 300.0
        self._background_tasks: dict[str, dict[str, Any]] = {}
        self._read_queue_lock = threading.RLock()
        self._pending_read_receipts: dict[str, dict[str, Any]] = {}
        self._read_worker_active = False
        self._read_receipt_delay_seconds = 3.0
        self._auth_runtime: EitaaAuth | None = None
        self._auth_challenge: Any | None = None
        self.dialog_catalog = JsonDialogCatalog(
            self.base_directory / "data" / "ui-peers" / "catalog.json",
            base_directory=self.base_directory,
        )
        atexit.register(self.close)

    def register_media_cache_file(self, path: Path, mime_type: str) -> str:
        """Register a cached UI media file under an unguessable process-local token."""
        resolved = path.expanduser().resolve()
        token = uuid.uuid4().hex
        with self._media_cache_lock:
            now = time.monotonic()
            self._media_cache_files[token] = (resolved, mime_type, now)
            if len(self._media_cache_files) > 256:
                oldest = sorted(self._media_cache_files.items(), key=lambda item: item[1][2])[:64]
                for key, _ in oldest:
                    self._media_cache_files.pop(key, None)
        return token

    def resolve_media_cache_file(self, token: str) -> tuple[Path, str] | None:
        if len(token) != 32 or any(character not in "0123456789abcdef" for character in token):
            return None
        with self._media_cache_lock:
            item = self._media_cache_files.get(token)
            if item is None:
                return None
            path, mime_type, _ = item
            if not path.is_file():
                self._media_cache_files.pop(token, None)
                return None
            self._media_cache_files[token] = (path, mime_type, time.monotonic())
            return path, mime_type

    def _prune_diagnostics(self) -> None:
        result = prune_old_diagnostic_runs(
            self._diagnostics.root,
            protected_run_ids={self._diagnostics.run_id},
            keep_newest=50,
            max_age_days=30,
        )
        if result["removed"] or result["failed"]:
            self._runtime_logger.emit("diagnostics_pruned", fields=result)

    def _open_bridge(
        self,
        config_path: str | Path,
        *,
        env_file: str | Path | None = None,
        site_key: str | None = None,
        open_core: bool = False,
        wordpress_session: Any | None = None,
    ) -> EitaaBridge:
        # The shared Core owns a thread-affine SQLite connection.  Reuse it only
        # on the scheduler worker that created and serializes it; ordinary HTTP
        # request threads receive a short-lived owned Core instead.
        reuse_core = bool(
            open_core and threading.current_thread().name == "eitaa-operation-scheduler"
        )
        return EitaaBridge.open(
            config_path,
            env_file=env_file,
            site_key=site_key,
            open_core=open_core,
            wordpress_session=wordpress_session,
            diagnostics=self._diagnostics,
            reuse_core=reuse_core,
        )

    def close(self) -> None:
        with self._content_index_lock:
            for cancellation in self._content_index_cancellations.values():
                cancellation.set()
        with self._auth_lock:
            if self._auth_runtime is not None:
                try:
                    self._auth_runtime.close()
                except Exception:
                    pass
                self._auth_runtime = None
        EitaaBridge.close_shared_cores()
        self._runtime_logger.close()

    def dispatch(
        self,
        method: str,
        raw_path: str,
        *,
        body: Mapping[str, Any] | None = None,
        authorization: str | None = None,
    ) -> ApiResponse:
        started = time.perf_counter()
        request_id = self._runtime_logger.request_id()
        parsed = urlsplit(raw_path)
        path = parsed.path.rstrip("/") or "/"
        selected_method = method.upper().strip()
        try:
            response = self._dispatch_inner(
                method, raw_path, body=body, authorization=authorization
            )
        except Exception as exc:
            response = self._error_response(exc)
        error = response.payload.get("error") if isinstance(response.payload, dict) else None
        self._runtime_logger.emit(
            "api_request",
            level="error" if response.status >= 500 else ("warning" if response.status >= 400 else "info"),
            fields={
                "request_id": request_id,
                "method": selected_method,
                "path": path,
                "status": response.status,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                "error_code": error.get("error_code") if isinstance(error, dict) else None,
            },
        )
        return response

    def _dispatch_inner(
        self,
        method: str,
        raw_path: str,
        *,
        body: Mapping[str, Any] | None = None,
        authorization: str | None = None,
    ) -> ApiResponse:
        try:
            self._authorize(authorization)
            selected_method = method.upper().strip()
            parsed = urlsplit(raw_path)
            path = parsed.path.rstrip("/") or "/"
            query = {key: values[-1] for key, values in parse_qs(parsed.query, keep_blank_values=True).items()}
            payload = dict(body or {})

            if selected_method == "GET" and path == "/api/v1/health":
                return ApiResponse(200, self._health())
            if selected_method == "GET" and path == "/api/v1/schema":
                return ApiResponse(200, self._schema())
            if selected_method == "GET" and path == "/api/v1/scheduler/status":
                return ApiResponse(200, {"ok": True, "scheduler": self._scheduler.snapshot()})
            if selected_method == "GET" and path == "/api/v1/auth/status":
                return ApiResponse(200, self._auth_status())
            if selected_method == "POST" and path == "/api/v1/auth/request-code":
                return ApiResponse(200, self._auth_request_code(payload))
            if selected_method == "POST" and path == "/api/v1/auth/submit-code":
                return ApiResponse(200, self._auth_submit_code(payload))
            if selected_method == "POST" and path == "/api/v1/auth/submit-password":
                return ApiResponse(200, self._auth_submit_password(payload))
            if selected_method == "POST" and path == "/api/v1/auth/logout":
                return ApiResponse(200, self._auth_logout())
            if selected_method == "POST" and path == "/api/v1/auth/reset-local-session":
                return ApiResponse(200, self._auth_reset_local_session(payload))
            if selected_method == "GET" and path == "/api/v1/sites":
                return ApiResponse(200, self._sites())
            if selected_method == "GET" and path == "/api/v1/settings/sites":
                return ApiResponse(200, self._settings_sites())
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
            if selected_method == "POST" and path == "/api/v1/contacts/list":
                return ApiResponse(200, self._contacts_list(payload))
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

    def _authorize(self, authorization: str | None) -> None:
        if self.bearer_token is None:
            return
        prefix = "Bearer "
        supplied = authorization[len(prefix):] if authorization and authorization.startswith(prefix) else ""
        if not supplied or not hmac.compare_digest(supplied, self.bearer_token):
            raise CredentialError("A valid local API bearer token is required.", code="api_unauthorized")

    def _health(self) -> dict[str, Any]:
        config = BridgeConfigLoader.load(self.config_path, env_file=self.env_file)
        return {
            "ok": True,
            "service": "eitaa-bridge-api",
            "api_version": self.API_VERSION,
            "bridge_version": __version__,
            "default_site_key": config.default_site_key,
            "site_count": len(config.wordpress_sites),
            "core_product": "0.6.0-core7.4.5-gmi1",
            "core_package": "0.6.0.dev19",
            "authentication_required": self.bearer_token is not None,
            "scheduler": self._scheduler.snapshot(),
        }

    def _schema(self) -> dict[str, Any]:
        return {
            "ok": True,
            "api_version": self.API_VERSION,
            "routes": [
                {"method": "GET", "path": "/api/v1/health"},
                {"method": "GET", "path": "/api/v1/schema"},
                {"method": "GET", "path": "/api/v1/scheduler/status"},
                {"method": "GET", "path": "/api/v1/auth/status"},
                {"method": "POST", "path": "/api/v1/auth/request-code"},
                {"method": "POST", "path": "/api/v1/auth/submit-code"},
                {"method": "POST", "path": "/api/v1/auth/submit-password"},
                {"method": "POST", "path": "/api/v1/auth/logout"},
                {"method": "POST", "path": "/api/v1/auth/reset-local-session"},
                {"method": "GET", "path": "/api/v1/sites"},
                {"method": "GET", "path": "/api/v1/settings/sites"},
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
                {"method": "POST", "path": "/api/v1/dialogs/list"},
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
        def guarded() -> Any:
            with self._eitaa_lock:
                return callback()
        return self._scheduler.run_sync(
            priority=priority, kind=kind, callback=guarded, timeout=timeout
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
        config = BridgeConfigLoader.load(self.config_path, env_file=self.env_file)
        return EitaaCoreConfig(
            session_file=config.core.session_file,
            database_file=config.core.database_file,
            media_directory=config.core.media_directory,
            diagnostics_root=config.core.diagnostics_root,
            diagnostics_enabled=config.core.diagnostics_enabled,
            timeout_seconds=config.core.timeout_seconds,
        )

    def _auth_status(self) -> dict[str, Any]:
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

    def _auth_reset_local_session(self, payload: Mapping[str, Any]) -> dict[str, Any]:
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
        EitaaBridge.close_shared_cores()
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

    def _auth_request_code(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        phone = str(payload.get("phone") or "").strip()
        if not phone:
            raise CompositionValidationError("phone is required.", code="api_phone_required")
        with self._eitaa_lock, self._auth_lock:
            try:
                if self._auth_runtime is not None:
                    self._auth_runtime.close()
                self._auth_runtime = EitaaAuth.open(self._core_config())
                self._auth_challenge = self._auth_runtime.auth.request_code(phone)
                return {
                    "ok": True,
                    "step": "code",
                    "challenge": self._auth_challenge.safe_summary(),
                }
            except BridgeError:
                raise
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

    def _auth_submit_code(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        code = str(payload.get("code") or "").strip()
        with self._eitaa_lock, self._auth_lock:
            if self._auth_runtime is None or self._auth_challenge is None:
                raise CompositionValidationError(
                    "No login code challenge is pending.", code="api_auth_challenge_missing"
                )
            try:
                result = self._auth_runtime.auth.submit_code(self._auth_challenge, code)
            except BridgeError:
                raise
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
                EitaaBridge.close_shared_cores()
                return {"ok": True, "step": "completed", **result.safe_summary()}
            return {"ok": True, "step": "password", **result.safe_summary()}

    def _auth_submit_password(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        password = payload.get("password")
        if not isinstance(password, str) or not password:
            raise CompositionValidationError("password is required.", code="api_password_required")
        with self._eitaa_lock, self._auth_lock:
            if self._auth_runtime is None:
                raise CompositionValidationError(
                    "No second-factor challenge is pending.", code="api_auth_challenge_missing"
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
            self._auth_runtime.close()
            self._auth_runtime = None
            self._auth_challenge = None
            EitaaBridge.close_shared_cores()
            return {"ok": True, "step": "completed", **result.safe_summary()}

    def _auth_logout(self) -> dict[str, Any]:
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
            EitaaBridge.close_shared_cores()
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
        EitaaBridge.close_shared_cores()
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

    def _dialogs_sync_start(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        page_size = self._integer(payload.get("page_size", 100), "page_size", minimum=1, maximum=100)
        max_pages = self._integer(payload.get("max_pages", 100), "max_pages", minimum=1, maximum=200)
        with self._jobs_lock:
            if self._active_dialog_sync_job:
                current = self._dialog_sync_jobs.get(self._active_dialog_sync_job)
                if current and current.get("state") in {"queued", "running"}:
                    return {"ok": True, "job": dict(current), "reused": True}
            job_id = uuid.uuid4().hex
            job = {
                "job_id": job_id, "kind": "dialog_sync", "site_key": site_key,
                "state": "queued", "created_at": datetime.now(timezone.utc).isoformat(),
                "started_at": None, "completed_at": None, "result": None, "error": None,
            }
            self._dialog_sync_jobs[job_id] = job
            self._active_dialog_sync_job = job_id
        thread = threading.Thread(
            target=self._run_dialog_sync_job,
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
            summary = self._sync_dialog_catalog(site_key=site_key, page_size=page_size, max_pages=max_pages)
            dialogs = self.dialog_catalog.list()
            result = {"site_key": site_key, "dialog_count": len(dialogs), "dialogs": dialogs, "sync": summary}
            with self._jobs_lock:
                job = self._dialog_sync_jobs[job_id]
                job["state"] = "completed"
                job["result"] = result
                job["completed_at"] = datetime.now(timezone.utc).isoformat()
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
            if not job:
                raise CompositionValidationError("Dialog sync job was not found.", code="api_job_not_found")
            return {"ok": True, "job": dict(job)}

    def _dialog_avatar_source(self, bridge: Any, site_key: str, peer_key: str) -> tuple[Any, Any] | None:
        """Resolve a dialog peer/photo pair without rescanning 10k rows per avatar."""

        now = time.monotonic()
        with self._avatar_source_cache_lock:
            cached = self._avatar_source_cache.get(site_key)
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
            self._avatar_source_cache[site_key] = (time.monotonic(), refreshed)
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
        if bool(payload.get("cached_only")) and (not cached_path or not cached_path.exists()):
            return {"ok": True, "peer_key": peer_key, "avatar_present": False, "cached_only": True}
        if not cached_path or not cached_path.exists():
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
                        MediaDownloadOptions(output_directory=output, file_name=file_name, overwrite=False, max_bytes=8 * 1024 * 1024),
                    )
                    path = result.path
                    bridge.core.discovery.set_cached_photo_path(source_peer, source_photo.photo_id, path)
                    return path

            cached_path = self._run_eitaa(
                priority=EitaaPriority.AVATAR,
                kind="dialogs.avatar",
                callback=operation,
            )
            if cached_path is None:
                return {"ok": True, "peer_key": peer_key, "avatar_present": False}
            try:
                stored = str(cached_path.resolve().relative_to(self.base_directory))
            except ValueError:
                stored = str(cached_path.resolve())
            entry = self.dialog_catalog.set_photo_cached_path(peer_key, stored)
        data = cached_path.read_bytes()
        mime_type = mimetypes.guess_type(cached_path.name)[0] or "image/jpeg"
        return {
            "ok": True, "peer_key": peer_key, "avatar_present": True,
            "mime_type": mime_type, "bytes": len(data),
            "data_url": f"data:{mime_type};base64,{base64.b64encode(data).decode('ascii')}",
        }

    def _merge_core_dialogs(
        self, bridge: EitaaBridge, entries: Any, *, source: str, complete: bool,
        finalize_snapshot: bool = True, active_keys: set[str] | None = None,
    ) -> dict[str, Any]:
        peer_directory = self.base_directory / "data" / "ui-peers"
        peer_directory.mkdir(parents=True, exist_ok=True)
        selected_keys: set[str] = set()
        counts: dict[str, int] = {}
        skipped_unusable = 0
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
        peer_directory = self.base_directory / "data" / "ui-peers"
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
                source = str(contact.get("source") or "").strip()
                profiles[selected_id] = {
                    "display_name": contact_name or current.get("display_name"),
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
            upload_root = (self.base_directory / "runtime" / "uploads").resolve()
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
                is_image = media.type.value in {"photo", "image_document", "sticker"}
                if not is_image:
                    return {
                        "ok": True,
                        "message_id": message_id,
                        "media_present": True,
                        "preview_available": False,
                        "media": media.safe_summary(),
                    }

                thumb_type = self._thumbnail_type(media) if quality == "thumbnail" else None
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
                mime_type = mimetypes.guess_type(cache_path.name)[0] or media.mime_type or "image/jpeg"
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
        due_at = time.monotonic() + self._read_receipt_delay_seconds
        with self._read_queue_lock:
            previous = self._pending_read_receipts.get(peer_key)
            if previous is None or max_id >= int(previous["max_id"]):
                self._pending_read_receipts[peer_key] = {
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
                    target=self._run_read_receipt_worker,
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
                peer_key, task = min(
                    self._pending_read_receipts.items(),
                    key=lambda item: float(item[1].get("due_at", 0.0)),
                )
                wait_seconds = max(0.0, float(task.get("due_at", 0.0)) - time.monotonic())
            if wait_seconds:
                time.sleep(min(wait_seconds, 0.5))
                continue
            if self._scheduler.has_higher_priority_work(EitaaPriority.READ_RECEIPT):
                with self._read_queue_lock:
                    if peer_key in self._pending_read_receipts:
                        self._pending_read_receipts[peer_key]["due_at"] = time.monotonic() + 1.0
                time.sleep(0.2)
                continue
            with self._read_queue_lock:
                task = self._pending_read_receipts.pop(peer_key, None)
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
            except Exception:
                # Safe Core diagnostics retain the failure. A read receipt is
                # best-effort and must never delay active message retrieval.
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
        scope = f"{site_key}:{peer.type.value}:{peer.id}"
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
            job_id = uuid.uuid4().hex
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
            target=self._run_content_index_job,
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

        def update_progress(summary: Mapping[str, object]) -> None:
            with self._content_index_lock:
                current = self._content_index_jobs.get(job_id)
                if current is not None:
                    current["progress"] = dict(summary)

        try:
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
            except LocalContentIndexError:
                # Preserve the original failure. A staging cleanup problem is
                # reported on the next run and never promotes incomplete rows.
                pass
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
            if job is None:
                raise CompositionValidationError(
                    "Content-index job was not found.",
                    code="api_content_index_job_not_found",
                )
            return {"ok": True, "job": self._content_index_job_copy(job)}

    def _content_index_cancel(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        job_id = str(payload.get("job_id") or "").strip()
        if not job_id:
            raise CompositionValidationError(
                "job_id is required.", code="api_job_id_required"
            )
        with self._content_index_lock:
            job = self._content_index_jobs.get(job_id)
            if job is None:
                raise CompositionValidationError(
                    "Content-index job was not found.",
                    code="api_content_index_job_not_found",
                )
            cancellation = self._content_index_cancellations.get(job_id)
            if cancellation is not None and job.get("state") in {"queued", "running"}:
                cancellation.set()
                job["state"] = "cancelling"
            return {"ok": True, "job": self._content_index_job_copy(job)}

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
        directory = self.base_directory / "data" / "eitaa-contact-peers"
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
        with self._eitaa_contacts_cache_lock:
            self._eitaa_contacts_cache.pop(site_key, None)

    def _eitaa_contacts_list(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        site_key = self._site_key(payload)
        refresh = bool(payload.get("refresh", False))
        search = str(payload.get("search") or "").strip().casefold()
        limit = self._integer(payload.get("limit", 50), "limit", minimum=1, maximum=500)
        offset = self._integer(payload.get("offset", 0), "offset", minimum=0, maximum=1_000_000)
        now = time.monotonic()

        with self._eitaa_contacts_cache_lock:
            cached = self._eitaa_contacts_cache.get(site_key)
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
                self._eitaa_contacts_cache[site_key] = (time.monotonic(), all_contacts, not_modified)
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
                self._contact_validation(lambda item=item, phone=phone: self._contact_store.upsert_contact(
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
                    duplicate_policy="update",
                    category_policy="merge",
                    status_policy="preserve",
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
            self._contact_validation(lambda: self._contact_store.upsert_contact(
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
                duplicate_policy="update",
                category_policy="merge",
                status_policy="preserve",
            ))
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
            )
            for local_contact in local_matches:
                local_user_id = local_contact.get("eitaa_user_id")
                if local_user_id is not None:
                    local_by_user_id[int(local_user_id)] = local_contact
                for local_phone in local_contact.get("phones") or ():
                    local_by_phone[normalize_phone(local_phone)] = local_contact

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
                    )
                )
            else:
                saved = self._contact_validation(
                    lambda raw_contact=raw_contact, user_id=user_id, phone=phone:
                    self._contact_store.upsert_contact(
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
                        duplicate_policy="update",
                        category_policy="merge" if operation == "add" else "replace",
                        status_policy="preserve",
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

    def _eitaa_contacts_import_local_start(self, payload: Mapping[str, Any]) -> dict[str, Any]:
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
                except Exception:
                    failed += 1
                processed += 1
                if processed % 5 == 0 or processed == len(selected):
                    update_progress({
                        "processed": processed, "eitaa_added": added,
                        "eitaa_updated": updated, "eitaa_existing": existing,
                        "eitaa_failed": failed, "skipped": skipped,
                    })
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
        return {
            "ok": True,
            "contacts": list(contacts),
            "count": len(contacts),
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": offset + len(contacts) < total,
        }

    def _contacts_upsert(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        contact = payload.get("contact")
        if not isinstance(contact, Mapping):
            raise CompositionValidationError(
                "contact must be an object.", code="api_contact_required"
            )
        saved = self._contact_validation(
            lambda: self._contact_store.upsert_contact(
                contact,
                duplicate_policy=str(payload.get("duplicate_policy") or "skip"),
            )
        )
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
            refreshed = self._contact_store.get_contacts((int(saved["id"]),))
            if refreshed:
                response["contact"] = refreshed[0]
        return response

    def _contacts_archive(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        contact_id = self._integer(payload.get("contact_id"), "contact_id", minimum=1)
        if payload.get("confirm") is not True:
            raise CompositionValidationError(
                "Explicit archive confirmation is required.",
                code="api_contact_archive_confirmation_required",
            )
        self._contact_validation(lambda: self._contact_store.archive_contact(contact_id))
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
                name=str(payload.get("name") or ""), category_id=category_id
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
        self._contact_validation(lambda: self._contact_store.delete_category(category_id))
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
        if add_to_eitaa and mapping.get("first_name") in (None, ""):
            raise CompositionValidationError(
                "Map a first-name column before adding spreadsheet rows to Eitaa.",
                code="api_contact_import_first_name_mapping_required",
            )
        site_key = self._site_key(payload)
        job_id = uuid.uuid4().hex
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
            target=self._run_contact_import,
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

        def update_progress(progress: Mapping[str, object]) -> None:
            with self._contact_import_lock:
                current = self._contact_import_jobs.get(job_id)
                if current is not None:
                    current["progress"] = {**current["progress"], **dict(progress)}

        try:
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
                        created = self._contact_store.save_category(name=str(name))
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
            )
            if add_to_eitaa and not result.get("cancelled"):
                selected_ids = tuple(int(value) for value in result.get("contact_ids", []))
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
                        break
                    time.sleep(0.25)
            result.pop("contact_ids", None)
            with self._contact_import_lock:
                job = self._contact_import_jobs[job_id]
                job["progress"] = {**job["progress"], **result}
                job["state"] = "cancelled" if result.get("cancelled") else "completed"
                job["completed_at"] = datetime.now(timezone.utc).isoformat()
        except Exception as exc:
            with self._contact_import_lock:
                job = self._contact_import_jobs[job_id]
                job["state"] = "failed"
                job["error"] = {
                    "message": (
                        exc.message
                        if isinstance(exc, ContactDirectoryError)
                        else str(exc) if isinstance(exc, ValueError)
                        else "Local contact import failed."
                    ),
                    "error_type": type(exc).__name__,
                }
                job["completed_at"] = datetime.now(timezone.utc).isoformat()
        finally:
            with self._contact_import_lock:
                self._contact_import_cancellations.pop(job_id, None)

    def _start_contact_source_import(
        self,
        *,
        kind: str,
        source_label: str,
        runner: Any,
    ) -> dict[str, Any]:
        """Start a local SQLite-to-SQLite import without occupying the Eitaa scheduler."""

        job_id = uuid.uuid4().hex
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

            def update_progress(progress: Mapping[str, object]) -> None:
                with self._contact_import_lock:
                    current = self._contact_import_jobs.get(job_id)
                    if current is not None:
                        current["progress"] = {
                            **current["progress"],
                            **dict(progress),
                        }

            try:
                result = runner(cancellation, update_progress)
                with self._contact_import_lock:
                    current = self._contact_import_jobs[job_id]
                    current["progress"] = {**current["progress"], **dict(result)}
                    current["state"] = (
                        "cancelled" if result.get("cancelled") else "completed"
                    )
                    current["completed_at"] = datetime.now(timezone.utc).isoformat()
            except Exception as exc:
                with self._contact_import_lock:
                    current = self._contact_import_jobs[job_id]
                    current["state"] = "failed"
                    current["error"] = {
                        "message": (
                            exc.message
                            if isinstance(exc, ContactDirectoryError)
                            else str(exc) if isinstance(exc, (ValueError, EitaaCoreError))
                            else "Local contact source import failed."
                        ),
                        "error_type": type(exc).__name__,
                    }
                    current["completed_at"] = datetime.now(timezone.utc).isoformat()
            finally:
                with self._contact_import_lock:
                    self._contact_import_cancellations.pop(job_id, None)

        threading.Thread(
            target=run,
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
                            saved = self._contact_store.upsert_contact(
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
                                duplicate_policy="update",
                                category_policy="merge",
                                status_policy="preserve",
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
                                saved = self._contact_store.upsert_contact(
                                    contact_row,
                                    duplicate_policy="update",
                                    category_policy="merge",
                                    status_policy="preserve",
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
            if job is None:
                raise CompositionValidationError(
                    "Contact import job was not found.",
                    code="api_contact_import_job_not_found",
                )
            copied = dict(job)
            copied["progress"] = dict(job["progress"])
            return {"ok": True, "job": copied}

    def _contact_import_cancel(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        job_id = str(payload.get("job_id") or "").strip()
        with self._contact_import_lock:
            job = self._contact_import_jobs.get(job_id)
            if job is None:
                raise CompositionValidationError(
                    "Contact import job was not found.",
                    code="api_contact_import_job_not_found",
                )
            cancellation = self._contact_import_cancellations.get(job_id)
            if cancellation is not None and job["state"] in {"queued", "running"}:
                cancellation.set()
                job["state"] = "cancelling"
            copied = dict(job)
            copied["progress"] = dict(job["progress"])
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
        task_id = uuid.uuid4().hex
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
                result = self._run_eitaa(priority=priority, kind=kind, callback=callback)
            except Exception as exc:
                converted = self._error_response(exc)
                error = converted.payload.get("error") or {}
                with self._jobs_lock:
                    state["status"] = "failed"
                    state["error_type"] = type(exc).__name__
                    state["error"] = error
                    state["finished_at"] = datetime.now(timezone.utc).isoformat()
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

        threading.Thread(target=worker, name=f"bridge-{kind}-{task_id[:8]}", daemon=True).start()
        return {"ok": True, "task": dict(state)}

    def _background_status(self, query: Mapping[str, str]) -> dict[str, Any]:
        task_id = str(query.get("task_id", "")).strip()
        with self._jobs_lock:
            if task_id:
                task = self._background_tasks.get(task_id)
                if task is None:
                    raise CompositionValidationError(
                        "Background task was not found.", code="api_background_task_not_found"
                    )
                return {"ok": True, "task": dict(task)}
            tasks = sorted(
                (dict(item) for item in self._background_tasks.values()),
                key=lambda item: str(item.get("created_at", "")),
                reverse=True,
            )[:50]
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
        return path.resolve() if path.is_absolute() else (self.base_directory / path).resolve()

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
