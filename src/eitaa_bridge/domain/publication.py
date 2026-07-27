from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from eitaa_core import PublicationRecord

from .wordpress import WordPressMedia, WordPressPost


@dataclass(slots=True, frozen=True)
class WordPressPublicationPlan:
    """Deterministic plan for publishing one locally stored Eitaa message."""

    site_key: str
    peer_type: str
    peer_id: int
    message_id: int
    content_hash: str
    title: str
    content: str
    post_slug: str
    media_slug: str | None
    media_fingerprint: str | None
    media_present: bool
    media_type: str | None
    category_id: int | None

    def safe_summary(self) -> dict[str, object]:
        return {
            "site_key": self.site_key,
            "peer_type": self.peer_type,
            "peer_id": self.peer_id,
            "message_id": self.message_id,
            "content_hash_prefix": self.content_hash[:12],
            "title_length": len(self.title),
            "content_length": len(self.content),
            "post_slug": self.post_slug,
            "media_slug": self.media_slug,
            "media_fingerprint_prefix": self.media_fingerprint[:12] if self.media_fingerprint else None,
            "media_present": self.media_present,
            "media_type": self.media_type,
            "category_id": self.category_id,
        }


@dataclass(slots=True, frozen=True)
class WordPressPublicationResult:
    """Safe outcome of one controlled publication attempt."""

    outcome: str
    plan: WordPressPublicationPlan
    publication: PublicationRecord | None = None
    post: WordPressPost | None = None
    media: WordPressMedia | None = None
    downloaded_path: Path | None = None
    recovered: bool = False
    action: str | None = None
    remote_matches_plan: bool | None = None
    live_update: bool = False

    def safe_summary(self) -> dict[str, object]:
        return {
            "outcome": self.outcome,
            "plan": self.plan.safe_summary(),
            "publication": self.publication.safe_summary() if self.publication else None,
            "post": self.post.safe_summary() if self.post else None,
            "media": self.media.safe_summary() if self.media else None,
            "downloaded_media_present": self.downloaded_path is not None,
            "downloaded_media_suffix": self.downloaded_path.suffix.lower() if self.downloaded_path else None,
            "recovered": self.recovered,
            "action": self.action,
            "remote_matches_plan": self.remote_matches_plan,
            "live_update": self.live_update,
        }
