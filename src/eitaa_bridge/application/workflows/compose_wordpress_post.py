from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eitaa_core import MediaDownloadOptions, MediaType, Message, PublicationStatus

from ...domain import (
    CompositionRecord,
    CompositionSourcePlan,
    WordPressCompositionPlan,
    WordPressCompositionRequest,
    WordPressCompositionResult,
    WordPressMedia,
    WordPressPost,
)
from ...errors import (
    CompositionBlockedError,
    CompositionCollisionError,
    CompositionValidationError,
    WordPressAmbiguousWriteError,
    WordPressError,
)
from ...infrastructure.composition_store import JsonCompositionStore
from ...infrastructure.diagnostics import BridgeDiagnosticManager
from ..services.wordpress_service import WordPressService

_TARGET_TYPE = "wordpress"
_SLUG_CHARS = re.compile(r"[^a-z0-9-]+")


@dataclass(slots=True)
class ComposeMessagesToWordPress:
    wordpress: WordPressService
    diagnostics: BridgeDiagnosticManager
    media_directory: Path
    store: JsonCompositionStore

    def preview(self, core: Any, request: WordPressCompositionRequest) -> WordPressCompositionResult:
        messages, plan = self._build_plan(core, request)
        del messages
        record = self.store.get(request.site_key, request.composition_key)
        return WordPressCompositionResult(outcome="composition_preview", plan=plan, record=record)

    def status(self, core: Any, request: WordPressCompositionRequest) -> WordPressCompositionResult:
        messages, plan = self._build_plan(core, request)
        del messages
        record = self.store.get(request.site_key, request.composition_key)
        post = None
        if record:
            try:
                post = self.wordpress.get_post(record.post_id)
            except WordPressError:
                post = None
        publications = tuple(
            item for source in request.sources
            if (item := core.publications.get(
                source.peer, source.message_id, target_type=_TARGET_TYPE, target_key=request.site_key
            )) is not None
        )
        return WordPressCompositionResult(
            outcome="composition_status", plan=plan, record=record, post=post, publications=publications
        )

    def message_usage(self, core: Any, *, site_key: str, peer: Any, message_id: int) -> dict[str, object]:
        publication = core.publications.get(
            peer, message_id, target_type=_TARGET_TYPE, target_key=site_key
        )
        source_key = f"{peer.type.value}:{peer.id}:{message_id}"
        records = self.store.find_by_source(site_key, source_key)
        composition_post_id = str(records[0].post_id) if records else None
        used = bool((publication and publication.external_post_id) or composition_post_id)
        return {
            "site_key": site_key,
            "source_key": source_key,
            "used": used,
            "publication": publication.safe_summary() if publication else None,
            "external_post_id": publication.external_post_id if publication and publication.external_post_id else composition_post_id,
            "composition_count": len(records),
            "compositions": [item.safe_summary() for item in records],
        }

    def execute(
        self,
        core: Any,
        request: WordPressCompositionRequest,
        *,
        max_media_bytes: int | None = 100 * 1024 * 1024,
    ) -> WordPressCompositionResult:
        messages, plan = self._build_plan(core, request)
        existing_record = self.store.get(request.site_key, request.composition_key)
        matching_post = self._unique_post(plan.post_slug)

        if existing_record:
            current_source_keys = tuple(item.source.source_key for item in plan.sources)
            if existing_record.source_keys != current_source_keys:
                raise CompositionCollisionError(
                    "The composition_key is already bound to a different ordered source list.",
                    safe_context={
                        "composition_key": request.composition_key,
                        "recorded_source_count": len(existing_record.source_keys),
                        "requested_source_count": len(current_source_keys),
                    },
                    code="composition_key_reused",
                )
            if matching_post and matching_post.id != existing_record.post_id:
                raise CompositionCollisionError(
                    "Composition state and deterministic slug resolve to different WordPress posts.",
                    safe_context={
                        "composition_key": request.composition_key,
                        "recorded_post_id": existing_record.post_id,
                        "slug_post_id": matching_post.id,
                    },
                    code="composition_post_identity_collision",
                )
            post = matching_post
            if post is None:
                try:
                    post = self.wordpress.get_post(existing_record.post_id)
                except WordPressError as exc:
                    raise CompositionBlockedError(
                        "The recorded composition post is missing; create mode will not make a replacement.",
                        safe_context={
                            "composition_key": request.composition_key,
                            "post_id": existing_record.post_id,
                        },
                        code="composition_remote_post_missing",
                    ) from exc
            if not post.contains_marker(self._identity_marker_prefix(plan)):
                raise CompositionCollisionError(
                    "The recorded WordPress post no longer contains the Bridge composition identity marker.",
                    safe_context={"composition_key": request.composition_key, "post_id": post.id},
                    code="composition_post_identity_mismatch",
                )
            if post.status == "trash":
                raise CompositionBlockedError(
                    "The recorded composition post is in Trash; create mode will not restore it automatically.",
                    safe_context={"composition_key": request.composition_key, "post_id": post.id},
                    code="composition_post_trashed",
                )
            publications = self._reconcile_publications(core, request, plan, post)
            self._verify_committed_sources(existing_record, publications)
            return WordPressCompositionResult(
                outcome="composition_already_created",
                plan=plan,
                record=existing_record,
                post=post,
                publications=publications,
                recovered=True,
            )

        if matching_post is not None:
            if not matching_post.contains_marker(self._identity_marker(plan)):
                raise CompositionCollisionError(
                    "The deterministic composition slug is already used by another WordPress post.",
                    safe_context={"post_id": matching_post.id, "post_slug": plan.post_slug},
                    code="composition_slug_collision",
                )
            record = self._save_record(request, plan, matching_post, (), None)
            publications = self._reconcile_publications(core, request, plan, matching_post)
            self._verify_committed_sources(record, publications)
            return WordPressCompositionResult(
                outcome="composition_recovered_post",
                plan=plan,
                record=record,
                post=matching_post,
                publications=publications,
                recovered=True,
            )

        blocked = [item for item in plan.sources if item.already_used]
        if blocked:
            raise CompositionBlockedError(
                "One or more selected Eitaa messages were already used in WordPress.",
                safe_context={
                    "site_key": request.site_key,
                    "blocked_source_count": len(blocked),
                    "blocked_sources": [item.source.source_key for item in blocked],
                },
                code="composition_source_already_used",
            )

        if request.post_status == "publish":
            connection = self.wordpress.test_connection()
            if not connection.can_publish_posts:
                raise CompositionBlockedError(
                    "The configured WordPress account cannot publish posts.",
                    safe_context={"site_key": request.site_key},
                    code="composition_publish_permission_missing",
                )

        media_items: list[WordPressMedia | None] = []
        for message, source_plan in zip(messages, plan.sources, strict=True):
            if not source_plan.media_present or source_plan.media_slug is None:
                media_items.append(None)
                continue
            existing_media = self._unique_media(source_plan.media_slug)
            if existing_media is None:
                path = self._download(core, message, source_plan.media_slug, max_media_bytes)
                try:
                    existing_media = self.wordpress.upload_media(
                        path,
                        mime_type=message.media.mime_type if message.media else None,
                        slug=source_plan.media_slug,
                        title=request.title,
                        alt_text=request.title if self._is_image_message(message) else None,
                    )
                except WordPressAmbiguousWriteError:
                    existing_media = self._unique_media(source_plan.media_slug)
                    if existing_media is None:
                        raise
            media_items.append(existing_media)

        featured_media_id = self._featured_media_id(request, messages, media_items)
        content = self._render_body(request, plan, messages, media_items)
        try:
            create_kwargs = {
                "title": request.title,
                "content": content,
                "excerpt": request.excerpt,
                "slug": plan.post_slug,
                "category_ids": request.category_ids,
                "tag_ids": request.tag_ids,
                "featured_media_id": featured_media_id,
            }
            if request.post_status == "draft":
                created = self.wordpress.create_text_draft(**create_kwargs)
            else:
                created = self.wordpress.create_post(status=request.post_status, **create_kwargs)
        except WordPressAmbiguousWriteError:
            created = self._unique_post(plan.post_slug)
            if created is None:
                raise

        # Verify by authenticated GET when the write response omits raw fields.
        try:
            post = self.wordpress.get_post(created.id)
        except WordPressError:
            post = created
        if post.id != created.id:
            raise CompositionCollisionError(
                "WordPress returned an unexpected post identity.",
                safe_context={"expected_post_id": created.id, "actual_post_id": post.id},
                code="composition_unverified_post",
            )
        if post.status != request.post_status:
            raise CompositionBlockedError(
                "WordPress did not apply the requested post status.",
                safe_context={
                    "post_id": post.id,
                    "requested_status": request.post_status,
                    "actual_status": post.status,
                },
                code="composition_post_status_mismatch",
            )

        publications = self._reconcile_publications(core, request, plan, post)
        record = self._save_record(
            request,
            plan,
            post,
            tuple(item for item in media_items if item is not None),
            featured_media_id,
        )
        self._verify_committed_sources(record, publications)
        self.diagnostics.emit(
            "composer", "composition_created",
            fields={"plan": plan.safe_summary(), "record": record.safe_summary(), "post": post.safe_summary()},
        )
        return WordPressCompositionResult(
            outcome="composition_created",
            plan=plan,
            record=record,
            post=post,
            media=tuple(item for item in media_items if item is not None),
            publications=publications,
        )

    def update(
        self,
        core: Any,
        request: WordPressCompositionRequest,
        *,
        max_media_bytes: int | None = 100 * 1024 * 1024,
    ) -> WordPressCompositionResult:
        """Update the same recorded multi-message WordPress post safely."""
        messages, plan = self._build_plan(core, request)
        existing_record = self.store.get(request.site_key, request.composition_key)
        if existing_record is None:
            raise CompositionBlockedError(
                "Composition state was not found; update cannot create a replacement.",
                safe_context={"composition_key": request.composition_key},
                code="composition_update_record_missing",
            )
        requested_keys = tuple(item.source.source_key for item in plan.sources)
        recorded_set = set(existing_record.source_keys)
        requested_set = set(requested_keys)
        if len(requested_set) != len(requested_keys):
            raise CompositionCollisionError(
                "Update source messages contain duplicate entries.",
                safe_context={
                    "composition_key": request.composition_key,
                    "requested_source_count": len(requested_keys),
                    "requested_unique_count": len(requested_set),
                },
                code="composition_update_duplicate_sources",
            )
        missing_recorded = tuple(key for key in existing_record.source_keys if key not in requested_set)
        if missing_recorded:
            raise CompositionCollisionError(
                "Update cannot remove or replace source messages already recorded for this composition.",
                safe_context={
                    "composition_key": request.composition_key,
                    "recorded_source_count": len(existing_record.source_keys),
                    "requested_source_count": len(requested_keys),
                    "missing_recorded_count": len(missing_recorded),
                },
                code="composition_update_source_removal_blocked",
            )
        added_source_count = len(requested_set - recorded_set)
        if added_source_count:
            self.diagnostics.emit(
                "composer",
                "composition_sources_appended",
                fields={
                    "composition_key": request.composition_key,
                    "post_id": existing_record.post_id,
                    "previous_source_count": len(existing_record.source_keys),
                    "requested_source_count": len(requested_keys),
                    "added_source_count": added_source_count,
                },
            )
        try:
            remote = self.wordpress.get_post(existing_record.post_id)
        except WordPressError as exc:
            raise CompositionBlockedError(
                "The recorded WordPress post is missing; update will not create a replacement.",
                safe_context={"composition_key": request.composition_key, "post_id": existing_record.post_id},
                code="composition_remote_post_missing",
            ) from exc
        if not remote.contains_marker(self._identity_marker_prefix(plan)):
            raise CompositionCollisionError(
                "The recorded WordPress post no longer contains the Bridge composition identity marker.",
                safe_context={"composition_key": request.composition_key, "post_id": remote.id},
                code="composition_post_identity_mismatch",
            )
        if remote.status == "trash":
            raise CompositionBlockedError(
                "The recorded composition post is in Trash and must be restored explicitly first.",
                safe_context={"composition_key": request.composition_key, "post_id": remote.id},
                code="composition_post_trashed",
            )
        for source_plan in plan.sources:
            if source_plan.existing_post_id and source_plan.existing_post_id != str(existing_record.post_id):
                raise CompositionCollisionError(
                    "A selected Eitaa message is linked to a different WordPress post.",
                    safe_context={
                        "source_key": source_plan.source.source_key,
                        "existing_post_id": source_plan.existing_post_id,
                        "composition_post_id": existing_record.post_id,
                    },
                    code="composition_source_post_collision",
                )
        if request.post_status == "publish":
            connection = self.wordpress.test_connection()
            if not connection.can_publish_posts:
                raise CompositionBlockedError(
                    "The configured WordPress account cannot publish posts.",
                    safe_context={"site_key": request.site_key},
                    code="composition_publish_permission_missing",
                )

        media_items: list[WordPressMedia | None] = []
        for message, source_plan in zip(messages, plan.sources, strict=True):
            if not source_plan.media_present or source_plan.media_slug is None:
                media_items.append(None)
                continue
            existing_media = self._unique_media(source_plan.media_slug)
            if existing_media is None:
                path = self._download(core, message, source_plan.media_slug, max_media_bytes)
                try:
                    existing_media = self.wordpress.upload_media(
                        path,
                        mime_type=message.media.mime_type if message.media else None,
                        slug=source_plan.media_slug,
                        title=request.title,
                        alt_text=request.title if self._is_image_message(message) else None,
                    )
                except WordPressAmbiguousWriteError:
                    existing_media = self._unique_media(source_plan.media_slug)
                    if existing_media is None:
                        raise
            media_items.append(existing_media)

        featured_media_id = self._featured_media_id(request, messages, media_items)
        content = self._render_body(request, plan, messages, media_items)
        try:
            updated = self.wordpress.update_post(
                existing_record.post_id,
                title=request.title,
                content=content,
                slug=existing_record.post_slug,
                category_ids=request.category_ids,
                tag_ids=request.tag_ids,
                excerpt=request.excerpt,
                featured_media_id=featured_media_id,
                status=request.post_status,
            )
        except WordPressAmbiguousWriteError:
            verified = self.wordpress.get_post(existing_record.post_id)
            if not verified.contains_marker(self._identity_marker(plan)):
                raise
            updated = verified
        post = self.wordpress.get_post(updated.id)
        if post.id != existing_record.post_id or not post.contains_marker(self._identity_marker(plan)):
            raise CompositionCollisionError(
                "Updated WordPress post could not be verified.",
                safe_context={"expected_post_id": existing_record.post_id, "actual_post_id": post.id},
                code="composition_unverified_post",
            )
        if post.status != request.post_status:
            raise CompositionBlockedError(
                "WordPress did not apply the requested post status.",
                safe_context={"post_id": post.id, "requested_status": request.post_status, "actual_status": post.status},
                code="composition_post_status_mismatch",
            )
        publications = self._reconcile_publications(core, request, plan, post)
        record = self._save_record(
            request,
            plan,
            post,
            tuple(item for item in media_items if item is not None),
            featured_media_id,
            existing=existing_record,
        )
        self._verify_committed_sources(record, publications)
        self.diagnostics.emit(
            "composer", "composition_updated",
            fields={"plan": plan.safe_summary(), "record": record.safe_summary(), "post": post.safe_summary()},
        )
        return WordPressCompositionResult(
            outcome="composition_updated",
            plan=plan,
            record=record,
            post=post,
            media=tuple(item for item in media_items if item is not None),
            publications=publications,
        )

    def _build_plan(
        self, core: Any, request: WordPressCompositionRequest
    ) -> tuple[tuple[Message, ...], WordPressCompositionPlan]:
        try:
            request.validate()
        except ValueError as exc:
            raise CompositionValidationError(str(exc)) from exc
        messages: list[Message] = []
        sources: list[CompositionSourcePlan] = []
        digest_payload: list[dict[str, object]] = []
        estimate = 0
        for source in request.sources:
            message = core.messages.get(source.peer, source.message_id)
            if message is None:
                raise CompositionValidationError(
                    "A selected Eitaa message is not stored in Core.",
                    safe_context={"source": source.safe_summary()},
                    code="composition_message_not_found",
                )
            content_hash = core.messages.content_hash(source.peer, source.message_id)
            if not content_hash:
                raise CompositionValidationError(
                    "Core did not return a content hash for a selected message.",
                    safe_context={"source": source.safe_summary()},
                    code="composition_content_hash_missing",
                )
            publication = core.publications.get(
                source.peer, source.message_id, target_type=_TARGET_TYPE, target_key=request.site_key
            )
            composition_records = self.store.find_by_source(request.site_key, source.source_key)
            composition_post_id = str(composition_records[0].post_id) if composition_records else None
            existing_post_id = (
                publication.external_post_id
                if publication and publication.external_post_id
                else composition_post_id
            )
            used = bool(existing_post_id)
            media_slug = self._media_slug(source, content_hash) if message.media else None
            sources.append(
                CompositionSourcePlan(
                    source=source,
                    content_hash=content_hash,
                    text_length=len(message.text),
                    media_present=message.media is not None,
                    media_type=message.media.type.value if message.media else None,
                    media_slug=media_slug,
                    already_used=used,
                    existing_post_id=existing_post_id,
                    stale=publication.stale if publication else False,
                )
            )
            messages.append(message)
            estimate += len(message.text) + (250 if message.media else 0)
            digest_payload.append({"source": source.source_key, "content_hash": content_hash})
        if request.featured_source_index is not None:
            featured_message = messages[request.featured_source_index]
            if not self._is_image_message(featured_message):
                raise CompositionValidationError(
                    "featured_source_index must refer to a selected image message.",
                    safe_context={"featured_source_index": request.featured_source_index},
                    code="composition_featured_source_not_image",
                )
        composition_hash = hashlib.sha256(
            json.dumps(
                {
                    "composition_key": request.composition_key,
                    "title": request.title,
                    "excerpt": request.excerpt,
                    "categories": request.category_ids,
                    "tags": request.tag_ids,
                    "sources": digest_payload,
                    "featured": request.featured_source_index,
                    "include_featured": request.include_featured_in_body,
                    "post_status": request.post_status,
                },
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        plan = WordPressCompositionPlan(
            request=request,
            post_slug=self._post_slug(request.composition_key),
            composition_hash=composition_hash,
            sources=tuple(sources),
            body_length_estimate=estimate,
        )
        return tuple(messages), plan

    def _reconcile_publications(
        self, core: Any, request: WordPressCompositionRequest, plan: WordPressCompositionPlan, post: WordPressPost
    ) -> tuple[Any, ...]:
        records = []
        for source_plan in plan.sources:
            existing = core.publications.get(
                source_plan.source.peer,
                source_plan.source.message_id,
                target_type=_TARGET_TYPE,
                target_key=request.site_key,
            )
            if existing and existing.external_post_id and existing.external_post_id != str(post.id):
                raise CompositionCollisionError(
                    "A selected Eitaa message is linked to a different WordPress post.",
                    safe_context={
                        "source_key": source_plan.source.source_key,
                        "existing_post_id": existing.external_post_id,
                        "composition_post_id": post.id,
                    },
                    code="composition_source_post_collision",
                )
            if existing is None:
                core.publications.mark_pending(
                    source_plan.source.peer,
                    source_plan.source.message_id,
                    target_type=_TARGET_TYPE,
                    target_key=request.site_key,
                )
                core.publications.mark_processing(
                    source_plan.source.peer,
                    source_plan.source.message_id,
                    target_type=_TARGET_TYPE,
                    target_key=request.site_key,
                )
            record = core.publications.mark_published(
                source_plan.source.peer,
                source_plan.source.message_id,
                external_post_id=str(post.id),
                external_url=post.link,
                target_type=_TARGET_TYPE,
                target_key=request.site_key,
            )
            records.append(record)
        return tuple(records)

    def _save_record(
        self,
        request: WordPressCompositionRequest,
        plan: WordPressCompositionPlan,
        post: WordPressPost,
        media: tuple[WordPressMedia, ...],
        featured_media_id: int | None,
        existing: CompositionRecord | None = None,
    ) -> CompositionRecord:
        del media
        featured_key = (
            request.sources[request.featured_source_index].source_key
            if request.featured_source_index is not None else None
        )
        return self.store.save(
            CompositionRecord(
                composition_key=request.composition_key,
                site_key=request.site_key,
                post_id=post.id,
                post_url=post.link,
                post_slug=plan.post_slug,
                status=post.status,
                title=request.title,
                excerpt=request.excerpt,
                category_ids=request.category_ids,
                tag_ids=request.tag_ids,
                source_keys=tuple(item.source.source_key for item in plan.sources),
                source_hashes=tuple(item.content_hash for item in plan.sources),
                featured_source_key=featured_key,
                featured_media_id=featured_media_id,
                created_at=existing.created_at if existing else datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )

    def _verify_committed_sources(
        self, record: CompositionRecord, publications: tuple[Any, ...]
    ) -> tuple[str, ...]:
        persisted = self.store.get(record.site_key, record.composition_key)
        expected = tuple(record.source_keys)
        if persisted is None or persisted.post_id != record.post_id or tuple(persisted.source_keys) != expected:
            raise CompositionBlockedError(
                "WordPress post was written, but the local composition source state could not be verified.",
                safe_context={
                    "composition_key": record.composition_key,
                    "post_id": record.post_id,
                    "expected_source_count": len(expected),
                },
                code="composition_usage_commit_unverified",
            )
        if len(publications) != len(expected) or any(
            str(getattr(item, "external_post_id", "") or "") != str(record.post_id)
            for item in publications
        ):
            raise CompositionBlockedError(
                "WordPress post was written, but one or more message usage rows were not committed to the same post.",
                safe_context={
                    "composition_key": record.composition_key,
                    "post_id": record.post_id,
                    "expected_source_count": len(expected),
                    "publication_count": len(publications),
                },
                code="composition_publication_commit_unverified",
            )
        for source_key in expected:
            matches = self.store.find_by_source(record.site_key, source_key)
            if not any(item.composition_key == record.composition_key and item.post_id == record.post_id for item in matches):
                raise CompositionBlockedError(
                    "WordPress post was written, but a source message could not be read back from the composition index.",
                    safe_context={
                        "composition_key": record.composition_key,
                        "post_id": record.post_id,
                        "source_key": source_key,
                    },
                    code="composition_source_index_unverified",
                )
        return expected

    def _download(
        self, core: Any, message: Message, media_slug: str, max_media_bytes: int | None
    ) -> Path:
        assert message.media is not None
        cache_directory = Path(self.media_directory) / "ui-cache" / "full"
        cache_directory.mkdir(parents=True, exist_ok=True)
        remote_id = int(message.media.remote_id or 0)
        prefix = f"{message.peer.type.value}_{message.peer.id}_{message.id}_{remote_id}"
        existing = max(
            (item for item in cache_directory.glob(f"{prefix}.*") if item.is_file() and not item.name.endswith(".partial")),
            key=lambda item: item.stat().st_mtime,
            default=None,
        )
        if existing is not None and (max_media_bytes is None or existing.stat().st_size <= max_media_bytes):
            return existing
        result = core.media.download(
            message.media,
            MediaDownloadOptions(
                output_directory=cache_directory,
                file_name=prefix,
                overwrite=True,
                max_bytes=max_media_bytes,
                request_delay_seconds=0.15,
            ),
        )
        return Path(result.path)

    def _render_body(
        self,
        request: WordPressCompositionRequest,
        plan: WordPressCompositionPlan,
        messages: tuple[Message, ...],
        media_items: list[WordPressMedia | None],
    ) -> str:
        chunks = [self._identity_marker(plan)]
        for index, (message, media) in enumerate(zip(messages, media_items, strict=True)):
            source = request.sources[index]
            chunks.append(f'<!-- eitaa-source:{html.escape(source.source_key)} -->')
            show_media = media is not None
            if request.featured_source_index == index and not request.include_featured_in_body:
                show_media = False
            if show_media and media is not None and media.source_url:
                url = html.escape(media.source_url, quote=True)
                if media.is_image:
                    chunks.append(
                        f'<figure class="wp-block-image"><img src="{url}" alt="{html.escape(request.title, quote=True)}"></figure>'
                    )
                elif media.mime_type.startswith("video/"):
                    chunks.append(f'<figure class="wp-block-video"><video controls src="{url}"></video></figure>')
                elif media.mime_type.startswith("audio/"):
                    chunks.append(f'<figure class="wp-block-audio"><audio controls src="{url}"></audio></figure>')
                else:
                    label = html.escape(message.media.file_name if message.media and message.media.file_name else "دانلود فایل")
                    chunks.append(f'<p><a href="{url}">{label}</a></p>')
            if message.text.strip():
                paragraphs = [part.strip() for part in re.split(r"\n\s*\n", message.text) if part.strip()]
                for paragraph in paragraphs:
                    chunks.append(f"<p>{html.escape(paragraph).replace(chr(10), '<br>')}</p>")
            if index < len(messages) - 1:
                chunks.append("<!-- wp:separator --><hr class=\"wp-block-separator has-alpha-channel-opacity\"/><!-- /wp:separator -->")
        return "\n\n".join(chunks)

    @staticmethod
    def _featured_media_id(
        request: WordPressCompositionRequest,
        messages: tuple[Message, ...],
        media_items: list[WordPressMedia | None],
    ) -> int | None:
        if request.featured_source_index is None:
            return None
        message = messages[request.featured_source_index]
        media = media_items[request.featured_source_index]
        if not ComposeMessagesToWordPress._is_image_message(message) or media is None or not media.is_image:
            raise CompositionValidationError(
                "featured_source_index must refer to a selected image message.",
                safe_context={"featured_source_index": request.featured_source_index},
                code="composition_featured_source_not_image",
            )
        return media.id

    @staticmethod
    def _is_image_message(message: Message) -> bool:
        return bool(
            message.media
            and message.media.type in {MediaType.PHOTO, MediaType.IMAGE_DOCUMENT, MediaType.STICKER}
        )

    @staticmethod
    def _post_slug(composition_key: str) -> str:
        normalized = _SLUG_CHARS.sub("-", composition_key.strip().lower()).strip("-")
        if not normalized:
            normalized = hashlib.sha256(composition_key.encode("utf-8")).hexdigest()[:16]
        suffix = hashlib.sha256(composition_key.encode("utf-8")).hexdigest()[:10]
        return f"eitaa-composition-{normalized[:150]}-{suffix}"[:200].rstrip("-")

    @staticmethod
    def _media_slug(source: Any, content_hash: str) -> str:
        return (
            f"eitaa-{source.peer.type.value}-{source.peer.id}-{source.message_id}-"
            f"{content_hash[:12]}-media"
        )

    @staticmethod
    def _identity_marker_prefix(plan: WordPressCompositionPlan) -> str:
        key_hash = hashlib.sha256(plan.request.composition_key.encode("utf-8")).hexdigest()[:16]
        return f"<!-- eitaa-bridge-composition site={plan.request.site_key} key={key_hash} "

    @staticmethod
    def _identity_marker(plan: WordPressCompositionPlan) -> str:
        return ComposeMessagesToWordPress._identity_marker_prefix(plan) + f"hash={plan.composition_hash[:16]} -->"

    def _unique_post(self, slug: str) -> WordPressPost | None:
        found = self.wordpress.find_posts_by_slug(slug)
        if len(found) > 1:
            raise CompositionCollisionError(
                "Multiple WordPress posts use the deterministic composition slug.",
                safe_context={"post_slug": slug, "count": len(found)},
                code="composition_duplicate_posts",
            )
        return found[0] if found else None

    def _unique_media(self, slug: str) -> WordPressMedia | None:
        found = self.wordpress.find_media_by_slug(slug)
        if len(found) > 1:
            raise CompositionCollisionError(
                "Multiple WordPress media items use one deterministic source slug.",
                safe_context={"media_slug": slug, "count": len(found)},
                code="composition_duplicate_media",
            )
        return found[0] if found else None
