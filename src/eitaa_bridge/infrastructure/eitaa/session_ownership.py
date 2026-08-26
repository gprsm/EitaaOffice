"""Explicit, side-effect-free ownership contract for Eitaa session storage.

This module deliberately does not select an account, open Core, create
directories, or modify runtime behavior. It gives the next migration phase a
single fail-closed source of truth for legacy and MessengerAccount-scoped paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
import os
import time
from uuid import UUID

from ...config import CoreDependencyConfig
from ...errors import SessionOwnershipError


ACCOUNT_SESSION_RELATIVE_PATH = PurePosixPath(
    "provider/session/eitaa_session.json"
)
ACCOUNT_CORE_DATABASE_RELATIVE_PATH = PurePosixPath("core/messages.sqlite3")
ACCOUNT_MEDIA_RELATIVE_PATH = PurePosixPath("media")
ACCOUNT_CONTENT_INDEX_RELATIVE_PATH = PurePosixPath(
    "index/content_index.sqlite3"
)
ACCOUNT_SENDER_DIRECTORY_RELATIVE_PATH = PurePosixPath(
    "provider/state/sender_directory.sqlite3"
)
ACCOUNT_DIALOG_CATALOG_RELATIVE_PATH = PurePosixPath(
    "provider/state/ui-peers/catalog.json"
)
ACCOUNT_CONTACT_PEERS_RELATIVE_PATH = PurePosixPath(
    "provider/state/contact-peers"
)


class SessionOwnershipMode(str, Enum):
    """The only two permitted Eitaa session-owner modes during migration."""

    LEGACY = "legacy"
    MESSENGER_ACCOUNT = "messenger_account"


def canonical_messenger_account_id(value: str) -> str:
    """Return a canonical UUIDv4 account identifier or fail without echoing it."""

    try:
        parsed = UUID(str(value))
    except (ValueError, AttributeError, TypeError) as exc:
        raise SessionOwnershipError(
            "The MessengerAccount identifier is invalid.",
            code="session_owner_identifier_invalid",
        ) from exc
    if parsed.version != 4 or str(parsed) != value:
        raise SessionOwnershipError(
            "The MessengerAccount identifier is invalid.",
            code="session_owner_identifier_invalid",
        )
    return value


def _within(installation_root: Path, candidate: Path, *, field: str) -> Path:
    root = installation_root.expanduser().resolve(strict=False)
    lexical = candidate.expanduser().absolute()
    try:
        lexical.relative_to(root)
    except ValueError as exc:
        raise SessionOwnershipError(
            "A session-owned path is outside the installation.",
            safe_context={"field": field},
            code="session_owner_path_outside_installation",
        ) from exc
    # On Windows, resolving a missing leaf while another process materializes
    # its parent can transiently return a path outside the lexical root. Retry
    # only candidates already proven lexically inside; a real junction/symlink
    # escape remains outside on every pass and is still rejected fail-closed.
    attempts = 5 if os.name == "nt" else 1
    for attempt in range(attempts):
        selected = candidate.expanduser().resolve(strict=False)
        try:
            selected.relative_to(root)
            return selected
        except ValueError:
            if attempt + 1 < attempts:
                time.sleep(0.001)
    raise SessionOwnershipError(
        "A session-owned path is outside the installation.",
        safe_context={"field": field},
        code="session_owner_path_outside_installation",
    )


def _account_path(
    installation_root: Path,
    account_data_directory: Path,
    relative: PurePosixPath,
    *,
    field: str,
) -> Path:
    return _within(
        installation_root,
        account_data_directory.joinpath(*relative.parts),
        field=field,
    )


@dataclass(frozen=True, slots=True)
class EitaaSessionOwnership:
    """Complete path boundary owned by one Eitaa session.

    ``legacy`` preserves the current shared layout explicitly. The
    ``messenger_account`` mode derives every provider-owned path from one
    canonical MessengerAccount UUID. Worker paths are intentionally absent in
    legacy mode because the current application process is not an account
    worker.
    """

    installation_root: Path
    mode: SessionOwnershipMode
    messenger_account_id: str | None
    core: CoreDependencyConfig
    account_data_directory: Path | None
    account_runtime_directory: Path | None
    provider_session_directory: Path
    provider_state_directory: Path
    content_index_file: Path
    sender_directory_file: Path
    dialog_catalog_file: Path
    contact_peers_directory: Path
    worker_diagnostics_root: Path | None
    worker_log_file: Path | None
    worker_lock_file: Path | None
    worker_cache_directory: Path | None

    def __post_init__(self) -> None:
        root = self.installation_root.expanduser().resolve(strict=False)
        if root != self.installation_root:
            raise SessionOwnershipError(
                "The session ownership contract is not canonical.",
                safe_context={"field": "installation_root"},
                code="session_owner_contract_invalid",
            )
        self.core.validate()
        owned_paths = {
            "core.session_file": self.core.session_file,
            "core.database_file": self.core.database_file,
            "core.media_directory": self.core.media_directory,
            "core.diagnostics_root": self.core.diagnostics_root,
            "provider_session_directory": self.provider_session_directory,
            "provider_state_directory": self.provider_state_directory,
            "content_index_file": self.content_index_file,
            "sender_directory_file": self.sender_directory_file,
            "dialog_catalog_file": self.dialog_catalog_file,
            "contact_peers_directory": self.contact_peers_directory,
        }
        if self.worker_diagnostics_root is not None:
            owned_paths["worker_diagnostics_root"] = self.worker_diagnostics_root
        for field, path in owned_paths.items():
            if _within(root, path, field=field) != path:
                raise SessionOwnershipError(
                    "The session ownership contract is not canonical.",
                    safe_context={"field": field},
                    code="session_owner_contract_invalid",
                )
        if self.mode is SessionOwnershipMode.LEGACY:
            if any(
                value is not None
                for value in (
                    self.messenger_account_id,
                    self.account_data_directory,
                    self.account_runtime_directory,
                    self.worker_diagnostics_root,
                    self.worker_log_file,
                    self.worker_lock_file,
                    self.worker_cache_directory,
                )
            ):
                raise SessionOwnershipError(
                    "Legacy session ownership cannot claim an account worker.",
                    code="session_owner_contract_invalid",
                )
            data_root = _within(root, root / "data", field="data_root")
            legacy_paths = {
                "provider_session_directory": (
                    self.provider_session_directory,
                    self.core.session_file.parent,
                ),
                "provider_state_directory": (
                    self.provider_state_directory,
                    data_root,
                ),
                "content_index_file": (
                    self.content_index_file,
                    data_root / "content_index.sqlite3",
                ),
                "sender_directory_file": (
                    self.sender_directory_file,
                    data_root / "sender_directory.sqlite3",
                ),
                "dialog_catalog_file": (
                    self.dialog_catalog_file,
                    data_root / "ui-peers" / "catalog.json",
                ),
                "contact_peers_directory": (
                    self.contact_peers_directory,
                    data_root / "eitaa-contact-peers",
                ),
            }
            for field, (actual, expected) in legacy_paths.items():
                if actual != expected:
                    raise SessionOwnershipError(
                        "The legacy path contract is inconsistent.",
                        safe_context={"field": field},
                        code="session_owner_contract_invalid",
                    )
            return
        if self.mode is not SessionOwnershipMode.MESSENGER_ACCOUNT:
            raise SessionOwnershipError(
                "The session ownership mode is unsupported.",
                code="session_owner_mode_invalid",
            )
        if self.messenger_account_id is None:
            raise SessionOwnershipError(
                "MessengerAccount ownership requires an account identifier.",
                code="session_owner_contract_invalid",
            )
        selected_id = canonical_messenger_account_id(self.messenger_account_id)
        expected_data = _within(
            root,
            root / "data" / "accounts" / selected_id,
            field="account_data_directory",
        )
        expected_runtime = _within(
            root,
            root / "runtime" / "accounts" / selected_id,
            field="account_runtime_directory",
        )
        expected_paths = {
            "account_data_directory": (self.account_data_directory, expected_data),
            "account_runtime_directory": (
                self.account_runtime_directory,
                expected_runtime,
            ),
            "core.session_file": (
                self.core.session_file,
                _account_path(
                    root,
                    expected_data,
                    ACCOUNT_SESSION_RELATIVE_PATH,
                    field="core.session_file",
                ),
            ),
            "core.database_file": (
                self.core.database_file,
                _account_path(
                    root,
                    expected_data,
                    ACCOUNT_CORE_DATABASE_RELATIVE_PATH,
                    field="core.database_file",
                ),
            ),
            "core.media_directory": (
                self.core.media_directory,
                _account_path(
                    root,
                    expected_data,
                    ACCOUNT_MEDIA_RELATIVE_PATH,
                    field="core.media_directory",
                ),
            ),
            "core.diagnostics_root": (
                self.core.diagnostics_root,
                _within(
                    root,
                    expected_runtime / "diagnostics" / "core",
                    field="core.diagnostics_root",
                ),
            ),
            "provider_session_directory": (
                self.provider_session_directory,
                _account_path(
                    root,
                    expected_data,
                    ACCOUNT_SESSION_RELATIVE_PATH.parent,
                    field="provider_session_directory",
                ),
            ),
            "provider_state_directory": (
                self.provider_state_directory,
                _account_path(
                    root,
                    expected_data,
                    ACCOUNT_SENDER_DIRECTORY_RELATIVE_PATH.parent,
                    field="provider_state_directory",
                ),
            ),
            "content_index_file": (
                self.content_index_file,
                _account_path(
                    root,
                    expected_data,
                    ACCOUNT_CONTENT_INDEX_RELATIVE_PATH,
                    field="content_index_file",
                ),
            ),
            "sender_directory_file": (
                self.sender_directory_file,
                _account_path(
                    root,
                    expected_data,
                    ACCOUNT_SENDER_DIRECTORY_RELATIVE_PATH,
                    field="sender_directory_file",
                ),
            ),
            "dialog_catalog_file": (
                self.dialog_catalog_file,
                _account_path(
                    root,
                    expected_data,
                    ACCOUNT_DIALOG_CATALOG_RELATIVE_PATH,
                    field="dialog_catalog_file",
                ),
            ),
            "contact_peers_directory": (
                self.contact_peers_directory,
                _account_path(
                    root,
                    expected_data,
                    ACCOUNT_CONTACT_PEERS_RELATIVE_PATH,
                    field="contact_peers_directory",
                ),
            ),
            "worker_diagnostics_root": (
                self.worker_diagnostics_root,
                _within(
                    root,
                    expected_runtime / "diagnostics" / "worker",
                    field="worker_diagnostics_root",
                ),
            ),
            "worker_log_file": (
                self.worker_log_file,
                _within(
                    root,
                    expected_runtime / "logs" / "worker.jsonl",
                    field="worker_log_file",
                ),
            ),
            "worker_lock_file": (
                self.worker_lock_file,
                _within(
                    root,
                    expected_runtime / "worker.lock",
                    field="worker_lock_file",
                ),
            ),
            "worker_cache_directory": (
                self.worker_cache_directory,
                _within(
                    root,
                    expected_runtime / "cache",
                    field="worker_cache_directory",
                ),
            ),
        }
        for field, (actual, expected) in expected_paths.items():
            if actual != expected:
                raise SessionOwnershipError(
                    "The MessengerAccount path contract is inconsistent.",
                    safe_context={"field": field},
                    code="session_owner_contract_invalid",
                )

    @classmethod
    def legacy(
        cls,
        installation_root: str | Path,
        core: CoreDependencyConfig,
    ) -> "EitaaSessionOwnership":
        """Describe the current shared paths without inferring an account."""

        root = Path(installation_root).expanduser().resolve(strict=False)
        core.validate()
        legacy_core = CoreDependencyConfig(
            session_file=_within(
                root, core.session_file, field="core.session_file"
            ),
            database_file=_within(
                root, core.database_file, field="core.database_file"
            ),
            media_directory=_within(
                root, core.media_directory, field="core.media_directory"
            ),
            diagnostics_root=_within(
                root, core.diagnostics_root, field="core.diagnostics_root"
            ),
            diagnostics_enabled=core.diagnostics_enabled,
            timeout_seconds=core.timeout_seconds,
        )
        data_root = _within(root, root / "data", field="data_root")
        return cls(
            installation_root=root,
            mode=SessionOwnershipMode.LEGACY,
            messenger_account_id=None,
            core=legacy_core,
            account_data_directory=None,
            account_runtime_directory=None,
            provider_session_directory=legacy_core.session_file.parent,
            provider_state_directory=data_root,
            content_index_file=_within(
                root,
                data_root / "content_index.sqlite3",
                field="content_index_file",
            ),
            sender_directory_file=_within(
                root,
                data_root / "sender_directory.sqlite3",
                field="sender_directory_file",
            ),
            dialog_catalog_file=_within(
                root,
                data_root / "ui-peers" / "catalog.json",
                field="dialog_catalog_file",
            ),
            contact_peers_directory=_within(
                root,
                data_root / "eitaa-contact-peers",
                field="contact_peers_directory",
            ),
            worker_diagnostics_root=None,
            worker_log_file=None,
            worker_lock_file=None,
            worker_cache_directory=None,
        )

    @classmethod
    def for_messenger_account(
        cls,
        installation_root: str | Path,
        messenger_account_id: str,
        *,
        core_template: CoreDependencyConfig,
    ) -> "EitaaSessionOwnership":
        """Derive isolated paths for exactly one canonical MessengerAccount."""

        root = Path(installation_root).expanduser().resolve(strict=False)
        selected_id = canonical_messenger_account_id(messenger_account_id)
        core_template.validate()
        account_data = _within(
            root,
            root / "data" / "accounts" / selected_id,
            field="account_data_directory",
        )
        account_runtime = _within(
            root,
            root / "runtime" / "accounts" / selected_id,
            field="account_runtime_directory",
        )
        provider_session = _account_path(
            root,
            account_data,
            ACCOUNT_SESSION_RELATIVE_PATH.parent,
            field="provider_session_directory",
        )
        provider_state = _account_path(
            root,
            account_data,
            ACCOUNT_SENDER_DIRECTORY_RELATIVE_PATH.parent,
            field="provider_state_directory",
        )
        core = CoreDependencyConfig(
            session_file=_account_path(
                root,
                account_data,
                ACCOUNT_SESSION_RELATIVE_PATH,
                field="core.session_file",
            ),
            database_file=_account_path(
                root,
                account_data,
                ACCOUNT_CORE_DATABASE_RELATIVE_PATH,
                field="core.database_file",
            ),
            media_directory=_account_path(
                root,
                account_data,
                ACCOUNT_MEDIA_RELATIVE_PATH,
                field="core.media_directory",
            ),
            diagnostics_root=_within(
                root,
                account_runtime / "diagnostics" / "core",
                field="core.diagnostics_root",
            ),
            diagnostics_enabled=core_template.diagnostics_enabled,
            timeout_seconds=core_template.timeout_seconds,
        )
        return cls(
            installation_root=root,
            mode=SessionOwnershipMode.MESSENGER_ACCOUNT,
            messenger_account_id=selected_id,
            core=core,
            account_data_directory=account_data,
            account_runtime_directory=account_runtime,
            provider_session_directory=provider_session,
            provider_state_directory=provider_state,
            content_index_file=_account_path(
                root,
                account_data,
                ACCOUNT_CONTENT_INDEX_RELATIVE_PATH,
                field="content_index_file",
            ),
            sender_directory_file=_account_path(
                root,
                account_data,
                ACCOUNT_SENDER_DIRECTORY_RELATIVE_PATH,
                field="sender_directory_file",
            ),
            dialog_catalog_file=_account_path(
                root,
                account_data,
                ACCOUNT_DIALOG_CATALOG_RELATIVE_PATH,
                field="dialog_catalog_file",
            ),
            contact_peers_directory=_account_path(
                root,
                account_data,
                ACCOUNT_CONTACT_PEERS_RELATIVE_PATH,
                field="contact_peers_directory",
            ),
            worker_diagnostics_root=_within(
                root,
                account_runtime / "diagnostics" / "worker",
                field="worker_diagnostics_root",
            ),
            worker_log_file=_within(
                root,
                account_runtime / "logs" / "worker.jsonl",
                field="worker_log_file",
            ),
            worker_lock_file=_within(
                root,
                account_runtime / "worker.lock",
                field="worker_lock_file",
            ),
            worker_cache_directory=_within(
                root,
                account_runtime / "cache",
                field="worker_cache_directory",
            ),
        )

    def safe_summary(self) -> dict[str, object]:
        """Return account-safe metadata without installation or secret paths."""

        return {
            "mode": self.mode.value,
            "provider": "eitaa",
            "messenger_account_id": self.messenger_account_id,
            "account_directory_name": (
                self.account_data_directory.name
                if self.account_data_directory is not None
                else None
            ),
            "session_file_name": self.core.session_file.name,
            "database_file_name": self.core.database_file.name,
            "worker_runtime_scoped": self.account_runtime_directory is not None,
        }
