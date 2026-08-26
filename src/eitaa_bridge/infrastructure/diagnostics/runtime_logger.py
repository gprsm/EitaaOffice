from __future__ import annotations

import json
import logging
import sys
import threading
import uuid
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Iterator, Mapping

from .event_catalog import (
    EVENT_SCHEMA_VERSION,
    event_definition,
    normalize_correlation_id,
    normalize_level,
    normalize_reason_code,
    normalize_result,
    validate_event_name,
    validate_source,
)
from .redaction import redact

_CORRELATION_ID: ContextVar[str | None] = ContextVar(
    "eitaa_bridge_runtime_correlation_id",
    default=None,
)


class _HealthAwareRotatingFileHandler(RotatingFileHandler):
    """Capture stream/rollover failures without printing the private record."""

    def __init__(self, *args: Any, on_failure: Any, **kwargs: Any) -> None:
        self._on_failure = on_failure
        super().__init__(*args, **kwargs)

    def handleError(self, record: logging.LogRecord) -> None:  # noqa: N802
        error = sys.exc_info()[1]
        self._on_failure(error if isinstance(error, BaseException) else RuntimeError())


class RuntimeLogger:
    """Compact rotating runtime log for desktop/API performance and failures.

    Unlike component diagnostics, this file is intended for ordinary support and
    contains no request bodies, credentials, message text, or media bytes.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        max_bytes: int = 5 * 1024 * 1024,
        backup_count: int = 5,
        context_fields: Mapping[str, Any] | None = None,
        source: str = "application",
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._health_lock = threading.Lock()
        self._write_failures = 0
        self._last_failure_type: str | None = None
        self._logger = logging.getLogger(f"eitaa_bridge.runtime.{id(self)}")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        handler = _HealthAwareRotatingFileHandler(
            self.path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
            on_failure=self._record_write_failure,
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        self._logger.handlers.clear()
        self._logger.addHandler(handler)
        self._closed = False
        self._context_fields = dict(context_fields or {})
        self._source = validate_source(source)

    @staticmethod
    def request_id() -> str:
        return uuid.uuid4().hex[:12]

    @staticmethod
    def correlation_id(value: object = None) -> str:
        return normalize_correlation_id(value) or RuntimeLogger.request_id()

    @staticmethod
    def current_correlation_id() -> str | None:
        return _CORRELATION_ID.get()

    @staticmethod
    def bind_correlation_id(value: str | None) -> Token[str | None]:
        return _CORRELATION_ID.set(value)

    @staticmethod
    def reset_correlation_id(token: Token[str | None]) -> None:
        _CORRELATION_ID.reset(token)

    def emit(
        self,
        event: str,
        *,
        level: str = "info",
        fields: dict[str, Any] | None = None,
        result: str | None = None,
        reason_code: str | None = None,
        correlation_id: str | None = None,
        operation: str | None = None,
    ) -> None:
        selected_event = validate_event_name(event)
        selected_level = normalize_level(level)
        definition = event_definition(selected_event)
        selected_fields = dict(fields or {})
        selected_correlation = (
            normalize_correlation_id(correlation_id)
            or normalize_correlation_id(_CORRELATION_ID.get())
        )
        if selected_correlation:
            selected_fields.setdefault("request_id", selected_correlation)
        selected_fields.update(self._context_fields)
        selected_reason = normalize_reason_code(
            reason_code
            or selected_fields.get("reason_code")
            or selected_fields.get("error_code"),
            event=selected_event,
            level=selected_level,
        )
        record = {
            "schema_version": EVENT_SCHEMA_VERSION,
            "at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "source": self._source,
            "event": selected_event,
            "category": definition.category if definition else "legacy",
            "cataloged": definition is not None,
            "level": selected_level,
            "result": normalize_result(result, level=selected_level, definition=definition),
            "reason_code": selected_reason,
            "correlation_id": selected_correlation,
            "operation": str(operation or "").strip().lower() or None,
            "thread": threading.current_thread().name,
            "fields": redact(selected_fields),
        }
        line = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        method = getattr(self._logger, selected_level, self._logger.info)
        with self._lock:
            if self._closed:
                return
            try:
                method(line)
            except Exception as exc:
                self._record_write_failure(exc)

    def _record_write_failure(self, error: BaseException) -> None:
        with self._health_lock:
            self._write_failures += 1
            self._last_failure_type = type(error).__name__

    def health_summary(self) -> dict[str, object]:
        """Return a path-free monotonic summary suitable for support surfaces."""

        with self._health_lock:
            return {
                "status": "degraded" if self._write_failures else "healthy",
                "write_failures": self._write_failures,
                "last_failure_type": self._last_failure_type,
            }

    @contextmanager
    def observed_operation(
        self,
        operation: str,
        *,
        fields: Mapping[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> Iterator[str]:
        """Emit a safe, balanced lifecycle for one background/external operation."""

        selected_correlation = self.correlation_id(correlation_id or _CORRELATION_ID.get())
        started = datetime.now(timezone.utc)
        self.emit(
            "operation_started",
            result="started",
            operation=operation,
            correlation_id=selected_correlation,
            fields=dict(fields or {}),
        )
        try:
            yield selected_correlation
        except Exception as exc:
            duration_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000
            self.emit(
                "operation_failed",
                level="error",
                result="failed",
                reason_code="operation_exception",
                operation=operation,
                correlation_id=selected_correlation,
                fields={**dict(fields or {}), "duration_ms": round(duration_ms, 2), "error_type": type(exc).__name__},
            )
            raise
        else:
            duration_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000
            self.emit(
                "operation_succeeded",
                result="succeeded",
                operation=operation,
                correlation_id=selected_correlation,
                fields={**dict(fields or {}), "duration_ms": round(duration_ms, 2)},
            )

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            for handler in list(self._logger.handlers):
                try:
                    try:
                        handler.flush()
                    except Exception as exc:
                        self._record_write_failure(exc)
                    try:
                        handler.close()
                    except Exception as exc:
                        self._record_write_failure(exc)
                finally:
                    self._logger.removeHandler(handler)
