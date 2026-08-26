from __future__ import annotations

import json
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .redaction import redact

_COMPONENT = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def prune_old_diagnostic_runs(
    root: str | Path,
    *,
    protected_run_ids: set[str] | None = None,
    keep_newest: int = 50,
    max_age_days: int = 30,
) -> dict[str, int]:
    """Remove only old top-level diagnostic run directories.

    Package directories named ``diagnostics`` are never traversed. Failures are
    ignored because cleanup must not delay or prevent application startup.
    """
    import shutil
    import time

    selected_root = Path(root)
    protected = protected_run_ids or set()
    if not selected_root.exists() or not selected_root.is_dir():
        return {"scanned": 0, "removed": 0, "failed": 0}

    entries: list[tuple[float, Path]] = []
    try:
        for child in selected_root.iterdir():
            if not child.is_dir() or child.name in protected:
                continue
            if not ((child / "manifest.json").is_file() or re.fullmatch(r"[0-9a-f]{12}", child.name)):
                continue
            try:
                entries.append((child.stat().st_mtime, child))
            except OSError:
                continue
    except OSError:
        return {"scanned": 0, "removed": 0, "failed": 1}

    entries.sort(key=lambda item: item[0], reverse=True)
    cutoff = time.time() - max(1, max_age_days) * 86400
    removed = failed = 0
    for index, (modified, child) in enumerate(entries):
        if index < max(1, keep_newest) and modified >= cutoff:
            continue
        try:
            shutil.rmtree(child)
            removed += 1
        except OSError:
            failed += 1
    return {"scanned": len(entries), "removed": removed, "failed": failed}


def _runtime_log_sets(root: Path) -> list[tuple[Path, list[Path]]]:
    runtime = root / "runtime"
    currents = [runtime / "logs" / "application.jsonl"]
    accounts_root = runtime / "accounts"
    if accounts_root.is_dir() and not accounts_root.is_symlink():
        try:
            accounts = sorted(
                (
                    child
                    for child in accounts_root.iterdir()
                    if child.is_dir() and not child.is_symlink()
                ),
                key=lambda item: item.name.casefold(),
            )
        except OSError:
            accounts = []
        currents.extend(account / "logs" / "worker.jsonl" for account in accounts)

    selected: list[tuple[Path, list[Path]]] = []
    for current in currents:
        rotations: list[tuple[int, Path]] = []
        if current.parent.is_dir() and not current.parent.is_symlink():
            try:
                for candidate in current.parent.glob(current.name + ".*"):
                    suffix = candidate.name.removeprefix(current.name + ".")
                    if (
                        suffix.isdecimal()
                        and candidate.is_file()
                        and not candidate.is_symlink()
                    ):
                        rotations.append((int(suffix), candidate))
            except OSError:
                pass
        selected.append((current, [path for _, path in sorted(rotations)]))
    return selected


