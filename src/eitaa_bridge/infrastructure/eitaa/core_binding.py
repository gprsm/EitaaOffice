"""Composition through the public eitaa_core package only."""

from __future__ import annotations

from dataclasses import dataclass, fields
from importlib.metadata import PackageNotFoundError, version as package_version
from typing import get_type_hints

from eitaa_core import (
    EitaaCore,
    EitaaCoreConfig,
    MessageSearchQuery,
    __version__ as core_product_version,
)

from ...config import CoreDependencyConfig
from ...errors import CoreCompatibilityError
from ..diagnostics import BridgeDiagnosticManager

EXPECTED_PRODUCT_VERSION = "0.6.0-core7.4.5-gmi1"
EXPECTED_PACKAGE_VERSION = "0.6.0.dev19"
EXPECTED_DATABASE_SCHEMA = 9
REQUIRED_FACADE_FIELDS = {"messages", "retrieval", "media", "publications", "sync", "discovery", "contacts", "send"}
REQUIRED_PUBLICATION_METHODS = {
    "get", "mark_pending", "mark_processing", "mark_published",
    "mark_failed", "mark_skipped", "list",
}
REQUIRED_DISCOVERY_METHODS = {
    "list_all_dialogs", "cached_dialogs", "resolve_peer_photo", "save_peer",
}
REQUIRED_HISTORY_METHODS = {"mark_read"}
REQUIRED_MESSAGE_METHODS = {"list_album"}


@dataclass(slots=True, frozen=True)
class CoreCompatibility:
    product_version: str
    package_version: str
    facade_fields: tuple[str, ...]
    database_schema: int
    publication_workflow: bool
    publication_methods: tuple[str, ...]
    discovery_methods: tuple[str, ...]
    history_methods: tuple[str, ...]
    message_methods: tuple[str, ...]
    sender_filter: bool

    @property
    def ok(self) -> bool:
        return (
            self.product_version == EXPECTED_PRODUCT_VERSION
            and self.package_version == EXPECTED_PACKAGE_VERSION
            and REQUIRED_FACADE_FIELDS.issubset(self.facade_fields)
            and self.database_schema == EXPECTED_DATABASE_SCHEMA
            and self.publication_workflow
            and REQUIRED_PUBLICATION_METHODS.issubset(self.publication_methods)
            and REQUIRED_DISCOVERY_METHODS.issubset(self.discovery_methods)
            and REQUIRED_HISTORY_METHODS.issubset(self.history_methods)
            and REQUIRED_MESSAGE_METHODS.issubset(self.message_methods)
            and self.sender_filter
        )

    def safe_summary(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "product_version": self.product_version,
            "package_version": self.package_version,
            "required_facade_fields_present": REQUIRED_FACADE_FIELDS.issubset(self.facade_fields),
            "database_schema": self.database_schema,
            "publication_workflow": self.publication_workflow,
            "required_publication_methods_present": REQUIRED_PUBLICATION_METHODS.issubset(self.publication_methods),
            "required_discovery_methods_present": REQUIRED_DISCOVERY_METHODS.issubset(self.discovery_methods),
            "required_history_methods_present": REQUIRED_HISTORY_METHODS.issubset(self.history_methods),
            "required_message_methods_present": REQUIRED_MESSAGE_METHODS.issubset(self.message_methods),
            "sender_filter": self.sender_filter,
        }


class CoreBinding:
    def __init__(self, config: CoreDependencyConfig, diagnostics: BridgeDiagnosticManager | None = None) -> None:
        self.config = config
        self.diagnostics = diagnostics

    def inspect(self) -> CoreCompatibility:
        try:
            installed = package_version("eitaa-core")
        except PackageNotFoundError as exc:
            raise CoreCompatibilityError("The eitaa-core package is not installed.") from exc
        facade_fields = tuple(item.name for item in fields(EitaaCore))
        type_hints = get_type_hints(EitaaCore)
        publication_type = type_hints.get("publications")
        discovery_type = type_hints.get("discovery")
        history_type = type_hints.get("history")
        message_type = type_hints.get("messages")
        publication_methods = tuple(
            name for name in REQUIRED_PUBLICATION_METHODS
            if publication_type is not None and callable(getattr(publication_type, name, None))
        )
        discovery_methods = tuple(
            name for name in REQUIRED_DISCOVERY_METHODS
            if discovery_type is not None and callable(getattr(discovery_type, name, None))
        )
        history_methods = tuple(
            name for name in REQUIRED_HISTORY_METHODS
            if history_type is not None and callable(getattr(history_type, name, None))
        )
        message_methods = tuple(
            name for name in REQUIRED_MESSAGE_METHODS
            if message_type is not None and callable(getattr(message_type, name, None))
        )
        compatibility = CoreCompatibility(
            product_version=core_product_version,
            package_version=installed,
            facade_fields=facade_fields,
            database_schema=EXPECTED_DATABASE_SCHEMA,
            publication_workflow=callable(getattr(EitaaCore, "capabilities", None)),
            publication_methods=publication_methods,
            discovery_methods=discovery_methods,
            history_methods=history_methods,
            message_methods=message_methods,
            sender_filter="sender" in {item.name for item in fields(MessageSearchQuery)},
        )
        if self.diagnostics:
            self.diagnostics.emit("core_binding", "core_inspected", fields=compatibility.safe_summary())
        return compatibility

    def assert_compatible(self) -> CoreCompatibility:
        compatibility = self.inspect()
        if not compatibility.ok:
            debug_file = None
            if self.diagnostics:
                debug_file = self.diagnostics.emit(
                    "core_binding", "core_incompatible", level="error", fields=compatibility.safe_summary()
                )
            raise CoreCompatibilityError(
                "Installed Core does not match the approved grouped-media contract.",
                safe_context=compatibility.safe_summary(),
                debug_file=debug_file,
            )
        return compatibility

    def open(self) -> EitaaCore:
        self.assert_compatible()
        core_config = EitaaCoreConfig(
            session_file=self.config.session_file,
            database_file=self.config.database_file,
            media_directory=self.config.media_directory,
            diagnostics_root=self.config.diagnostics_root,
            diagnostics_enabled=self.config.diagnostics_enabled,
            timeout_seconds=self.config.timeout_seconds,
        )
        try:
            core = EitaaCore.open(core_config)
        except Exception as exc:
            debug_file = None
            if self.diagnostics:
                debug_file = self.diagnostics.emit(
                    "core_binding",
                    "core_open_failed",
                    level="error",
                    fields={"error_type": type(exc).__name__},
                )
            raise CoreCompatibilityError(
                "Core grouped-media build could not be opened through its public facade.",
                safe_context={"error_type": type(exc).__name__},
                debug_file=debug_file,
            ) from exc
        if self.diagnostics:
            self.diagnostics.emit(
                "core_binding",
                "core_opened",
                fields={"capabilities": core.capabilities(), "session_present": True},
            )
        return core
