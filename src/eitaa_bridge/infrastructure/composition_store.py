from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock

from ..domain.composer import CompositionRecord
from ..errors import CompositionStateError


class JsonCompositionStore:
    """Bridge-owned atomic JSON state; Core SQLite remains untouched."""

    _lock = RLock()

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()

    def get(self, site_key: str, composition_key: str) -> CompositionRecord | None:
        data = self._load()
        raw = data.get(self._key(site_key, composition_key))
        return CompositionRecord.from_json(raw) if isinstance(raw, dict) else None

    def save(self, record: CompositionRecord) -> CompositionRecord:
        with self._lock:
            data = self._load()
            key = self._key(record.site_key, record.composition_key)
            existing = data.get(key)
            created_at = record.created_at
            if isinstance(existing, dict) and existing.get("created_at"):
                created_at = datetime.fromisoformat(str(existing["created_at"]))
            saved = replace(
                record,
                created_at=created_at,
                updated_at=datetime.now(timezone.utc),
            )
            data[key] = saved.to_json()
            self._write(data)
            return saved

    def find_by_source(self, site_key: str, source_key: str) -> tuple[CompositionRecord, ...]:
        found: list[CompositionRecord] = []
        for raw in self._load().values():
            if not isinstance(raw, dict) or raw.get("site_key") != site_key:
                continue
            if source_key in raw.get("source_keys", []):
                found.append(CompositionRecord.from_json(raw))
        return tuple(sorted(found, key=lambda item: item.updated_at, reverse=True))

    def list(self, site_key: str | None = None, limit: int = 100) -> tuple[CompositionRecord, ...]:
        if not 1 <= limit <= 1000:
            raise CompositionStateError("limit must be between 1 and 1000.")
        records = [
            CompositionRecord.from_json(raw)
            for raw in self._load().values()
            if isinstance(raw, dict) and (site_key is None or raw.get("site_key") == site_key)
        ]
        return tuple(sorted(records, key=lambda item: item.updated_at, reverse=True)[:limit])

    def _load(self) -> dict[str, dict[str, object]]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CompositionStateError(
                "Composition state file could not be read.",
                safe_context={"file_name": self.path.name, "error_type": type(exc).__name__},
            ) from exc
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise CompositionStateError("Unsupported composition state schema.")
        records = payload.get("records", {})
        if not isinstance(records, dict):
            raise CompositionStateError("Composition state records are invalid.")
        return records

    def _write(self, records: dict[str, dict[str, object]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": 1, "records": records}
        try:
            with NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.path.parent, prefix=self.path.name + ".", suffix=".tmp", delete=False
            ) as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
                temporary = Path(handle.name)
            os.replace(temporary, self.path)
        except OSError as exc:
            raise CompositionStateError(
                "Composition state file could not be written.",
                safe_context={"file_name": self.path.name, "error_type": type(exc).__name__},
            ) from exc

    @staticmethod
    def _key(site_key: str, composition_key: str) -> str:
        return f"{site_key}::{composition_key}"
