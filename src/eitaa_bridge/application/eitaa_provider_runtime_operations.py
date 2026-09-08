"""Bounded Eitaa application operations owned by one account runtime.

This module is the provider-specific execution side of the Phase 11-B2
orchestrator.  It accepts only high-level DTO fields, resolves every peer and
file from account-owned server state, and never returns a provider object or a
filesystem path.  The same implementation can run in an in-process account
runtime or behind the authenticated Child-process RPC boundary.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import mimetypes
from pathlib import Path
import re
import time
from typing import Any, Callable, Iterator, Mapping
import uuid

from eitaa_core import MediaDownloadOptions, PeerType, PhoneNumber, load_peer_file

from ..config import BridgeConfig
from ..errors import BridgeError, CompositionValidationError
from ..facade import EitaaBridge
from ..infrastructure.coordinator import masked_phone, validate_canonical_e164
from .account_runtime import EitaaAccountRuntime
from .scheduler import EitaaPriority


_OPAQUE_REFERENCE = re.compile(r"^[A-Za-z0-9._:-]{1,256}$")
_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{16,128}$")
_SENDER_REFERENCE = re.compile(r"^[A-Za-z0-9._:-]{1,256}$")
_CACHE_REFERENCE = re.compile(r"^[0-9a-f]{32}$")
_HISTORY_TEXT_BUDGET_BYTES = 512 * 1024
_MEDIA_CHUNK_MAX_BYTES = 192 * 1024


class EitaaProviderRuntimeOperations:
    """Execute generic provider operations inside exactly one Eitaa runtime."""

    def __init__(self, runtime: EitaaAccountRuntime, config: BridgeConfig) -> None:
        if not runtime.is_account_scoped:
            raise CompositionValidationError(
                "Provider runtime operations require an account scope.",
                code="eitaa_provider_account_scope_required",
            )
        self.runtime = runtime
        self.config = config
        self.core_opened = False

    @contextmanager
    def _open_bridge(self, site_key: str) -> Iterator[EitaaBridge]:
        self.config.site(site_key)
        opened = EitaaBridge.open(
            self.config.source_file,
            site_key=site_key,
            open_core=True,
            diagnostics=self.runtime.diagnostics,
            reuse_core=self.runtime.scheduler.is_worker_thread(),
            core_config_override=self.runtime.ownership.core,
            data_scope=self.runtime.data_scope,
        )
        self.core_opened = True
        with opened as bridge:
            yield bridge

    def _execute(
        self,
        *,
        priority: EitaaPriority,
        kind: str,
        callback: Callable[[], dict[str, object]],
        timeout: float = 120.0,
    ) -> dict[str, object]:
        result = self.runtime.run_sync(
            priority=priority,
            kind=kind,
            callback=callback,
            timeout=timeout,
        )
        if not isinstance(result, dict):
            raise CompositionValidationError(
                "The Eitaa provider operation returned an invalid result.",
                code="eitaa_provider_result_invalid",
            )
        return result

    @staticmethod
    def _offset_cursor(value: object) -> int:
        if value in {None, ""}:
            return 0
        selected = str(value)
        if not selected.startswith("offset:") or not selected[7:].isdigit():
            raise CompositionValidationError(
                "The provider page cursor is invalid.",
                code="provider_cursor_invalid",
            )
        return int(selected[7:])

    @staticmethod
    def _history_cursor(value: object) -> int | None:
        if value in {None, ""}:
            return None
        selected = str(value)
        if not selected.startswith("before:") or not selected[7:].isdigit():
            raise CompositionValidationError(
                "The provider history cursor is invalid.",
                code="provider_cursor_invalid",
            )
        parsed = int(selected[7:])
        if parsed <= 0:
            raise CompositionValidationError(
                "The provider history cursor is invalid.",
                code="provider_cursor_invalid",
            )
        return parsed

    @staticmethod
    def _bounded_integer(
        value: object,
        *,
        field: str,
        minimum: int,
        maximum: int,
    ) -> int:
        if isinstance(value, bool):
            raise CompositionValidationError(
                "A provider operation integer is invalid.",
                safe_context={"field": field},
                code="eitaa_provider_request_invalid",
            )
        try:
            selected = int(value)
        except (TypeError, ValueError) as exc:
            raise CompositionValidationError(
                "A provider operation integer is invalid.",
                safe_context={"field": field},
                code="eitaa_provider_request_invalid",
            ) from exc
        if not minimum <= selected <= maximum:
            raise CompositionValidationError(
                "A provider operation integer is out of range.",
                safe_context={
                    "field": field,
                    "minimum": minimum,
                    "maximum": maximum,
                },
                code="eitaa_provider_request_invalid",
            )
        return selected

    def _peer_path(self, peer_reference: object) -> Path:
        selected = str(peer_reference or "")
        if not _OPAQUE_REFERENCE.fullmatch(selected):
            raise CompositionValidationError(
                "The provider peer reference is invalid.",
                code="provider_peer_reference_invalid",
            )
        dialog = self.runtime.dialog_catalog.get(selected)
        if dialog is None:
            raise CompositionValidationError(
                "The selected dialog was not found.",
                code="api_dialog_not_found",
            )
        raw = dialog.get("peer_file")
        if not isinstance(raw, str) or not raw.strip():
            raise CompositionValidationError(
                "The selected dialog has no provider peer reference.",
                code="api_peer_file_required",
            )
        candidate = Path(raw).expanduser()
        resolved = (
            candidate.resolve()
            if candidate.is_absolute()
            else (self.runtime.ownership.installation_root / candidate).resolve()
        )
        account_root = self.runtime.ownership.account_data_directory
        if account_root is None:
            raise CompositionValidationError(
                "The provider peer is not account scoped.",
                code="eitaa_provider_account_scope_required",
            )
        try:
            resolved.relative_to(account_root.resolve())
        except ValueError as exc:
            raise CompositionValidationError(
                "The provider peer is outside the selected account.",
                code="api_peer_file_account_boundary",
            ) from exc
        return resolved

    @staticmethod
    def _peer_kind(dialog: Mapping[str, object]) -> str:
        selected = str(dialog.get("display_kind") or "").strip().lower()
        return {
            "personal": "private",
            "group": "group",
            "channel": "channel",
        }.get(selected, "unknown")

    @staticmethod
    def _message_timestamp(value: object) -> int:
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

    def _merge_cached_dialogs(self, bridge: EitaaBridge) -> None:
        peer_directory = self.runtime.peer_directory
        peer_directory.mkdir(parents=True, exist_ok=True)
        entries = bridge.core.discovery.cached_dialogs(active_only=True, limit=10_000)
        active_keys: set[str] = set()
        for entry in entries:
            peer = entry.peer
            if peer.type in {PeerType.USER, PeerType.CHANNEL} and peer.access_hash is None:
                continue
            peer_key = f"{peer.type.value}:{peer.id}"
            active_keys.add(peer_key)
            peer_file = peer_directory / f"{peer.type.value}-{peer.id}.json"
            bridge.core.discovery.save_peer(peer, peer_file)
            self.runtime.dialog_catalog.upsert(
                peer=peer,
                peer_file=peer_file,
                source="remote",
                top_message_id=entry.top_message_id,
                top_message_date=entry.top_message_date,
                unread_count=entry.unread_count,
                unread_mentions_count=entry.unread_mentions_count,
                read_inbox_max_id=entry.read_inbox_max_id,
                pinned=entry.pinned,
                unread_mark=entry.unread_mark,
                folder_id=entry.folder_id,
                technical_kind=entry.kind.value,
                broadcast=entry.broadcast,
                megagroup=entry.megagroup,
                participants_count=entry.participants_count,
                photo_cached_path=entry.photo_cached_path,
                active=True,
            )
        self.runtime.dialog_catalog.mark_remote_snapshot(active_keys, complete=False)

    def list_dialogs(
        self,
        *,
        site_key: str,
        cursor: object,
        limit: object,
    ) -> dict[str, object]:
        offset = self._offset_cursor(cursor)
        selected_limit = self._bounded_integer(
            limit, field="limit", minimum=1, maximum=200
        )
        dialogs = self.runtime.dialog_catalog.list()
        if not dialogs:
            def hydrate() -> dict[str, object]:
                with self._open_bridge(site_key) as bridge:
                    self._merge_cached_dialogs(bridge)
                return {"ok": True}

            try:
                self._execute(
                    priority=EitaaPriority.BACKGROUND,
                    kind="provider.dialogs.cache",
                    callback=hydrate,
                )
            except Exception as exc:
                self.runtime.logger.emit(
                    "dialog_sync_failed",
                    level="warning",
                    fields={
                        "reason_code": "provider_dialog_cache_refresh_failed",
                        "error_type": type(exc).__name__,
                        "error_code": getattr(exc, "code", None),
                    },
                )
            dialogs = self.runtime.dialog_catalog.list()
        page = dialogs[offset : offset + selected_limit]
        payload: list[dict[str, object]] = []
        for item in page:
            peer_reference = str(item.get("peer_key") or "")
            if not _OPAQUE_REFERENCE.fullmatch(peer_reference):
                continue
            peer = item.get("peer") if isinstance(item.get("peer"), Mapping) else {}
            payload.append(
                {
                    "peer_reference": peer_reference,
                    "peer_kind": self._peer_kind(item),
                    "title": str(peer.get("title") or "")[:512],
                    "unread_count": max(0, int(item.get("unread_count") or 0)),
                }
            )
        next_offset = offset + len(page)
        return {
            "dialogs": payload,
            "next_cursor": (
                f"offset:{next_offset}" if next_offset < len(dialogs) else None
            ),
        }

    def load_history(
        self,
        *,
        site_key: str,
        peer_reference: object,
        peer_kind: object,
        cursor: object,
        limit: object,
    ) -> dict[str, object]:
        selected_peer = str(peer_reference or "")
        selected_kind = str(peer_kind or "unknown").strip().lower()
        if selected_kind not in {"private", "group", "channel", "bot", "unknown"}:
            raise CompositionValidationError(
                "The provider peer kind is invalid.",
                code="provider_peer_reference_invalid",
            )
        peer = load_peer_file(self._peer_path(selected_peer))
        before_id = self._history_cursor(cursor)
        selected_limit = self._bounded_integer(
            limit, field="limit", minimum=1, maximum=500
        )

        def operation() -> dict[str, object]:
            with self._open_bridge(site_key) as bridge:
                raw = bridge.application_messages(
                    peer,
                    limit=selected_limit,
                    before_id=before_id,
                )
            messages: list[dict[str, object]] = []
            text_bytes = 0
            transport_truncated = False
            last_message_id: int | None = None
            for item in raw.get("messages") or []:
                if not isinstance(item, Mapping):
                    continue
                message_id = int(item.get("id") or 0)
                if message_id <= 0:
                    continue
                text_value = item.get("text")
                text = str(text_value)[:100_000] if text_value is not None else None
                candidate_bytes = len(text.encode("utf-8")) if text is not None else 0
                if messages and text_bytes + candidate_bytes > _HISTORY_TEXT_BUDGET_BYTES:
                    transport_truncated = True
                    break
                sender = str(item.get("sender_key") or "").strip() or None
                if sender is not None and not _SENDER_REFERENCE.fullmatch(sender):
                    sender = None
                messages.append(
                    {
                        "message_reference": f"message:{message_id}",
                        "peer_reference": selected_peer,
                        "peer_kind": selected_kind,
                        "sender_reference": sender,
                        "sent_at_unix_ms": self._message_timestamp(
                            item.get("date") or item.get("sent_at")
                        ),
                        "text": text,
                    }
                )
                text_bytes += candidate_bytes
                last_message_id = message_id
            next_before = raw.get("next_before_id")
            if transport_truncated and last_message_id is not None:
                next_before = last_message_id
            return {
                "messages": messages,
                "next_cursor": (
                    f"before:{int(next_before)}"
                    if next_before not in {None, ""} and int(next_before) > 0
                    else None
                ),
                "transport_truncated": transport_truncated,
            }

        return self._execute(
            priority=EitaaPriority.ACTIVE_MESSAGES,
            kind="provider.history.query",
            callback=operation,
        )

    def send_text(
        self,
        *,
        site_key: str,
        peer_reference: object,
        text: object,
        idempotency_key: object,
    ) -> dict[str, object]:
        selected_text = str(text or "")
        selected_key = str(idempotency_key or "")
        if not selected_text or len(selected_text) > 100_000 or "\x00" in selected_text:
            raise CompositionValidationError(
                "The provider message text is invalid.",
                code="provider_extension_value_invalid",
            )
        if not _IDEMPOTENCY_KEY.fullmatch(selected_key):
            raise CompositionValidationError(
                "The provider send idempotency key is invalid.",
                code="provider_idempotency_key_invalid",
            )
        peer = load_peer_file(self._peer_path(peer_reference))

        def operation() -> dict[str, object]:
            with self._open_bridge(site_key) as bridge:
                result = bridge.core.send.send_text(peer, selected_text)
            summary = result.safe_summary()
            remote_id = summary.get("message_id") or summary.get("id")
            reference = (
                f"message:{int(remote_id)}"
                if remote_id not in {None, ""} and str(remote_id).isdigit()
                else f"send:{selected_key[:64]}"
            )
            return {"status": "succeeded", "message_reference": reference}

        return self._execute(
            priority=EitaaPriority.ACTIVE_MESSAGES,
            kind="provider.messages.send_text",
            callback=operation,
            timeout=90.0,
        )

    @staticmethod
    def _reference_integer(value: object, *, prefix: str) -> int:
        selected = str(value or "")
        marker = f"{prefix}:"
        suffix = selected[len(marker) :] if selected.startswith(marker) else ""
        if not suffix.isdigit() or int(suffix) <= 0:
            raise CompositionValidationError(
                "The provider numeric reference is invalid.",
                code="provider_reference_invalid",
            )
        return int(suffix)

    @staticmethod
    def _thumbnail_type(media: Any, *, target_edge: int = 420) -> str | None:
        candidates = [
            item
            for item in getattr(media, "photo_sizes", ())
            if getattr(item, "type", None)
        ]
        if not candidates:
            return None

        def dimensions(item: Any) -> tuple[int, int, int]:
            width = int(getattr(item, "width", 0) or 0)
            height = int(getattr(item, "height", 0) or 0)
            size = int(getattr(item, "size", 0) or 0)
            return max(width, height), width * height, size

        usable = [item for item in candidates if dimensions(item)[0] > 0]
        if usable:
            large = [item for item in usable if dimensions(item)[0] >= target_edge]
            selected = min(large, key=dimensions) if large else max(usable, key=dimensions)
        else:
            selected = max(
                candidates,
                key=lambda item: int(getattr(item, "size", 0) or 0),
            )
        return str(selected.type)

    @staticmethod
    def _cached_media_file(directory: Path, prefix: str) -> Path | None:
        if not directory.exists():
            return None
        candidates = [
            item
            for item in directory.glob(f"{prefix}.*")
            if item.is_file() and not item.name.endswith(".partial")
        ]
        return max(candidates, key=lambda item: item.stat().st_mtime, default=None)

    def _register_media_file(self, path: Path, mime_type: str) -> str:
        resolved = path.expanduser().resolve()
        media_root = self.runtime.ownership.core.media_directory.resolve()
        try:
            resolved.relative_to(media_root)
        except ValueError as exc:
            raise CompositionValidationError(
                "The provider media is outside the selected account.",
                code="api_media_cache_account_boundary",
            ) from exc
        reference = uuid.uuid4().hex
        with self.runtime.media_cache_lock:
            self.runtime.media_cache_files[reference] = (
                resolved,
                mime_type,
                time.monotonic(),
                self.runtime.data_scope.scope_key,
            )
            if len(self.runtime.media_cache_files) > 256:
                oldest = sorted(
                    self.runtime.media_cache_files.items(),
                    key=lambda item: item[1][2],
                )[:64]
                for key, _ in oldest:
                    self.runtime.media_cache_files.pop(key, None)
        return reference

    def read_media(
        self,
        *,
        site_key: str,
        peer_reference: object,
        message_reference: object,
        media_reference: object,
        variant: object,
        max_bytes: object,
    ) -> dict[str, object]:
        selected_media_reference = str(media_reference or "")
        if not _OPAQUE_REFERENCE.fullmatch(selected_media_reference):
            raise CompositionValidationError(
                "The provider media reference is invalid.",
                code="provider_media_reference_invalid",
            )
        selected_variant = str(variant or "thumbnail").strip().lower()
        if selected_variant not in {"thumbnail", "full"}:
            raise CompositionValidationError(
                "The provider media variant is invalid.",
                code="provider_media_variant_invalid",
            )
        selected_max = self._bounded_integer(
            max_bytes,
            field="max_bytes",
            minimum=32 * 1024,
            maximum=512 * 1024 * 1024,
        )
        message_id = self._reference_integer(message_reference, prefix="message")
        peer = load_peer_file(self._peer_path(peer_reference))

        def operation() -> dict[str, object]:
            with self._open_bridge(site_key) as bridge:
                message = bridge.core.messages.get(peer, message_id)
                if message is None:
                    raise CompositionValidationError(
                        "Stored message was not found.",
                        safe_context={"message_id": message_id},
                        code="composition_message_not_found",
                    )
                if message.media is None:
                    raise CompositionValidationError(
                        "The selected provider media is unavailable.",
                        code="provider_media_not_found",
                    )
                media = message.media
                media_type = media.type.value
                mime_hint = str(media.mime_type or "").strip().lower()
                is_image = media_type in {"photo", "image_document", "sticker"}
                is_playable = media_type in {"audio", "video"} or mime_hint.startswith(
                    ("audio/", "video/")
                )
                if not is_image and (
                    selected_variant != "full" or not is_playable
                ):
                    raise CompositionValidationError(
                        "The selected provider media has no supported preview.",
                        code="provider_media_not_found",
                    )
                thumbnail = (
                    self._thumbnail_type(media)
                    if selected_variant == "thumbnail"
                    else None
                )
                cache_directory = (
                    bridge.config.core.media_directory
                    / "ui-cache"
                    / selected_variant
                )
                cache_directory.mkdir(parents=True, exist_ok=True)
                remote_id = int(getattr(media, "remote_id", 0) or 0)
                prefix = f"{peer.type.value}_{peer.id}_{message_id}_{remote_id}"
                cache_path = self._cached_media_file(cache_directory, prefix)
                if cache_path is None:
                    result = bridge.core.media.download(
                        media,
                        MediaDownloadOptions(
                            output_directory=cache_directory,
                            file_name=prefix,
                            overwrite=True,
                            max_bytes=(
                                selected_max
                                if selected_variant == "full"
                                else max(selected_max, 64 * 1024 * 1024)
                            ),
                            chunk_size=(
                                256 * 1024
                                if selected_variant == "thumbnail"
                                else 512 * 1024
                            ),
                            request_delay_seconds=(
                                0.0 if selected_variant == "thumbnail" else 0.15
                            ),
                            photo_thumb_type=thumbnail,
                        ),
                    )
                    cache_path = result.path
                size = cache_path.stat().st_size
                if size > selected_max:
                    if selected_variant == "thumbnail":
                        cache_path.unlink(missing_ok=True)
                    raise CompositionValidationError(
                        "Provider media exceeds the requested limit.",
                        safe_context={"bytes": size, "max_bytes": selected_max},
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
                cache_reference = self._register_media_file(cache_path, mime_type)
                return {
                    "media_reference": selected_media_reference,
                    "content_reference": f"cache:{cache_reference}",
                    "mime_type": mime_type,
                    "byte_count": size,
                }

        return self._execute(
            priority=EitaaPriority.MEDIA_PREVIEW,
            kind=f"provider.media.{selected_variant}",
            callback=operation,
            timeout=180.0,
        )

    def read_media_chunk(
        self,
        *,
        cache_reference: object,
        offset: object,
        max_bytes: object,
    ) -> tuple[dict[str, object], bytes]:
        reference = str(cache_reference or "").strip().lower()
        if reference.startswith("cache:"):
            reference = reference[6:]
        if not _CACHE_REFERENCE.fullmatch(reference):
            raise CompositionValidationError(
                "The provider media cache reference is invalid.",
                code="provider_media_content_reference_invalid",
            )
        selected_offset = self._bounded_integer(
            offset,
            field="offset",
            minimum=0,
            maximum=512 * 1024 * 1024,
        )
        selected_max = self._bounded_integer(
            max_bytes,
            field="max_bytes",
            minimum=1,
            maximum=_MEDIA_CHUNK_MAX_BYTES,
        )
        with self.runtime.media_cache_lock:
            item = self.runtime.media_cache_files.get(reference)
            if item is None:
                raise CompositionValidationError(
                    "The provider media cache entry was not found.",
                    code="provider_media_content_not_found",
                )
            path, mime_type, _, scope = item
            if scope != self.runtime.data_scope.scope_key or not path.is_file():
                self.runtime.media_cache_files.pop(reference, None)
                raise CompositionValidationError(
                    "The provider media cache entry is unavailable.",
                    code="provider_media_content_not_found",
                )
            media_root = self.runtime.ownership.core.media_directory.resolve()
            try:
                path.resolve().relative_to(media_root)
            except ValueError as exc:
                self.runtime.media_cache_files.pop(reference, None)
                raise CompositionValidationError(
                    "The provider media cache entry is outside the account.",
                    code="api_media_cache_account_boundary",
                ) from exc
            total = path.stat().st_size
            if selected_offset > total:
                raise CompositionValidationError(
                    "The provider media chunk offset is invalid.",
                    code="provider_media_chunk_offset_invalid",
                )
            with path.open("rb") as handle:
                handle.seek(selected_offset)
                data = handle.read(selected_max)
            next_offset = selected_offset + len(data)
            self.runtime.media_cache_files[reference] = (
                path,
                mime_type,
                time.monotonic(),
                scope,
            )
        return (
            {
                "content_reference": f"cache:{reference}",
                "mime_type": mime_type,
                "total_bytes": total,
                "offset": selected_offset,
                "next_offset": next_offset,
                "eof": next_offset >= total,
            },
            data,
        )

    @staticmethod
    def _contact_display_name(contact: Any) -> str:
        user = contact.user
        return (
            " ".join(
                item
                for item in (
                    str(user.first_name or "").strip(),
                    str(user.last_name or "").strip(),
                )
                if item
            )
            or str(user.username or "")
            or f"کاربر {int(user.peer.id)}"
        )[:512]

    def list_contacts(
        self,
        *,
        site_key: str,
        cursor: object,
        limit: object,
    ) -> dict[str, object]:
        offset = self._offset_cursor(cursor)
        selected_limit = self._bounded_integer(
            limit, field="limit", minimum=1, maximum=500
        )

        def operation() -> dict[str, object]:
            with self._open_bridge(site_key) as bridge:
                snapshot = bridge.core.contacts.list(refresh=False)
            contacts = sorted(
                snapshot.contacts,
                key=lambda item: (
                    self._contact_display_name(item).casefold(),
                    int(item.user.peer.id),
                ),
            )
            page = contacts[offset : offset + selected_limit]
            payload: list[dict[str, object]] = []
            for contact in page:
                user = contact.user
                user_id = int(user.peer.id)
                phone = (
                    str(user.phone)
                    if getattr(user, "phone", None) is not None
                    else ""
                )
                try:
                    hint = masked_phone(phone) if phone else None
                except BridgeError:
                    hint = None
                payload.append(
                    {
                        "contact_reference": f"contact:{user_id}",
                        "display_name": self._contact_display_name(contact),
                        "identity_hint": hint,
                    }
                )
            next_offset = offset + len(page)
            return {
                "contacts": payload,
                "next_cursor": (
                    f"offset:{next_offset}"
                    if next_offset < len(contacts)
                    else None
                ),
            }

        return self._execute(
            priority=EitaaPriority.ACTIVE_MESSAGES,
            kind="provider.contacts.query",
            callback=operation,
        )

    def upsert_contact(
        self,
        *,
        site_key: str,
        identity: object,
        display_name: object,
        idempotency_key: object,
    ) -> dict[str, object]:
        phone = validate_canonical_e164(str(identity or ""))
        selected_name = str(display_name or "").strip()
        selected_key = str(idempotency_key or "")
        if not selected_name or len(selected_name) > 512 or "\x00" in selected_name:
            raise CompositionValidationError(
                "The provider contact name is invalid.",
                code="provider_extension_value_invalid",
            )
        if not _IDEMPOTENCY_KEY.fullmatch(selected_key):
            raise CompositionValidationError(
                "The provider contact idempotency key is invalid.",
                code="provider_idempotency_key_invalid",
            )

        def operation() -> dict[str, object]:
            with self._open_bridge(site_key) as bridge:
                contacts = bridge.core.contacts
                normalized = PhoneNumber.parse(phone)
                existing = contacts.find(normalized, refresh=True)
                requested_names = (selected_name, "")
                existing_names = (
                    (
                        str(existing.user.first_name or "").strip(),
                        str(existing.user.last_name or "").strip(),
                    )
                    if existing is not None
                    else None
                )
                if existing is not None and existing_names != requested_names:
                    imported = contacts.repository.import_contact(
                        normalized,
                        first_name=selected_name,
                        last_name="",
                    )
                    if imported.retry_client_ids:
                        raise CompositionValidationError(
                            "The provider requested a later contact retry.",
                            code="api_eitaa_contact_name_update_retry",
                        )
                    selected = contacts.find(normalized, refresh=True)
                    if selected is None:
                        raise CompositionValidationError(
                            "The provider contact could not be verified.",
                            code="api_eitaa_contact_name_update_missing",
                        )
                    created = False
                else:
                    resolution = contacts.resolve(
                        normalized,
                        first_name=selected_name,
                        last_name="",
                        import_if_missing=True,
                        refresh_contacts=False,
                    )
                    selected = resolution.contact
                    created = bool(resolution.contact_added)
            user_id = int(selected.user.peer.id)
            if user_id <= 0:
                raise CompositionValidationError(
                    "The provider contact receipt is invalid.",
                    code="provider_contact_receipt_invalid",
                )
            return {
                "contact_reference": f"contact:{user_id}",
                "created": created,
            }

        return self._execute(
            priority=EitaaPriority.ACTIVE_MESSAGES,
            kind="provider.contacts.upsert",
            callback=operation,
            timeout=120.0,
        )

    def mark_core_closed(self) -> None:
        self.core_opened = False


__all__ = ["EitaaProviderRuntimeOperations"]
