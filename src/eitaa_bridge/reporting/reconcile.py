"""Reconciliation and audit tools for WordPress legacy archive and native store.

In accordance with Phase 6 of UNIFIED_REPORTING_FINAL_STRATEGY_2026-10-01.md:
- Reconciles historical WP post links against native reported events.
- Verifies integrity of media attachments and documents.
- Identifies orphaned events, broken post links, and unlinked sections.
- Strictly privacy-safe: never logs sensitive PII or tokens.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
from typing import Any, Mapping

from .store import ReportingStore


@dataclass(slots=True)
class WpReconciliationReport:
    """Structured audit report for WordPress historical archive reconciliation."""

    total_wp_links: int
    confirmed_matches: int
    candidate_matches: int
    unmatched_links: int
    broken_links: int
    total_events: int
    events_with_wp_link: int
    native_only_events: int
    media_documents_count: int
    valid_media_checksums: int
    broken_media_documents: int
    section_breakdown: dict[str, int] = field(default_factory=dict)
    exceptions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_wp_links": self.total_wp_links,
            "confirmed_matches": self.confirmed_matches,
            "candidate_matches": self.candidate_matches,
            "unmatched_links": self.unmatched_links,
            "broken_links": self.broken_links,
            "total_events": self.total_events,
            "events_with_wp_link": self.events_with_wp_link,
            "native_only_events": self.native_only_events,
            "media_documents_count": self.media_documents_count,
            "valid_media_checksums": self.valid_media_checksums,
            "broken_media_documents": self.broken_media_documents,
            "section_breakdown": self.section_breakdown,
            "exceptions_count": len(self.exceptions),
            "exceptions": self.exceptions[:50],  # cap details to 50 for clean reporting
        }


def reconcile_wp_archive(store: ReportingStore) -> WpReconciliationReport:
    """Perform a comprehensive reconciliation audit between wp_post_links and native events."""
    with store._connect() as conn:
        # 1. Inspect WP post links
        wp_rows = conn.execute(
            "SELECT link_id, post_slug, section, event_id, match_status "
            "FROM wp_post_links"
        ).fetchall()

        # 2. Inspect reported events
        event_rows = conn.execute("SELECT event_id, review_status FROM reported_events").fetchall()
        event_ids = {r["event_id"] for r in event_rows}

        # 3. Inspect event documents
        doc_rows = conn.execute(
            "SELECT document_id, event_id, media_id, sha256, size_bytes FROM event_documents"
        ).fetchall()

    total_wp = len(wp_rows)
    confirmed = 0
    candidate = 0
    unmatched = 0
    broken = 0
    section_counts: dict[str, int] = {}
    exceptions: list[dict[str, Any]] = []
    linked_event_ids: set[str] = set()

    for r in wp_rows:
        status = r["match_status"] or "unmatched"
        sec = r["section"] or "unspecified"
        section_counts[sec] = section_counts.get(sec, 0) + 1
        ev_id = str(r["event_id"] or "").strip()

        if status == "confirmed":
            if ev_id and ev_id in event_ids:
                confirmed += 1
                linked_event_ids.add(ev_id)
            else:
                broken += 1
                exceptions.append({
                    "kind": "broken_link",
                    "link_id": r["link_id"],
                    "post_slug": r["post_slug"],
                    "referenced_event_id": ev_id,
                    "reason": "Referenced event does not exist in reported_events",
                })
        elif status == "candidate":
            candidate += 1
        else:
            unmatched += 1

    total_events = len(event_ids)
    events_with_wp = len(linked_event_ids)
    native_only = total_events - events_with_wp

    # Media document verification — metadata-level audit. The media binaries
    # live in the messenger session store, not under this module's reach, so
    # this checks checksum/size metadata consistency and flags anything
    # incomplete or malformed as an exception for human adjudication.
    total_docs = len(doc_rows)
    valid_checksums = 0
    broken_docs = 0

    for d in doc_rows:
        sha = str(d["sha256"] or "")
        size = d["size_bytes"]
        sha_ok = len(sha) == 64 and all(c in "0123456789abcdefABCDEF" for c in sha)
        if not sha_ok:
            broken_docs += 1
            exceptions.append({
                "kind": "invalid_document_sha256",
                "document_id": d["document_id"],
                "event_id": d["event_id"],
                "media_id": d["media_id"],
                "reason": "Document missing or malformed SHA-256 checksum",
            })
            continue
        if size is not None and (not isinstance(size, int) or size <= 0):
            broken_docs += 1
            exceptions.append({
                "kind": "invalid_document_size",
                "document_id": d["document_id"],
                "event_id": d["event_id"],
                "media_id": d["media_id"],
                "reason": "Document size_bytes is non-positive or malformed",
            })
            continue
        valid_checksums += 1

    return WpReconciliationReport(
        total_wp_links=total_wp,
        confirmed_matches=confirmed,
        candidate_matches=candidate,
        unmatched_links=unmatched,
        broken_links=broken,
        total_events=total_events,
        events_with_wp_link=events_with_wp,
        native_only_events=native_only,
        media_documents_count=total_docs,
        valid_media_checksums=valid_checksums,
        broken_media_documents=broken_docs,
        section_breakdown=section_counts,
        exceptions=exceptions,
    )
