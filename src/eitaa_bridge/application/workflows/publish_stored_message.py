from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eitaa_core import (
    MediaDownloadOptions,
    MediaType,
    Message,
    Peer,
    PublicationRecord,
    PublicationStatus,
)

from ...domain import (
    WordPressMedia,
    WordPressPost,
    WordPressPublicationPlan,
    WordPressPublicationResult,
)
from ...errors import (
    BridgeError,
    PublicationBlockedError,
    PublicationCollisionError,
    PublicationMessageNotFoundError,
    PublicationWorkflowError,
    WordPressAmbiguousWriteError,
    WordPressError,
    WordPressHttpError,
)
from ...infrastructure.diagnostics import BridgeDiagnosticManager
from ..services.wordpress_service import WordPressService

_TARGET_TYPE = "wordpress"
_TITLE_LIMIT = 160
_SPACE = re.compile(r"\s+")


@dataclass(slots=True)
class PublishStoredMessageToWordPress:
    """Publish one locally stored Core message as a controlled WordPress Draft.

    Core owns message data, content hashes, and publication lifecycle state.
    Bridge owns deterministic WordPress slugs, rendering, media transfer, and
    write reconciliation. WordPress writes are never retried automatically.
    """

    wordpress: WordPressService
    diagnostics: BridgeDiagnosticManager
    media_directory: Path

    def preview(
        self,
        core: Any,
        peer: Peer,
        message_id: int,
        *,
        site_key: str,
        title: str | None = None,
        category_id: int | None = None,
        include_media: bool = True,
    ) -> WordPressPublicationResult:
        message, plan = self._build_plan(
            core,
            peer,
            message_id,
            site_key=site_key,
            title=title,
            category_id=category_id,
            include_media=include_media,
        )
        del message
        publication = self._get_publication(core, peer, message_id, site_key)
        return WordPressPublicationResult(
            outcome="preview",
            plan=plan,
            publication=publication,
        )

    def status(
        self,
        core: Any,
        peer: Peer,
        message_id: int,
        *,
        site_key: str,
        title: str | None = None,
        category_id: int | None = None,
        include_media: bool = True,
    ) -> WordPressPublicationResult:
        message, plan = self._build_plan(
            core,
            peer,
            message_id,
            site_key=site_key,
            title=title,
            category_id=category_id,
            include_media=include_media,
        )
        del message
        publication = self._get_publication(core, peer, message_id, site_key)
        return WordPressPublicationResult(
            outcome="status",
            plan=plan,
            publication=publication,
        )

    def update_preview(
        self,
        core: Any,
        peer: Peer,
        message_id: int,
        *,
        site_key: str,
        title: str | None = None,
        category_id: int | None = None,
        include_media: bool = True,
        allow_live_update: bool = False,
        restore_trashed: bool = False,
    ) -> WordPressPublicationResult:
        """Inspect whether one existing WordPress publication needs an update."""
        message, plan = self._build_plan(
            core,
            peer,
            message_id,
            site_key=site_key,
            title=title,
            category_id=category_id,
            include_media=include_media,
        )
        publication = self._require_existing_publication(core, peer, message_id, site_key)
        post = self._resolve_remote_post(publication, plan, require_present=False)
        if post is None:
            return WordPressPublicationResult(
                outcome="update_preview",
                action="remote_missing",
                plan=plan,
                publication=publication,
                post=None,
                remote_matches_plan=False,
            )
        trashed = post.status == "trash"
        live = post.status not in {"draft", "trash"}
        media = self._preview_media(plan, post, publication)
        content = self._render_content(message, plan, media)
        expected_featured = media.id if media and media.is_image else None
        matches = self._post_matches_plan(
            post,
            plan,
            content,
            expected_featured,
        )
        if trashed:
            action = "restore_required" if restore_trashed else "blocked_trashed_post"
        elif matches:
            action = "reconcile_local_state" if publication.stale or publication.status is PublicationStatus.NEEDS_UPDATE else "already_current"
        elif live and not allow_live_update:
            action = "blocked_live_post"
        elif publication.stale or publication.status is PublicationStatus.NEEDS_UPDATE:
            action = "update_required"
        else:
            action = "remote_drift"
        return WordPressPublicationResult(
            outcome="update_preview",
            action=action,
            plan=plan,
            publication=publication,
            post=post,
            media=media,
            remote_matches_plan=matches,
            live_update=live,
        )

    def update_execute(
        self,
        core: Any,
        peer: Peer,
        message_id: int,
        *,
        site_key: str,
        title: str | None = None,
        category_id: int | None = None,
        include_media: bool = True,
        max_media_bytes: int | None = 100 * 1024 * 1024,
        allow_live_update: bool = False,
        overwrite_remote_drift: bool = False,
        restore_trashed: bool = False,
    ) -> WordPressPublicationResult:
        """Update exactly one existing WordPress post in a controlled manner.

        No new post is created by this method. A non-Draft post and unexpected
        remote drift both require explicit opt-in. Ambiguous POST outcomes are
        reconciled with a safe GET before any future write is allowed.
        """
        message, plan = self._build_plan(
            core,
            peer,
            message_id,
            site_key=site_key,
            title=title,
            category_id=category_id,
            include_media=include_media,
        )
        publication = self._require_existing_publication(core, peer, message_id, site_key)
        post = self._resolve_remote_post(publication, plan, require_present=True)
        assert post is not None
        trashed = post.status == "trash"
        live = post.status not in {"draft", "trash"}
        if trashed and not restore_trashed:
            raise PublicationBlockedError(
                "The recorded WordPress post is in Trash. Use the explicit restore-trashed option to restore this same post as a Draft before updating it.",
                safe_context={
                    "site_key": site_key,
                    "peer": peer.safe_summary(),
                    "message_id": message_id,
                    "post_id": post.id,
                    "post_status": post.status,
                },
                code="publication_trashed_post_blocked",
            )
        if live and not allow_live_update:
            raise PublicationBlockedError(
                "The WordPress post is not a Draft. Use the explicit allow-live-update option to modify it.",
                safe_context={
                    "site_key": site_key,
                    "peer": peer.safe_summary(),
                    "message_id": message_id,
                    "post_id": post.id,
                    "post_status": post.status,
                },
                code="publication_live_update_blocked",
            )

        media = self._preview_media(plan, post, publication)
        downloaded_path: Path | None = None
        if plan.media_slug is not None and media is None:
            downloaded_path = self._download_media(
                core,
                message,
                plan,
                max_media_bytes=max_media_bytes,
            )
            media = self._upload_or_reconcile_media(downloaded_path, message, plan)
        content = self._render_content(message, plan, media)
        expected_featured = media.id if media and media.is_image else None
        matches = self._post_matches_plan(post, plan, content, expected_featured)

        if matches and not trashed:
            publication = self._mark_published(core, peer, message_id, site_key, post)
            return WordPressPublicationResult(
                outcome="reconciled_current_post" if publication.stale is False else "already_current",
                action="reconciled_without_write",
                plan=plan,
                publication=publication,
                post=post,
                media=media,
                downloaded_path=downloaded_path,
                recovered=True,
                remote_matches_plan=True,
                live_update=live,
            )

        local_changed = publication.stale or publication.status is PublicationStatus.NEEDS_UPDATE
        if not trashed and not local_changed and not overwrite_remote_drift:
            raise PublicationBlockedError(
                "The current Core message has not changed, but the WordPress post differs from the Bridge payload. Use overwrite-remote-drift only after reviewing the remote post.",
                safe_context={
                    "site_key": site_key,
                    "peer": peer.safe_summary(),
                    "message_id": message_id,
                    "post_id": post.id,
                    "post_status": post.status,
                },
                code="publication_remote_drift",
            )

        if publication.status is PublicationStatus.PROCESSING:
            raise PublicationBlockedError(
                "A previous WordPress update has an unresolved outcome and the remote post does not match the current payload. Bridge will not issue another write automatically.",
                safe_context={
                    "site_key": site_key,
                    "peer": peer.safe_summary(),
                    "message_id": message_id,
                    "post_id": post.id,
                },
                code="publication_update_processing_unresolved",
            )

        self._mark_processing(core, peer, message_id, site_key)
        try:
            updated, recovered = self._update_or_reconcile_post(
                post,
                plan,
                content,
                expected_featured,
                restore_to_draft=trashed,
            )
            publication = self._mark_published(
                core, peer, message_id, site_key, updated
            )
            result = WordPressPublicationResult(
                outcome=(
                    "recovered_restore" if recovered and trashed
                    else "restored_and_updated" if trashed
                    else "recovered_update" if recovered
                    else "updated"
                ),
                action="restored_existing_post" if trashed else "updated_existing_post",
                plan=plan,
                publication=publication,
                post=updated,
                media=media,
                downloaded_path=downloaded_path,
                recovered=recovered,
                remote_matches_plan=True,
                live_update=live,
            )
            self.diagnostics.emit(
                "publication", "publication_update_completed", fields=result.safe_summary()
            )
            return result
        except WordPressAmbiguousWriteError:
            self.diagnostics.emit(
                "publication",
                "publication_update_outcome_ambiguous",
                level="error",
                fields={"plan": plan.safe_summary(), "core_state": "processing"},
            )
            raise
        except WordPressError as exc:
            self._mark_failed_best_effort(core, peer, message_id, site_key, exc.code)
            raise
        except BridgeError as exc:
            self._mark_failed_best_effort(core, peer, message_id, site_key, exc.code)
            raise

    def execute(
        self,
        core: Any,
        peer: Peer,
        message_id: int,
        *,
        site_key: str,
        title: str | None = None,
        category_id: int | None = None,
        include_media: bool = True,
        max_media_bytes: int | None = 100 * 1024 * 1024,
        retry_skipped: bool = False,
    ) -> WordPressPublicationResult:
        message, plan = self._build_plan(
            core,
            peer,
            message_id,
            site_key=site_key,
            title=title,
            category_id=category_id,
            include_media=include_media,
        )
        existing = self._get_publication(core, peer, message_id, site_key)
        self.diagnostics.emit(
            "publication",
            "publication_requested",
            fields={
                "plan": plan.safe_summary(),
                "existing": existing.safe_summary() if existing else None,
            },
        )

        if existing is not None:
            if existing.status is PublicationStatus.PUBLISHED and not existing.stale:
                return WordPressPublicationResult(
                    outcome="already_published",
                    plan=plan,
                    publication=existing,
                )
            if existing.status is PublicationStatus.NEEDS_UPDATE or existing.stale:
                raise PublicationBlockedError(
                    "The Eitaa message changed after publication. Use the explicit publication update-preview and update commands.",
                    safe_context={
                        "site_key": site_key,
                        "peer": peer.safe_summary(),
                        "message_id": message_id,
                        "publication_status": existing.status.value,
                        "stale": existing.stale,
                    },
                    code="publication_needs_update",
                )
            if existing.status is PublicationStatus.SKIPPED and not retry_skipped:
                raise PublicationBlockedError(
                    "The publication is marked skipped. Use the explicit retry-skipped option to continue.",
                    safe_context={
                        "site_key": site_key,
                        "peer": peer.safe_summary(),
                        "message_id": message_id,
                    },
                    code="publication_skipped",
                )
            if existing.status is PublicationStatus.PROCESSING:
                try:
                    return self._resume_processing(core, message, plan, existing)
                except WordPressAmbiguousWriteError:
                    raise
                except PublicationBlockedError:
                    raise
                except WordPressError as exc:
                    self._mark_failed_best_effort(
                        core, peer, message_id, site_key, exc.code
                    )
                    raise

        # A safe read before changing state recovers a WordPress object created by
        # a previous run whose local Core state was not completed.
        post = self._unique_post(plan.post_slug)
        if post is not None:
            publication = self._mark_published(core, peer, message_id, site_key, post)
            return WordPressPublicationResult(
                outcome="recovered_post",
                plan=plan,
                publication=publication,
                post=post,
                recovered=True,
            )

        media: WordPressMedia | None = None
        if plan.media_slug is not None:
            media = self._unique_media(plan.media_slug)

        self._mark_pending_if_needed(core, peer, message_id, site_key, existing)
        self._mark_processing(core, peer, message_id, site_key)

        downloaded_path: Path | None = None
        try:
            if plan.media_slug is not None and media is None:
                downloaded_path = self._download_media(
                    core,
                    message,
                    plan,
                    max_media_bytes=max_media_bytes,
                )
                media = self._upload_or_reconcile_media(downloaded_path, message, plan)

            rendered_content = self._render_content(message, plan, media)
            # Recheck immediately before the POST to close the normal duplicate
            # window between the initial read and the external write.
            post = self._unique_post(plan.post_slug)
            recovered = post is not None
            if post is None:
                post = self._create_or_reconcile_post(plan, rendered_content, media)
                recovered = post.slug == plan.post_slug and self._last_post_write_recovered

            publication = self._mark_published(core, peer, message_id, site_key, post)
            result = WordPressPublicationResult(
                outcome="published" if not recovered else "recovered_post",
                plan=plan,
                publication=publication,
                post=post,
                media=media,
                downloaded_path=downloaded_path,
                recovered=recovered,
            )
            self.diagnostics.emit(
                "publication", "publication_completed", fields=result.safe_summary()
            )
            return result
        except WordPressAmbiguousWriteError:
            # Unknown external outcomes remain processing. A later explicit run
            # reconciles by deterministic slug before any additional write.
            self.diagnostics.emit(
                "publication",
                "publication_outcome_ambiguous",
                level="error",
                fields={"plan": plan.safe_summary(), "core_state": "processing"},
            )
            raise
        except PublicationBlockedError:
            raise
        except WordPressError as exc:
            self._mark_failed_best_effort(core, peer, message_id, site_key, exc.code)
            raise
        except BridgeError as exc:
            self._mark_failed_best_effort(core, peer, message_id, site_key, exc.code)
            raise
        except Exception as exc:
            self._mark_failed_best_effort(
                core, peer, message_id, site_key, "publication_workflow_error"
            )
            debug_file = self.diagnostics.emit(
                "publication",
                "publication_failed",
                level="error",
                fields={"plan": plan.safe_summary(), "error_type": type(exc).__name__},
            )
            raise PublicationWorkflowError(
                "The controlled publication workflow failed.",
                safe_context={
                    "site_key": site_key,
                    "peer": peer.safe_summary(),
                    "message_id": message_id,
                    "error_type": type(exc).__name__,
                },
                debug_file=debug_file,
            ) from exc

    _last_post_write_recovered: bool = False

    def _resume_processing(
        self,
        core: Any,
        message: Message,
        plan: WordPressPublicationPlan,
        existing: PublicationRecord,
    ) -> WordPressPublicationResult:
        post = self._unique_post(plan.post_slug)
        if post is not None:
            publication = self._mark_published(
                core, message.peer, message.id, plan.site_key, post
            )
            return WordPressPublicationResult(
                outcome="recovered_post",
                plan=plan,
                publication=publication,
                post=post,
                recovered=True,
            )

        if plan.media_slug is not None:
            media = self._unique_media(plan.media_slug)
            if media is not None:
                rendered = self._render_content(message, plan, media)
                post = self._create_or_reconcile_post(plan, rendered, media)
                publication = self._mark_published(
                    core, message.peer, message.id, plan.site_key, post
                )
                return WordPressPublicationResult(
                    outcome="recovered_media_and_published",
                    plan=plan,
                    publication=publication,
                    post=post,
                    media=media,
                    recovered=True,
                )

        raise PublicationBlockedError(
            "The previous WordPress write has an unresolved outcome. Bridge will not issue another write automatically.",
            safe_context={
                "site_key": plan.site_key,
                "peer_type": plan.peer_type,
                "peer_id": plan.peer_id,
                "message_id": plan.message_id,
                "publication_status": existing.status.value,
                "post_slug": plan.post_slug,
                "media_slug": plan.media_slug,
            },
            code="publication_processing_unresolved",
        )

    def _build_plan(
        self,
        core: Any,
        peer: Peer,
        message_id: int,
        *,
        site_key: str,
        title: str | None,
        category_id: int | None,
        include_media: bool,
    ) -> tuple[Message, WordPressPublicationPlan]:
        if message_id <= 0:
            raise PublicationWorkflowError("message_id must be positive.")
        if category_id is not None and category_id <= 0:
            raise PublicationWorkflowError("category_id must be positive or omitted.")
        try:
            message = core.messages.get(peer, message_id)
            content_hash = core.messages.content_hash(peer, message_id)
        except Exception as exc:
            raise PublicationWorkflowError(
                "Core could not read the locally stored message.",
                safe_context={
                    "peer": peer.safe_summary(),
                    "message_id": message_id,
                    "error_type": type(exc).__name__,
                },
                code="core_message_read_error",
            ) from exc
        if message is None or not content_hash:
            raise PublicationMessageNotFoundError(
                "The message is not stored in the configured Core database.",
                safe_context={"peer": peer.safe_summary(), "message_id": message_id},
            )
        has_media = bool(include_media and message.media is not None)
        if not message.text.strip() and not has_media:
            raise PublicationBlockedError(
                "The selected message has neither publishable text nor enabled media.",
                safe_context={"peer": peer.safe_summary(), "message_id": message_id},
                code="publication_empty_message",
            )
        selected_title = self._derive_title(message, title)
        post_slug = f"eitaa-{peer.type.value}-{peer.id}-{message_id}"
        media_fingerprint = self._media_fingerprint(message) if has_media else None
        media_slug = (
            f"{post_slug}-{media_fingerprint[:12]}-media"
            if media_fingerprint else None
        )
        base_content = self._render_text(message.text)
        plan = WordPressPublicationPlan(
            site_key=site_key,
            peer_type=peer.type.value,
            peer_id=peer.id,
            message_id=message_id,
            content_hash=content_hash,
            title=selected_title,
            content=base_content,
            post_slug=post_slug,
            media_slug=media_slug,
            media_fingerprint=media_fingerprint,
            media_present=has_media,
            media_type=message.media.type.value if has_media and message.media else None,
            category_id=category_id,
        )
        return message, plan

    @staticmethod
    def _derive_title(message: Message, override: str | None) -> str:
        if override is not None:
            candidate = _SPACE.sub(" ", override).strip()
            if not candidate:
                raise PublicationWorkflowError("title cannot be blank.")
            return candidate[:_TITLE_LIMIT]
        for line in message.text.splitlines():
            candidate = _SPACE.sub(" ", line).strip()
            if candidate:
                return candidate[:_TITLE_LIMIT]
        media_label = message.media.type.value if message.media else "message"
        return f"Eitaa {media_label} {message.id}"[:_TITLE_LIMIT]

    @staticmethod
    def _render_text(text: str) -> str:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            return ""
        paragraphs: list[str] = []
        for block in re.split(r"\n\s*\n", normalized):
            lines = [html.escape(line) for line in block.split("\n")]
            paragraphs.append("<p>" + "<br>\n".join(lines) + "</p>")
        return "\n".join(paragraphs)

    def _render_content(
        self,
        message: Message,
        plan: WordPressPublicationPlan,
        media: WordPressMedia | None,
    ) -> str:
        parts: list[str] = [plan.content] if plan.content else []
        if media is not None and not media.is_image:
            url = html.escape(media.source_url or "", quote=True)
            if url:
                if media.mime_type.startswith("audio/"):
                    parts.append(f'<audio controls preload="metadata" src="{url}"></audio>')
                elif media.mime_type.startswith("video/"):
                    parts.append(f'<video controls preload="metadata" src="{url}"></video>')
                else:
                    parts.append(f'<p><a href="{url}">دریافت فایل پیوست</a></p>')
            else:
                parts.append("<p>پیوست رسانه‌ای در کتابخانه وردپرس بارگذاری شد.</p>")
        parts.append(self._marker(plan))
        return "\n".join(parts)

    @staticmethod
    def _marker(plan: WordPressPublicationPlan) -> str:
        return (
            f"<!-- eitaa-bridge:{plan.site_key}:{plan.peer_type}:"
            f"{plan.peer_id}:{plan.message_id}:{plan.content_hash[:12]} -->"
        )

    @staticmethod
    def _identity_marker_prefix(plan: WordPressPublicationPlan) -> str:
        """Return the stable marker prefix for one Bridge publication identity.

        The final marker segment is the mutable Core content hash.  Excluding
        that segment lets Update 1 safely recognize a v0.3 Draft after the
        Eitaa message changes or after WordPress normalizes the requested slug.
        """
        return (
            f"<!-- eitaa-bridge:{plan.site_key}:{plan.peer_type}:"
            f"{plan.peer_id}:{plan.message_id}:"
        )

    @staticmethod
    def _media_fingerprint(message: Message) -> str | None:
        media = message.media
        if media is None:
            return None
        payload = {
            "type": media.type.value,
            "remote_id": media.remote_id,
            "access_hash": media.access_hash,
            "file_reference_sha256": hashlib.sha256(media.file_reference or b"").hexdigest(),
            "mime_type": media.mime_type,
            "file_name": media.file_name,
            "size": media.size,
            "dc_id": media.dc_id,
            "date": media.date,
            "constructor": media.constructor,
            "thumb_types": list(media.thumb_types),
            "attributes": list(media.attributes),
        }
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _preview_media(
        self,
        plan: WordPressPublicationPlan,
        post: WordPressPost,
        publication: PublicationRecord,
    ) -> WordPressMedia | None:
        if plan.media_slug is None:
            return None
        media = self._unique_media(plan.media_slug)
        if media is not None:
            return media
        # A v0.3 publication used the whole content hash for its media slug. If
        # the local content has not changed, the current featured item remains a
        # safe compatibility fallback and avoids an unnecessary duplicate upload.
        if (
            not publication.stale
            and publication.status is PublicationStatus.PUBLISHED
            and post.featured_media_id is not None
        ):
            try:
                return self.wordpress.get_media(post.featured_media_id)
            except WordPressError:
                return None
        return None

    @staticmethod
    def _post_matches_plan(
        post: WordPressPost,
        plan: WordPressPublicationPlan,
        content: str,
        featured_media_id: int | None,
        *,
        expected_status: str | None = None,
    ) -> bool:
        if expected_status is not None and post.status != expected_status:
            return False
        if post.slug != plan.post_slug:
            return False
        if not post.contains_marker(PublishStoredMessageToWordPress._marker(plan)):
            return False
        return post.matches_bridge_payload(
            title=plan.title,
            content=content,
            featured_media_id=featured_media_id,
            category_id=plan.category_id,
        )

    def _require_existing_publication(
        self,
        core: Any,
        peer: Peer,
        message_id: int,
        site_key: str,
    ) -> PublicationRecord:
        publication = self._get_publication(core, peer, message_id, site_key)
        if publication is None or publication.external_post_id is None:
            raise PublicationBlockedError(
                "The selected message has no recorded WordPress post to update. Run the create publication command first.",
                safe_context={
                    "site_key": site_key,
                    "peer": peer.safe_summary(),
                    "message_id": message_id,
                },
                code="publication_update_missing_record",
            )
        return publication

    def _resolve_remote_post(
        self,
        publication: PublicationRecord,
        plan: WordPressPublicationPlan,
        *,
        require_present: bool,
    ) -> WordPressPost | None:
        post_id: int | None = None
        try:
            post_id = int(publication.external_post_id or "")
        except (TypeError, ValueError):
            post_id = None
        post: WordPressPost | None = None
        if post_id and post_id > 0:
            try:
                post = self.wordpress.get_post(post_id)
            except WordPressHttpError as exc:
                if exc.code != "wordpress_http_404":
                    raise
        by_slug = self._unique_post(plan.post_slug)
        if post is not None and by_slug is not None and by_slug.id != post.id:
            raise PublicationCollisionError(
                "The recorded WordPress post ID and deterministic slug resolve to different posts.",
                safe_context={
                    "recorded_post_id": post.id,
                    "slug_post_id": by_slug.id,
                    "slug": plan.post_slug,
                },
                code="publication_post_identity_collision",
            )
        if post is not None and by_slug is not None and by_slug.id == post.id:
            # Prefer the slug lookup representation when both authenticated
            # reads agree on the same WordPress object.
            post = by_slug
        if (
            post is not None
            and post.slug != plan.post_slug
            and not post.contains_marker(self._identity_marker_prefix(plan))
        ):
            raise PublicationCollisionError(
                "The recorded WordPress post ID no longer has the deterministic Bridge slug.",
                safe_context={
                    "post_id": post.id,
                    "expected_slug": plan.post_slug,
                    "actual_slug_present": bool(post.slug),
                    "identity_marker_present": False,
                },
                code="publication_post_identity_mismatch",
            )
        resolved = post or by_slug
        if require_present and resolved is None:
            raise PublicationBlockedError(
                "The recorded WordPress post is missing. Update mode never creates a replacement post automatically.",
                safe_context={
                    "site_key": plan.site_key,
                    "peer_type": plan.peer_type,
                    "peer_id": plan.peer_id,
                    "message_id": plan.message_id,
                    "post_slug": plan.post_slug,
                },
                code="publication_remote_post_missing",
            )
        return resolved

    def _update_or_reconcile_post(
        self,
        current: WordPressPost,
        plan: WordPressPublicationPlan,
        content: str,
        featured_media_id: int | None,
        *,
        restore_to_draft: bool = False,
    ) -> tuple[WordPressPost, bool]:
        try:
            updated = self.wordpress.update_post(
                current.id,
                title=plan.title,
                content=content,
                slug=plan.post_slug,
                category_id=plan.category_id,
                featured_media_id=featured_media_id,
                restore_to_draft=restore_to_draft,
            )
            expected_status = "draft" if restore_to_draft else None
            if not self._post_matches_plan(
                updated, plan, content, featured_media_id, expected_status=expected_status
            ):
                # WordPress can omit raw fields from a write response. Confirm by
                # a safe GET before considering the write ambiguous.
                try:
                    updated = self.wordpress.get_post(current.id)
                except WordPressError as exc:
                    raise WordPressAmbiguousWriteError(
                        "The WordPress update may have succeeded, but its result could not be verified.",
                        safe_context={
                            "site_key": plan.site_key,
                            "post_id": current.id,
                            "automatic_retry": False,
                            "verification_error": exc.code,
                        },
                    ) from exc
                if not self._post_matches_plan(
                    updated, plan, content, featured_media_id, expected_status=expected_status
                ):
                    raise WordPressAmbiguousWriteError(
                        "WordPress accepted the update but the returned post could not be verified.",
                        safe_context={
                            "site_key": plan.site_key,
                            "post_id": current.id,
                            "automatic_retry": False,
                        },
                    )
            return updated, False
        except WordPressAmbiguousWriteError as ambiguous:
            try:
                recovered = self.wordpress.get_post(current.id)
            except WordPressError:
                raise ambiguous
            expected_status = "draft" if restore_to_draft else None
            if self._post_matches_plan(
                recovered, plan, content, featured_media_id, expected_status=expected_status
            ):
                self.diagnostics.emit(
                    "publication",
                    "ambiguous_update_recovered",
                    fields={"plan": plan.safe_summary(), "post": recovered.safe_summary()},
                )
                return recovered, True
            raise ambiguous

    def _download_media(
        self,
        core: Any,
        message: Message,
        plan: WordPressPublicationPlan,
        *,
        max_media_bytes: int | None,
    ) -> Path:
        assert message.media is not None
        output = Path(self.media_directory) / "ui-cache" / "full"
        output.mkdir(parents=True, exist_ok=True)
        remote_id = int(message.media.remote_id or 0)
        prefix = f"{message.peer.type.value}_{message.peer.id}_{message.id}_{remote_id}"
        existing = max(
            (item for item in output.glob(f"{prefix}.*") if item.is_file() and not item.name.endswith(".partial")),
            key=lambda item: item.stat().st_mtime,
            default=None,
        )
        if existing is not None and (max_media_bytes is None or existing.stat().st_size <= max_media_bytes):
            return existing
        options = MediaDownloadOptions(
            output_directory=output,
            file_name=prefix,
            overwrite=True,
            max_bytes=max_media_bytes,
            request_delay_seconds=0.15,
        )
        try:
            result = core.media.download(message.media, options)
        except Exception as exc:
            raise PublicationWorkflowError(
                "Core could not download the message media.",
                safe_context={
                    "peer": message.peer.safe_summary(),
                    "message_id": message.id,
                    "media_type": message.media.type.value,
                    "error_type": type(exc).__name__,
                },
                code="core_media_download_error",
            ) from exc
        return Path(result.path)

    def _upload_or_reconcile_media(
        self,
        path: Path,
        message: Message,
        plan: WordPressPublicationPlan,
    ) -> WordPressMedia:
        assert plan.media_slug is not None
        try:
            return self.wordpress.upload_media(
                path,
                mime_type=message.media.mime_type if message.media else None,
                slug=plan.media_slug,
                title=plan.title,
                alt_text=(
                    plan.title
                    if message.media
                    and message.media.type
                    in {MediaType.PHOTO, MediaType.IMAGE_DOCUMENT, MediaType.STICKER}
                    else None
                ),
            )
        except WordPressAmbiguousWriteError:
            recovered = self._unique_media(plan.media_slug)
            if recovered is not None:
                self.diagnostics.emit(
                    "publication",
                    "ambiguous_media_recovered",
                    fields={"plan": plan.safe_summary(), "media": recovered.safe_summary()},
                )
                return recovered
            raise

    def _create_or_reconcile_post(
        self,
        plan: WordPressPublicationPlan,
        content: str,
        media: WordPressMedia | None,
    ) -> WordPressPost:
        self._last_post_write_recovered = False
        try:
            return self.wordpress.create_text_draft(
                title=plan.title,
                content=content,
                slug=plan.post_slug,
                category_id=plan.category_id,
                featured_media_id=media.id if media and media.is_image else None,
            )
        except WordPressAmbiguousWriteError:
            recovered = self._unique_post(plan.post_slug)
            if recovered is not None:
                self._last_post_write_recovered = True
                self.diagnostics.emit(
                    "publication",
                    "ambiguous_post_recovered",
                    fields={"plan": plan.safe_summary(), "post": recovered.safe_summary()},
                )
                return recovered
            raise

    def _unique_post(self, slug: str) -> WordPressPost | None:
        posts = self.wordpress.find_posts_by_slug(slug)
        if len(posts) > 1:
            raise PublicationCollisionError(
                "Multiple WordPress posts use the deterministic publication slug.",
                safe_context={"slug": slug, "count": len(posts)},
                code="publication_post_slug_collision",
            )
        return posts[0] if posts else None

    def _unique_media(self, slug: str) -> WordPressMedia | None:
        items = self.wordpress.find_media_by_slug(slug)
        if len(items) > 1:
            raise PublicationCollisionError(
                "Multiple WordPress media items use the deterministic publication slug.",
                safe_context={"slug": slug, "count": len(items)},
                code="publication_media_slug_collision",
            )
        return items[0] if items else None

    @staticmethod
    def _get_publication(
        core: Any, peer: Peer, message_id: int, site_key: str
    ) -> PublicationRecord | None:
        try:
            return core.publications.get(
                peer,
                message_id,
                target_type=_TARGET_TYPE,
                target_key=site_key,
            )
        except Exception as exc:
            raise PublicationWorkflowError(
                "Core could not read publication state.",
                safe_context={
                    "peer": peer.safe_summary(),
                    "message_id": message_id,
                    "site_key": site_key,
                    "error_type": type(exc).__name__,
                },
                code="core_publication_state_error",
            ) from exc

    @staticmethod
    def _mark_pending_if_needed(
        core: Any,
        peer: Peer,
        message_id: int,
        site_key: str,
        existing: PublicationRecord | None,
    ) -> None:
        if existing is None or existing.status in {
            PublicationStatus.FAILED,
            PublicationStatus.SKIPPED,
            PublicationStatus.PENDING,
        }:
            try:
                core.publications.mark_pending(
                    peer,
                    message_id,
                    target_type=_TARGET_TYPE,
                    target_key=site_key,
                )
            except Exception as exc:
                raise PublicationWorkflowError(
                    "Core could not mark the publication as pending.",
                    safe_context={
                        "peer": peer.safe_summary(),
                        "message_id": message_id,
                        "site_key": site_key,
                        "error_type": type(exc).__name__,
                    },
                    code="core_publication_state_error",
                ) from exc

    @staticmethod
    def _mark_processing(core: Any, peer: Peer, message_id: int, site_key: str) -> None:
        try:
            core.publications.mark_processing(
                peer,
                message_id,
                target_type=_TARGET_TYPE,
                target_key=site_key,
            )
        except Exception as exc:
            raise PublicationWorkflowError(
                "Core could not mark the publication as processing.",
                safe_context={
                    "peer": peer.safe_summary(),
                    "message_id": message_id,
                    "site_key": site_key,
                    "error_type": type(exc).__name__,
                },
                code="core_publication_state_error",
            ) from exc

    @staticmethod
    def _mark_published(
        core: Any,
        peer: Peer,
        message_id: int,
        site_key: str,
        post: WordPressPost,
    ) -> PublicationRecord:
        try:
            return core.publications.mark_published(
                peer,
                message_id,
                target_type=_TARGET_TYPE,
                target_key=site_key,
                external_post_id=str(post.id),
                external_url=post.link,
            )
        except Exception as exc:
            raise PublicationWorkflowError(
                "WordPress created the Draft, but Core could not record the published state. Run the same command again to reconcile it by slug.",
                safe_context={
                    "peer": peer.safe_summary(),
                    "message_id": message_id,
                    "site_key": site_key,
                    "post_id": post.id,
                    "error_type": type(exc).__name__,
                },
                code="core_publication_commit_error",
            ) from exc

    @staticmethod
    def _mark_failed_best_effort(
        core: Any,
        peer: Peer,
        message_id: int,
        site_key: str,
        error_code: str,
    ) -> None:
        try:
            core.publications.mark_failed(
                peer,
                message_id,
                target_type=_TARGET_TYPE,
                target_key=site_key,
                error_code=error_code[:128],
            )
        except Exception:
            # The original failure remains more actionable. A failed local state
            # write is intentionally not allowed to hide it.
            pass
