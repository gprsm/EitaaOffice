from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Iterable

from eitaa_core import Peer


class JsonDialogCatalog:
    """Bridge-owned UI metadata layered over Core's persistent dialog cache.

    Core 7.4.5 GMI 1 is the source of truth for remote dialogs, classification,
    unread counters, and avatar cache paths. This small JSON catalogue keeps
    only UI concerns that Core should not own: favorites, manual peers, peer
    files, and an optional human override of the displayed kind.
    """

    SCHEMA = 2
    _DISPLAY_KINDS = {"channel", "group", "personal"}
    _TECHNICAL_KINDS = {"private", "basic_group", "supergroup", "channel", "unknown"}

    def __init__(self, path: str | Path, *, base_directory: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.base_directory = Path(base_directory).expanduser().resolve()
        self._lock = RLock()

    @staticmethod
    def key(peer: Peer) -> str:
        return f"{peer.type.value}:{peer.id}"

    @classmethod
    def default_display_kind(cls, peer: Peer, technical_kind: str | None = None) -> str:
        if technical_kind == "private":
            return "personal"
        if technical_kind in {"basic_group", "supergroup"}:
            return "group"
        if technical_kind == "channel":
            return "channel"
        if peer.type.value == "user":
            return "personal"
        if peer.type.value == "chat":
            return "group"
        return "channel"

    def list(self, *, include_inactive: bool = False) -> list[dict[str, Any]]:
        with self._lock:
            data = self._read()
            values = [
                item for item in data["dialogs"].values()
                if include_inactive or bool(item.get("active", True)) or item.get("source") == "manual"
            ]
        return sorted(
            values,
            key=lambda item: (
                not bool(item.get("pinned")),
                -int(item.get("top_message_date") or 0),
                -int(item.get("top_message_id") or 0),
                str((item.get("peer") or {}).get("title") or ""),
            ),
        )

    def get(self, peer_key: str) -> dict[str, Any] | None:
        with self._lock:
            value = self._read()["dialogs"].get(peer_key)
            return dict(value) if isinstance(value, dict) else None

    def upsert(
        self,
        *,
        peer: Peer,
        peer_file: str | Path,
        source: str,
        top_message_id: int = 0,
        top_message_date: int | None = None,
        unread_count: int = 0,
        unread_mentions_count: int = 0,
        read_inbox_max_id: int = 0,
        pinned: bool = False,
        unread_mark: bool = False,
        folder_id: int | None = None,
        technical_kind: str | None = None,
        broadcast: bool = False,
        megagroup: bool = False,
        participants_count: int | None = None,
        photo_cached_path: str | None = None,
        active: bool = True,
        display_kind: str | None = None,
    ) -> dict[str, Any]:
        if technical_kind is not None and technical_kind not in self._TECHNICAL_KINDS:
            technical_kind = "unknown"
        selected_kind = display_kind or self.default_display_kind(peer, technical_kind)
        if selected_kind not in self._DISPLAY_KINDS:
            raise ValueError("Unsupported display_kind.")
        peer_path = Path(peer_file).expanduser().resolve()
        try:
            stored_path = peer_path.relative_to(self.base_directory).as_posix()
        except ValueError:
            stored_path = peer_path.as_posix()
        now = datetime.now(timezone.utc).isoformat()
        peer_key = self.key(peer)
        with self._lock:
            data = self._read()
            previous = data["dialogs"].get(peer_key, {})
            previous_source = str(previous.get("source") or "")
            stored_source = previous_source if previous_source == "manual" and source == "remote" else source
            entry = {
                "peer_key": peer_key,
                "peer": {
                    **peer.safe_summary(),
                    "title": peer.title,
                    "username": peer.username,
                },
                "peer_file": stored_path,
                "technical_kind": technical_kind or str(previous.get("technical_kind") or "unknown"),
                "display_kind": (
                    str(previous.get("display_kind"))
                    if previous.get("display_kind_locked")
                    else selected_kind
                ),
                "display_kind_locked": bool(previous.get("display_kind_locked", False)),
                "favorite": bool(previous.get("favorite", False)),
                "source": stored_source,
                "active": bool(active),
                "top_message_id": int(top_message_id or 0),
                "top_message_date": top_message_date,
                "unread_count": int(unread_count or 0),
                "unread_mentions_count": int(unread_mentions_count or 0),
                "read_inbox_max_id": int(read_inbox_max_id or 0),
                "pinned": bool(pinned),
                "unread_mark": bool(unread_mark),
                "folder_id": folder_id,
                "broadcast": bool(broadcast),
                "megagroup": bool(megagroup),
                "participants_count": participants_count,
                "photo_cached_path": photo_cached_path,
                "created_at": str(previous.get("created_at") or now),
                "updated_at": now,
            }
            data["dialogs"][peer_key] = entry
            self._write(data)
            return dict(entry)

    def merge(self, entries: Iterable[dict[str, Any]]) -> int:
        count = 0
        for item in entries:
            self.upsert(**item)
            count += 1
        return count

    def mark_remote_snapshot(self, active_peer_keys: set[str], *, complete: bool) -> int:
        """Hide missing remote rows only after a complete Core snapshot."""
        if not complete:
            return 0
        changed = 0
        with self._lock:
            data = self._read()
            for peer_key, item in data["dialogs"].items():
                if not isinstance(item, dict) or item.get("source") == "manual":
                    continue
                new_active = peer_key in active_peer_keys
                if bool(item.get("active", True)) != new_active:
                    item["active"] = new_active
                    item["updated_at"] = datetime.now(timezone.utc).isoformat()
                    changed += 1
            if changed:
                self._write(data)
        return changed

    def set_favorite(self, peer_key: str, favorite: bool) -> dict[str, Any]:
        return self._patch(peer_key, favorite=bool(favorite))

    def set_display_kind(self, peer_key: str, display_kind: str) -> dict[str, Any]:
        if display_kind not in self._DISPLAY_KINDS:
            raise ValueError("Unsupported display_kind.")
        return self._patch(peer_key, display_kind=display_kind, display_kind_locked=True)

    def set_photo_cached_path(self, peer_key: str, path: str) -> dict[str, Any]:
        return self._patch(peer_key, photo_cached_path=path)

    def mark_read(
        self,
        peer_key: str,
        *,
        max_id: int | None = None,
        remaining_unread_count: int | None = None,
    ) -> dict[str, Any]:
        remaining = 0 if remaining_unread_count is None else max(0, int(remaining_unread_count))
        changes: dict[str, Any] = {
            "unread_count": remaining,
            "unread_mentions_count": 0 if remaining == 0 else None,
            "unread_mark": remaining > 0,
        }
        if changes["unread_mentions_count"] is None:
            changes.pop("unread_mentions_count")
        if max_id is not None:
            changes["read_inbox_max_id"] = int(max_id)
        return self._patch(peer_key, **changes)

    def _patch(self, peer_key: str, **changes: Any) -> dict[str, Any]:
        with self._lock:
            data = self._read()
            current = data["dialogs"].get(peer_key)
            if not isinstance(current, dict):
                raise KeyError(peer_key)
            current.update(changes)
            current["updated_at"] = datetime.now(timezone.utc).isoformat()
            data["dialogs"][peer_key] = current
            self._write(data)
            return dict(current)

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema_version": self.SCHEMA, "dialogs": {}}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            return {"schema_version": self.SCHEMA, "dialogs": {}}
        if not isinstance(payload, dict):
            return {"schema_version": self.SCHEMA, "dialogs": {}}
        schema = payload.get("schema_version")
        dialogs = payload.get("dialogs")
        if schema not in {1, self.SCHEMA} or not isinstance(dialogs, dict):
            return {"schema_version": self.SCHEMA, "dialogs": {}}
        if schema == 1:
            for item in dialogs.values():
                if isinstance(item, dict):
                    item.setdefault("technical_kind", "unknown")
                    item.setdefault("active", True)
                    item.setdefault("top_message_date", None)
                    item.setdefault("broadcast", False)
                    item.setdefault("megagroup", False)
                    item.setdefault("participants_count", None)
                    item.setdefault("photo_cached_path", None)
        return {"schema_version": self.SCHEMA, "dialogs": dialogs}

    def _write(self, data: dict[str, Any]) -> None:
        data["schema_version"] = self.SCHEMA
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(prefix=self.path.name + ".", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
