"""Bale messaging integration for the reporting office (send/receive focus).

Wraps the existing research-grade ``bale_client`` (auth, session, WebSocket,
history and send) behind a small, testable facade used by the reporting
workflow. The quarantined ``BaleProviderApplicationAdapter`` (G-02) stays
untouched: this module is an application-level helper, not a Provider.

Typical reporting-office uses:
- push a generated report/announcement to the culture-affairs channel;
- pull recent channel/group messages as another ``scan_texts`` input for the
  intent indexer (same pipeline as Eitaa).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from .indexer import EitaaIntentIndexer, IndexDecision, MessageIntent
from .monitor import MonitorResult


class BaleMessagingError(Exception):
    code = "bale_messaging_error"

    def __init__(self, message: str, *, safe_context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.safe_context = safe_context or {}


class BaleSessionNotAvailableError(BaleMessagingError):
    code = "bale_session_not_available"


@dataclass(slots=True)
class BaleMessageRecord:
    """A received Bale message normalized for the indexing pipeline."""

    message_ref: str
    dialog_label: str
    text: str
    sent_at: str = ""
    sender_hint: str = ""

    def as_scan_tuple(self) -> tuple[str, str, str]:
        return (self.message_ref, self.dialog_label, self.text)


@dataclass(slots=True)
class BaleSendReport:
    peer_label: str
    text_preview: str
    sent: bool = False
    raw_length: int = 0
    error: str = ""

    def summary(self) -> dict[str, Any]:
        return {
            "peer": self.peer_label,
            "sent": self.sent,
            "preview": self.text_preview[:80],
            "error": self.error,
        }


def _peer_label(peer: Any) -> str:
    for attribute in ("title", "username", "first_name", "name"):
        value = getattr(peer, attribute, None)
        if value:
            return str(value)
    return f"peer:{getattr(peer, 'id', '?')}"


class BaleMessagingFacade:
    """Send/receive facade over a ``BaleClient``-shaped object."""

    def __init__(self, client: Any, *, indexer: EitaaIntentIndexer | None = None) -> None:
        self.client = client
        self.indexer = indexer or EitaaIntentIndexer()

    # -- sending -------------------------------------------------------------

    async def send_text(self, peer: Any, text: str) -> BaleSendReport:
        if not text.strip():
            raise BaleMessagingError("Message text cannot be empty.", safe_context={"peer": _peer_label(peer)})
        try:
            await self.client.send_text(peer, text)
        except BaleMessagingError:
            raise
        except Exception as error:  # noqa: BLE001 - boundary converts provider exceptions
            raise BaleMessagingError(
                "Failed to send Bale message.",
                safe_context={"peer": _peer_label(peer), "type": type(error).__name__},
            ) from error
        return BaleSendReport(
            peer_label=_peer_label(peer),
            text_preview=text.strip()[:80],
            sent=True,
            raw_length=len(text.encode("utf-8")),
        )

    # -- receiving ------------------------------------------------------------

    async def fetch_history_records(
        self,
        peer: Any,
        *,
        limit: int = 50,
        dialog_label: str = "",
    ) -> list[BaleMessageRecord]:
        """Fetch recent history as normalized records (no persistence)."""

        label = dialog_label or _peer_label(peer)
        try:
            payload = await self.client.load_history(peer, limit=limit)
        except BaleMessagingError:
            raise
        except Exception as error:  # noqa: BLE001
            raise BaleMessagingError(
                "Failed to load Bale history.",
                safe_context={"peer": label, "type": type(error).__name__},
            ) from error

        records: list[BaleMessageRecord] = []
        messages = self._extract_messages(payload)
        peer_id = getattr(peer, "id", 0)
        for message in messages:
            text = getattr(message, "text", None)
            message_id = getattr(message, "id", None)
            sent_at = getattr(message, "date", None)
            sender_hint = str(getattr(message, "from_peer", None) or "")
            if message_id is None:
                continue
            if isinstance(text, str) and text.strip():
                records.append(
                    BaleMessageRecord(
                        message_ref=f"bale:{peer_id}:{message_id}",
                        dialog_label=label,
                        text=text,
                        sent_at=str(sent_at or ""),
                        sender_hint=sender_hint,
                    )
                )
        return records

    @staticmethod
    def _extract_messages(payload: Any) -> list[Any]:
        if isinstance(payload, list):
            return payload
        for attribute in ("messages", "items", "entries"):
            candidate = getattr(payload, attribute, None)
            if isinstance(candidate, list):
                return candidate
            if isinstance(candidate, dict):
                return list(candidate.values())
        if isinstance(payload, dict):
            for value in payload.values():
                if isinstance(value, list):
                    return value
        return []

    def index_records(self, records: Sequence[BaleMessageRecord]) -> MonitorResult:
        """Run the shared intent pipeline over Bale messages."""

        from .monitor import EitaaReportMonitor

        monitor = EitaaReportMonitor(self.indexer)
        return monitor.scan_texts([record.as_scan_tuple() for record in records])

    async def scan_peer(
        self,
        peer: Any,
        *,
        limit: int = 50,
        dialog_label: str = "",
    ) -> MonitorResult:
        records = await self.fetch_history_records(peer, limit=limit, dialog_label=dialog_label)
        return self.index_records(records)
