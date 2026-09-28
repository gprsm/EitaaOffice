"""Monitors configured Eitaa dialogs and feeds the reporting pipeline.

The monitor pulls messages via ``eitaa_core`` for the two mandated targets
(«مدیریت امور فرهنگی دادگستری» channel and «رابطان فرهنگی دادگستری»
group), indexes every message with the intent indexer, and turns event-report
messages into ``EventCandidate``s for the central-staff review queue.

No message text is persisted by this module: only scores, matched evidence
and message references flow onward (privacy per ADR-47/governance).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import time
from typing import Any, Callable, Iterable, Mapping, Sequence

from .eitaa_extraction import EventCandidate
from .indexer import (
    DEFAULT_MONITOR_TARGETS,
    EitaaIntentIndexer,
    IndexDecision,
    MessageIntent,
)
from .model import ProgramKind

MONITOR_VERSION = "eitaa-report-monitor-v1"


class MonitorConfigurationError(Exception):
    code = "monitor_configuration_error"


@dataclass(slots=True)
class DialogWatchConfig:
    label: str
    match_keywords: tuple[str, ...] = ()
    enabled: bool = True


@dataclass(slots=True)
class MonitorResult:
    scanned: int = 0
    event_reports: int = 0
    informational: int = 0
    promotional: int = 0
    candidates: list[EventCandidate] = field(default_factory=list)
    decisions: list[IndexDecision] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "scanned": self.scanned,
            "event_reports": self.event_reports,
            "informational": self.informational,
            "promotional": self.promotional,
            "candidates": [candidate.event_key for candidate in self.candidates],
        }


def default_watch_configs(extra: Iterable[DialogWatchConfig] = ()) -> tuple[DialogWatchConfig, ...]:
    return (
        DialogWatchConfig(label=DEFAULT_MONITOR_TARGETS[0], match_keywords=("امور فرهنگی", "فرهنگی")),
        DialogWatchConfig(label=DEFAULT_MONITOR_TARGETS[1], match_keywords=("رابطان فرهنگی", "رابطان")),
        *extra,
    )


class EitaaReportMonitor:
    """Pull-and-index loop over Eitaa dialogs; safe to run on demand."""

    version = MONITOR_VERSION

    def __init__(
        self,
        indexer: EitaaIntentIndexer | None = None,
        *,
        watch_configs: Iterable[DialogWatchConfig] | None = None,
    ) -> None:
        self.indexer = indexer or EitaaIntentIndexer()
        self.watch_configs = tuple(watch_configs) if watch_configs is not None else default_watch_configs()

    def matches_dialog(self, dialog_title: str) -> DialogWatchConfig | None:
        for config in self.watch_configs:
            if not config.enabled:
                continue
            if config.label == dialog_title:
                return config
            if config.match_keywords and any(keyword in dialog_title for keyword in config.match_keywords):
                return config
        return None

    def _iter_messages(self, core: Any, config: DialogWatchConfig, limit: int) -> list[tuple[str, str, str]]:
        """Fetch recent messages for one dialog via eitaa_core services.

        ``core`` must expose ``search_messages(MessageSearchQuery)`` or a
        ``list_dialogs()``-style API; the monitor never mutates anything.
        """

        from eitaa_core import MessageSearchQuery  # local import: optional provider

        collected: list[tuple[str, str, str]] = []
        query = MessageSearchQuery(text=None, limit=limit)
        page = core.search_messages(query)
        messages = getattr(page, "messages", None) or []
        for message in messages:
            text = getattr(message, "text", "") or ""
            peer = getattr(message, "peer", None)
            peer_id = getattr(peer, "id", 0) if peer is not None else 0
            dialog_hint = config.label
            ref = f"eitaa:{peer_id}:{getattr(message, 'id', 0)}"
            if not text.strip():
                continue
            collected.append((ref, dialog_hint, text))
        return collected

    def scan_once(self, core: Any, *, limit_per_dialog: int = 50, timeout_seconds: float = 30.0) -> MonitorResult:
        result = MonitorResult()
        seen_refs: set[str] = set()
        start_time = time.monotonic()
        for config in self.watch_configs:
            if not config.enabled:
                continue
            if time.monotonic() - start_time >= timeout_seconds:
                break
            try:
                batch = self._iter_messages(core, config, limit_per_dialog)
            except AttributeError:
                # Provider runtime not available (clean install, offline
                # bootstrap): monitoring abstains instead of guessing.
                continue
            for ref, dialog, text in batch:
                if time.monotonic() - start_time >= timeout_seconds:
                    break
                if ref in seen_refs:
                    continue  # same message matched by two watch configs
                seen_refs.add(ref)
                decision = self.indexer.classify(text, message_ref=ref, dialog_label=dialog)
                result.decisions.append(decision)
                result.scanned += 1
                if decision.intent == MessageIntent.EVENT_REPORT:
                    result.event_reports += 1
                    candidate = self.indexer.candidate_from_decision(decision)
                    if candidate is not None:
                        result.candidates.append(candidate)
                elif decision.intent == MessageIntent.PROMOTIONAL:
                    result.promotional += 1
                else:
                    result.informational += 1
        return result

    def scan_texts(self, messages: Sequence[tuple[str, str, str]], *, timeout_seconds: float = 30.0) -> MonitorResult:
        """Classify an explicit batch of ``(ref, dialog_label, text)`` tuples."""

        result = MonitorResult()
        start_time = time.monotonic()
        for ref, dialog, text in messages:
            if time.monotonic() - start_time >= timeout_seconds:
                break
            decision = self.indexer.classify(text, message_ref=ref, dialog_label=dialog)
            result.decisions.append(decision)
            result.scanned += 1
            if decision.is_event_report:
                result.event_reports += 1
                candidate = self.indexer.candidate_from_decision(decision)
                if candidate is not None:
                    result.candidates.append(candidate)
            elif decision.intent == MessageIntent.PROMOTIONAL:
                result.promotional += 1
            else:
                result.informational += 1
        return result