def enforce_runtime_log_retention(
    root: str | Path,
    *,
    keep_newest_rotations: int = 5,
    max_age_days: int = 30,
    max_total_bytes: int = 100 * 1024 * 1024,
) -> dict[str, int]:
    """Bound only numeric Application/Worker rotations; never remove current logs."""

    import time

    selected_root = Path(root).expanduser().resolve()
    keep_newest = max(0, int(keep_newest_rotations))
    cutoff = time.time() - max(1, int(max_age_days)) * 86400
    budget = max(1, int(max_total_bytes))
    log_sets = _runtime_log_sets(selected_root)
    scanned = sum(len(rotations) for _, rotations in log_sets)
    removed = failed = 0
    retained_rotations: list[tuple[float, Path]] = []

    for _current, rotations in log_sets:
        dated: list[tuple[float, Path]] = []
        for path in rotations:
            try:
                dated.append((path.stat().st_mtime, path))
            except OSError:
                failed += 1
        dated.sort(key=lambda item: item[0], reverse=True)
        for index, (modified, path) in enumerate(dated):
            if index < keep_newest and modified >= cutoff:
                retained_rotations.append((modified, path))
                continue
            try:
                path.unlink()
                removed += 1
            except OSError:
                failed += 1
                retained_rotations.append((modified, path))

    def file_size(path: Path) -> int:
        nonlocal failed
        if not path.is_file() or path.is_symlink():
            return 0
        try:
            return int(path.stat().st_size)
        except OSError:
            failed += 1
            return 0

    current_files = [current for current, _ in log_sets]
    remaining_bytes = sum(file_size(path) for path in current_files)
    retained_sizes: list[tuple[float, Path, int]] = []
    for modified, path in retained_rotations:
        size = file_size(path)
        if path.is_file() and not path.is_symlink():
            retained_sizes.append((modified, path, size))
            remaining_bytes += size

    for _modified, path, size in sorted(retained_sizes, key=lambda item: item[0]):
        if remaining_bytes <= budget:
            break
        try:
            path.unlink()
            removed += 1
            remaining_bytes = max(0, remaining_bytes - size)
        except OSError:
            failed += 1

    return {
        "scanned": scanned,
        "removed": removed,
        "failed": failed,
        "remaining_bytes": remaining_bytes,
    }


def observability_disk_health(
    root: str | Path,
    *,
    minimum_free_bytes: int = 256 * 1024 * 1024,
) -> dict[str, object]:
    """Return only numeric disk health; never expose a filesystem path."""

    import shutil

    selected_root = Path(root).expanduser().resolve()
    minimum = max(1, int(minimum_free_bytes))
    try:
        available = int(shutil.disk_usage(selected_root).free)
    except OSError:
        return {
            "status": "unknown",
            "available_free_bytes": None,
            "minimum_free_bytes": minimum,
        }
    return {
        "status": "healthy" if available >= minimum else "degraded",
        "available_free_bytes": available,
        "minimum_free_bytes": minimum,
    }


@dataclass(slots=True)
class BridgeDiagnosticManager:
    root: Path
    enabled: bool = True
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _components: set[str] = field(default_factory=set, init=False, repr=False)

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        if self.enabled:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            self._write_manifest()

    @property
    def run_dir(self) -> Path:
        return self.root / self.run_id

    def file_for(self, component: str) -> Path:
        self._validate(component)
        return self.run_dir / f"{component}.jsonl"

    def emit(self, component: str, event: str, *, level: str = "info", fields: dict[str, Any] | None = None) -> str | None:
        if not self.enabled:
            return None
        self._validate(component)
        record = {
            "at": _utc_now(), "run_id": self.run_id, "component": component,
            "level": level, "event": event, "fields": redact(fields or {}),
        }
        path = self.file_for(component)
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            is_new_component = component not in self._components
            self._components.add(component)
            if is_new_component:
                self._write_manifest()
        return str(path)

    def share_hint(self, component: str) -> str:
        return f"Share only this safe file: {self.file_for(component)}"

    def _write_manifest(self) -> None:
        if not self.enabled:
            return
        manifest = {
            "schema_version": 1,
            "run_id": self.run_id,
            "security": {
                "raw_requests_written": False,
                "raw_responses_written": False,
                "authorization_headers_written": False,
                "wordpress_credentials_written": False,
                "eitaa_tokens_written": False,
                "eitaa_imeis_written": False,
                "access_hashes_written": False,
                "phone_numbers_written": False,
                "message_or_post_content_written": False,
                "sqlite_contents_written": False,
            },
            "component_files": {name: f"{name}.jsonl" for name in sorted(self._components)},
            "sharing_rule": "Share only the component file named by an error.",
        }
        (self.run_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )

    @staticmethod
    def _validate(component: str) -> None:
        if not _COMPONENT.fullmatch(component):
            raise ValueError(f"Invalid diagnostic component: {component!r}")
