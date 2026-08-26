from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eitaa_core import Peer, PublicationRecord

from .wordpress import WordPressMedia, WordPressPost


@dataclass(slots=True, frozen=True)
class CompositionSource:
    """One ordered Eitaa message selected for a WordPress composition."""

    peer: Peer
    message_id: int
    peer_file: Path | None = None

    @property
    def source_key(self) -> str:
        return f"{self.peer.type.value}:{self.peer.id}:{self.message_id}"

    def safe_summary(self) -> dict[str, object]:
        return {
            "source_key": self.source_key,
            "peer": self.peer.safe_summary(),
            "message_id": self.message_id,
            "peer_file_present": self.peer_file is not None,
        }


@dataclass(slots=True, frozen=True)
class WordPressCompositionRequest:
    """UI-neutral request describing one multi-message WordPress Draft."""

    composition_key: str
    site_key: str
    title: str
    excerpt: str
    sources: tuple[CompositionSource, ...]
    category_ids: tuple[int, ...] = ()
    tag_ids: tuple[int, ...] = ()
    featured_source_index: int | None = None
    include_featured_in_body: bool = True
    post_status: str = "draft"
    confirm_publish: bool = False

    def validate(self) -> None:
        if not self.composition_key.strip() or len(self.composition_key) > 128:
            raise ValueError("composition_key must contain 1 to 128 characters.")
        if not self.site_key.strip() or len(self.site_key) > 64:
            raise ValueError("site_key must contain 1 to 64 characters.")
        if not self.title.strip() or len(self.title) > 500:
            raise ValueError("title must contain 1 to 500 characters.")
        if len(self.excerpt) > 5000:
            raise ValueError("excerpt cannot exceed 5000 characters.")
        if not self.sources:
            raise ValueError("At least one source message is required.")
        if len(self.sources) > 100:
            raise ValueError("A composition cannot contain more than 100 messages.")
        keys: set[str] = set()
        for source in self.sources:
            source.peer.validate()
            if source.message_id <= 0:
                raise ValueError("message_id must be positive.")
            if source.source_key in keys:
                raise ValueError("Duplicate source message in one composition.")
            keys.add(source.source_key)
        for term_id in (*self.category_ids, *self.tag_ids):
            if term_id <= 0:
                raise ValueError("WordPress taxonomy ids must be positive.")
        if len(set(self.category_ids)) != len(self.category_ids):
            raise ValueError("category_ids cannot contain duplicates.")
        if len(set(self.tag_ids)) != len(self.tag_ids):
            raise ValueError("tag_ids cannot contain duplicates.")
        if self.featured_source_index is not None and not 0 <= self.featured_source_index < len(self.sources):
            raise ValueError("featured_source_index is outside the source list.")
        if self.post_status not in {"draft", "publish"}:
            raise ValueError("post_status must be draft or publish.")
        if self.post_status == "publish" and not self.confirm_publish:
            raise ValueError("confirm_publish must be true when post_status is publish.")

    def safe_summary(self) -> dict[str, object]:
        return {
            "composition_key": self.composition_key,
            "site_key": self.site_key,
            "title_length": len(self.title),
            "excerpt_length": len(self.excerpt),
            "source_count": len(self.sources),
            "source_keys": [item.source_key for item in self.sources],
            "category_ids": list(self.category_ids),
            "tag_ids": list(self.tag_ids),
            "featured_source_index": self.featured_source_index,
            "include_featured_in_body": self.include_featured_in_body,
            "post_status": self.post_status,
            "confirm_publish": self.confirm_publish,
        }


@dataclass(slots=True, frozen=True)
class CompositionSourcePlan:
    source: CompositionSource
    content_hash: str
    text_length: int
    media_present: bool
    media_type: str | None
    media_slug: str | None
    already_used: bool
    existing_post_id: str | None
    stale: bool

    def safe_summary(self) -> dict[str, object]:
        return {
            **self.source.safe_summary(),
            "content_hash_prefix": self.content_hash[:12],
            "text_length": self.text_length,
            "media_present": self.media_present,
            "media_type": self.media_type,
            "media_slug": self.media_slug,
            "already_used": self.already_used,
            "existing_post_id_present": self.existing_post_id is not None,
            "stale": self.stale,
        }


@dataclass(slots=True, frozen=True)
class WordPressCompositionPlan:
    request: WordPressCompositionRequest
    post_slug: str
    composition_hash: str
    sources: tuple[CompositionSourcePlan, ...]
    body_length_estimate: int

    @property
    def blocked_source_count(self) -> int:
        return sum(1 for item in self.sources if item.already_used)

    def safe_summary(self) -> dict[str, object]:
        return {
            "request": self.request.safe_summary(),
            "post_slug": self.post_slug,
            "composition_hash_prefix": self.composition_hash[:12],
            "sources": [item.safe_summary() for item in self.sources],
            "blocked_source_count": self.blocked_source_count,
            "body_length_estimate": self.body_length_estimate,
        }


@dataclass(slots=True, frozen=True)
class CompositionRecord:
    composition_key: str
    site_key: str
    post_id: int
    post_url: str | None
    post_slug: str
    status: str
    title: str
    excerpt: str
    category_ids: tuple[int, ...]
    tag_ids: tuple[int, ...]
    source_keys: tuple[str, ...]
    source_hashes: tuple[str, ...]
    featured_source_key: str | None
    featured_media_id: int | None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def safe_summary(self) -> dict[str, object]:
        return {
            "composition_key": self.composition_key,
            "site_key": self.site_key,
            "post_id": self.post_id,
            "post_url_present": self.post_url is not None,
            "post_slug": self.post_slug,
            "status": self.status,
            "title_length": len(self.title),
            "excerpt_length": len(self.excerpt),
            "category_ids": list(self.category_ids),
            "tag_ids": list(self.tag_ids),
            "source_count": len(self.source_keys),
            "source_keys": list(self.source_keys),
            "featured_source_key": self.featured_source_key,
            "featured_media_id": self.featured_media_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def to_json(self) -> dict[str, Any]:
        return {
            "composition_key": self.composition_key,
            "site_key": self.site_key,
            "post_id": self.post_id,
            "post_url": self.post_url,
            "post_slug": self.post_slug,
            "status": self.status,
            "title": self.title,
            "excerpt": self.excerpt,
            "category_ids": list(self.category_ids),
            "tag_ids": list(self.tag_ids),
            "source_keys": list(self.source_keys),
            "source_hashes": list(self.source_hashes),
            "featured_source_key": self.featured_source_key,
            "featured_media_id": self.featured_media_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "CompositionRecord":
        return cls(
            composition_key=str(data["composition_key"]),
            site_key=str(data["site_key"]),
            post_id=int(data["post_id"]),
            post_url=str(data["post_url"]) if data.get("post_url") else None,
            post_slug=str(data["post_slug"]),
            status=str(data["status"]),
            title=str(data.get("title") or ""),
            excerpt=str(data.get("excerpt") or ""),
            category_ids=tuple(int(value) for value in data.get("category_ids", [])),
            tag_ids=tuple(int(value) for value in data.get("tag_ids", [])),
            source_keys=tuple(str(value) for value in data.get("source_keys", [])),
            source_hashes=tuple(str(value) for value in data.get("source_hashes", [])),
            featured_source_key=(str(data["featured_source_key"]) if data.get("featured_source_key") else None),
            featured_media_id=(int(data["featured_media_id"]) if data.get("featured_media_id") else None),
            created_at=datetime.fromisoformat(str(data["created_at"])),
            updated_at=datetime.fromisoformat(str(data["updated_at"])),
        )


@dataclass(slots=True, frozen=True)
class WordPressCompositionResult:
    outcome: str
    plan: WordPressCompositionPlan
    record: CompositionRecord | None = None
    post: WordPressPost | None = None
    media: tuple[WordPressMedia, ...] = ()
    publications: tuple[PublicationRecord, ...] = ()
    recovered: bool = False

    def safe_summary(self) -> dict[str, object]:
        return {
            "outcome": self.outcome,
            "plan": self.plan.safe_summary(),
            "record": self.record.safe_summary() if self.record else None,
            "post": self.post.safe_summary() if self.post else None,
            "media": [item.safe_summary() for item in self.media],
            "publication_count": len(self.publications),
            "publications": [item.safe_summary() for item in self.publications],
            "confirmed_source_keys": list(self.record.source_keys) if self.record else [],
            "recovered": self.recovered,
        }
