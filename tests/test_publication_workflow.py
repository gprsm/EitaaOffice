from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from eitaa_core import (
    MediaReference,
    MediaType,
    Message,
    Peer,
    PeerType,
    PublicationRecord,
    PublicationStatus,
)
from eitaa_bridge.application.workflows import PublishStoredMessageToWordPress
from eitaa_bridge.domain import WordPressMedia, WordPressPost
from eitaa_bridge.errors import (
    PublicationBlockedError,
    PublicationCollisionError,
    PublicationMessageNotFoundError,
    WordPressAmbiguousWriteError,
    WordPressHttpError,
)
from eitaa_bridge.infrastructure.diagnostics import BridgeDiagnosticManager


PEER = Peer(id=181197, type=PeerType.CHANNEL, access_hash=987654321)


def message(*, text="عنوان پیام\n\nمتن پیام", media=None):
    return Message(
        id=77,
        peer=PEER,
        date=datetime(2026, 7, 17, tzinfo=timezone.utc),
        text=text,
        media=media,
    )


class FakeMessages:
    def __init__(self, selected, digest="a" * 64):
        self.selected = selected
        self.digest = digest

    def get(self, peer, message_id):
        return self.selected if self.selected and message_id == self.selected.id else None

    def content_hash(self, peer, message_id):
        return self.digest if self.get(peer, message_id) else None


class FakePublications:
    def __init__(self, record=None):
        self.record = record
        self.calls = []

    def get(self, peer, message_id, *, target_type, target_key):
        self.calls.append(("get", target_type, target_key))
        return self.record

    def _record(self, peer, message_id, status, target_type, target_key, **changes):
        old = self.record
        data = dict(
            peer=peer,
            message_id=message_id,
            target_type=target_type,
            target_key=target_key,
            status=status,
            attempts=old.attempts if old else 0,
            external_post_id=old.external_post_id if old else None,
            external_url=old.external_url if old else None,
            published_content_hash=old.published_content_hash if old else None,
            error_code=None,
            current_content_hash="a" * 64,
        )
        data.update(changes)
        self.record = PublicationRecord(**data)
        return self.record

    def mark_pending(self, peer, message_id, *, target_type, target_key):
        self.calls.append(("pending", target_type, target_key))
        return self._record(peer, message_id, PublicationStatus.PENDING, target_type, target_key)

    def mark_processing(self, peer, message_id, *, target_type, target_key):
        self.calls.append(("processing", target_type, target_key))
        attempts = (self.record.attempts if self.record else 0) + 1
        return self._record(
            peer, message_id, PublicationStatus.PROCESSING,
            target_type, target_key, attempts=attempts,
        )

    def mark_published(
        self, peer, message_id, *, target_type, target_key,
        external_post_id, external_url,
    ):
        self.calls.append(("published", external_post_id, target_key))
        return self._record(
            peer, message_id, PublicationStatus.PUBLISHED,
            target_type, target_key,
            external_post_id=external_post_id,
            external_url=external_url,
            published_content_hash="a" * 64,
        )

    def mark_failed(self, peer, message_id, *, target_type, target_key, error_code):
        self.calls.append(("failed", error_code, target_key))
        return self._record(
            peer, message_id, PublicationStatus.FAILED,
            target_type, target_key, error_code=error_code,
        )


class FakeMediaService:
    def __init__(self, tmp_path):
        self.tmp_path = tmp_path
        self.calls = []

    def download(self, media, options):
        self.calls.append((media, options))
        path = Path(options.output_directory) / (options.file_name + ".jpg")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"image")
        return SimpleNamespace(path=path)


class FakeCore:
    def __init__(self, selected, tmp_path, record=None):
        self.messages = FakeMessages(selected)
        self.publications = FakePublications(record)
        self.media = FakeMediaService(tmp_path)


class FakeWordPress:
    def __init__(
        self,
        *,
        post_searches=None,
        media_searches=None,
        created_post=None,
        uploaded_media=None,
        create_error=None,
        upload_error=None,
        get_posts=None,
        get_media_result=None,
        updated_post=None,
        update_error=None,
    ):
        self.post_searches = list(post_searches or [()])
        self.media_searches = list(media_searches or [()])
        self.created_post = created_post or WordPressPost(
            id=500,
            status="draft",
            link="https://example.test/?p=500",
            slug="eitaa-channel-181197-77",
            site_key="medical-site",
        )
        self.uploaded_media = uploaded_media or WordPressMedia(
            id=600,
            status="inherit",
            media_type="image",
            mime_type="image/jpeg",
            source_url="https://example.test/uploads/600.jpg",
            slug="eitaa-channel-181197-77-aaaaaaaaaaaa-media",
            site_key="medical-site",
        )
        self.create_error = create_error
        self.upload_error = upload_error
        self.get_posts = list(get_posts or [])
        self.get_media_result = get_media_result
        self.updated_post = updated_post
        self.update_error = update_error
        self.calls = []

    def find_posts_by_slug(self, slug):
        self.calls.append(("find_post", slug))
        if self.post_searches:
            return tuple(self.post_searches.pop(0))
        return ()

    def find_media_by_slug(self, slug):
        self.calls.append(("find_media", slug))
        if self.media_searches:
            return tuple(self.media_searches.pop(0))
        return ()

    def get_post(self, post_id):
        self.calls.append(("get_post", post_id))
        if self.get_posts:
            value = self.get_posts.pop(0)
            if isinstance(value, Exception):
                raise value
            return value
        return self.created_post

    def get_media(self, media_id):
        self.calls.append(("get_media", media_id))
        if isinstance(self.get_media_result, Exception):
            raise self.get_media_result
        return self.get_media_result or self.uploaded_media

    def update_post(self, post_id, **kwargs):
        self.calls.append(("update", post_id, kwargs))
        if self.update_error:
            raise self.update_error
        if self.updated_post is not None:
            return self.updated_post
        return WordPressPost(
            id=post_id,
            status=self.created_post.status,
            link=self.created_post.link,
            slug=kwargs.get("slug"),
            site_key="medical-site",
            featured_media_id=kwargs.get("featured_media_id"),
            title_raw=kwargs.get("title"),
            content_raw=kwargs.get("content"),
            category_ids=((kwargs["category_id"],) if kwargs.get("category_id") else ()),
        )

    def create_text_draft(self, **kwargs):
        self.calls.append(("create", kwargs))
        if self.create_error:
            raise self.create_error
        return self.created_post

    def upload_media(self, path, **kwargs):
        self.calls.append(("upload", Path(path), kwargs))
        if self.upload_error:
            raise self.upload_error
        return self.uploaded_media


def workflow(tmp_path, wp):
    return PublishStoredMessageToWordPress(
        wp,
        BridgeDiagnosticManager(tmp_path / "diagnostics"),
        tmp_path / "media",
    )


def published_record(status=PublicationStatus.PUBLISHED, *, stale=False):
    return PublicationRecord(
        peer=PEER,
        message_id=77,
        target_type="wordpress",
        target_key="medical-site",
        status=status,
        external_post_id="500",
        external_url="https://example.test/?p=500",
        published_content_hash="b" * 64 if stale else "a" * 64,
        current_content_hash="a" * 64,
    )


def test_preview_has_no_wordpress_or_state_write(tmp_path):
    core = FakeCore(message(), tmp_path)
    wp = FakeWordPress()
    result = workflow(tmp_path, wp).preview(
        core, PEER, 77, site_key="medical-site"
    )
    assert result.outcome == "preview"
    assert result.plan.post_slug == "eitaa-channel-181197-77"
    assert wp.calls == []
    assert [call[0] for call in core.publications.calls] == ["get"]


def test_text_publication_transitions_to_published(tmp_path):
    core = FakeCore(message(), tmp_path)
    wp = FakeWordPress(post_searches=[(), ()])
    result = workflow(tmp_path, wp).execute(
        core, PEER, 77, site_key="medical-site"
    )
    assert result.outcome == "published"
    assert result.post.id == 500
    assert core.publications.record.status is PublicationStatus.PUBLISHED
    names = [call[0] for call in core.publications.calls]
    assert names == ["get", "pending", "processing", "published"]
    create = next(call for call in wp.calls if call[0] == "create")
    assert create[1]["slug"] == "eitaa-channel-181197-77"
    assert "عنوان پیام" in create[1]["content"]


def test_image_publication_downloads_uploads_and_sets_featured_media(tmp_path):
    selected = message(media=MediaReference(
        type=MediaType.PHOTO,
        remote_id=99,
        access_hash=123,
        file_reference=b"ref",
        mime_type="image/jpeg",
    ))
    core = FakeCore(selected, tmp_path)
    wp = FakeWordPress(post_searches=[(), ()], media_searches=[()])
    result = workflow(tmp_path, wp).execute(
        core, PEER, 77, site_key="medical-site"
    )
    assert result.media.id == 600
    assert len(core.media.calls) == 1
    upload = next(call for call in wp.calls if call[0] == "upload")
    assert upload[2]["slug"].startswith("eitaa-channel-181197-77-")
    assert upload[2]["slug"].endswith("-media")
    create = next(call for call in wp.calls if call[0] == "create")
    assert create[1]["featured_media_id"] == 600


def test_already_published_is_idempotent(tmp_path):
    core = FakeCore(message(), tmp_path, published_record())
    wp = FakeWordPress()
    result = workflow(tmp_path, wp).execute(
        core, PEER, 77, site_key="medical-site"
    )
    assert result.outcome == "already_published"
    assert wp.calls == []


def test_stale_publication_is_blocked_without_wordpress_write(tmp_path):
    core = FakeCore(
        message(), tmp_path,
        published_record(PublicationStatus.NEEDS_UPDATE, stale=True),
    )
    wp = FakeWordPress()
    with pytest.raises(PublicationBlockedError) as error:
        workflow(tmp_path, wp).execute(
            core, PEER, 77, site_key="medical-site"
        )
    assert error.value.code == "publication_needs_update"
    assert wp.calls == []


def test_processing_without_reconcilable_object_is_blocked(tmp_path):
    core = FakeCore(
        message(), tmp_path,
        published_record(PublicationStatus.PROCESSING),
    )
    wp = FakeWordPress(post_searches=[()])
    with pytest.raises(PublicationBlockedError) as error:
        workflow(tmp_path, wp).execute(
            core, PEER, 77, site_key="medical-site"
        )
    assert error.value.code == "publication_processing_unresolved"
    assert not any(call[0] == "create" for call in wp.calls)


def test_ambiguous_post_is_recovered_by_slug(tmp_path):
    recovered_post = WordPressPost(
        id=501,
        status="draft",
        link="https://example.test/?p=501",
        slug="eitaa-channel-181197-77",
        site_key="medical-site",
    )
    core = FakeCore(message(), tmp_path)
    wp = FakeWordPress(
        post_searches=[(), (), (recovered_post,)],
        create_error=WordPressAmbiguousWriteError("unknown"),
    )
    result = workflow(tmp_path, wp).execute(
        core, PEER, 77, site_key="medical-site"
    )
    assert result.outcome == "recovered_post"
    assert result.recovered is True
    assert core.publications.record.external_post_id == "501"


def test_deterministic_wordpress_error_marks_failed(tmp_path):
    core = FakeCore(message(), tmp_path)
    wp = FakeWordPress(
        post_searches=[(), ()],
        create_error=WordPressHttpError("bad request", code="wordpress_http_400"),
    )
    with pytest.raises(WordPressHttpError):
        workflow(tmp_path, wp).execute(
            core, PEER, 77, site_key="medical-site"
        )
    assert core.publications.record.status is PublicationStatus.FAILED
    assert core.publications.record.error_code == "wordpress_http_400"


def test_missing_local_message_is_typed(tmp_path):
    core = FakeCore(None, tmp_path)
    with pytest.raises(PublicationMessageNotFoundError):
        workflow(tmp_path, FakeWordPress()).preview(
            core, PEER, 77, site_key="medical-site"
        )


def test_real_core_publication_service_integration(tmp_path):
    import json
    from eitaa_core import EitaaCore, EitaaCoreConfig

    session_file = tmp_path / "session.json"
    session_file.write_text(
        json.dumps({"token": "t" * 30, "imei": "bridge_test__web", "dc": 2}),
        encoding="utf-8",
    )
    config = EitaaCoreConfig(
        session_file=session_file,
        database_file=tmp_path / "core.sqlite3",
        media_directory=tmp_path / "core-media",
        diagnostics_root=tmp_path / "core-diagnostics",
        diagnostics_enabled=False,
    )
    with EitaaCore.open(config) as core:
        core.messages.save((message(),))
        wp = FakeWordPress(post_searches=[(), ()])
        result = workflow(tmp_path, wp).execute(
            core, PEER, 77, site_key="medical-site"
        )
        stored = core.publications.get(
            PEER, 77, target_type="wordpress", target_key="medical-site"
        )
        assert result.outcome == "published"
        assert stored is not None
        assert stored.status is PublicationStatus.PUBLISHED
        assert stored.external_post_id == "500"



def remote_post(*, hash_prefix="bbbbbbbbbbbb", status="draft", post_id=500, title="عنوان پیام", content_text=None, featured_media_id=None):
    if content_text is None:
        content_text = "<p>عنوان پیام</p>\n<p>متن پیام</p>"
    content = (
        content_text
        + f"\n<!-- eitaa-bridge:medical-site:channel:181197:77:{hash_prefix} -->"
    )
    return WordPressPost(
        id=post_id,
        status=status,
        link=f"https://example.test/?p={post_id}",
        slug="eitaa-channel-181197-77",
        site_key="medical-site",
        featured_media_id=featured_media_id,
        title_raw=title,
        content_raw=content,
    )


def test_update_preview_reports_stale_draft_without_write(tmp_path):
    current = remote_post()
    core = FakeCore(
        message(), tmp_path,
        published_record(PublicationStatus.NEEDS_UPDATE, stale=True),
    )
    wp = FakeWordPress(get_posts=[current], post_searches=[(current,)])
    result = workflow(tmp_path, wp).update_preview(
        core, PEER, 77, site_key="medical-site"
    )
    assert result.action == "update_required"
    assert result.remote_matches_plan is False
    assert not any(call[0] == "update" for call in wp.calls)
    assert [call[0] for call in core.publications.calls] == ["get"]


def test_update_changes_same_draft_and_marks_published(tmp_path):
    old = remote_post()
    current = remote_post(hash_prefix="aaaaaaaaaaaa")
    core = FakeCore(
        message(), tmp_path,
        published_record(PublicationStatus.NEEDS_UPDATE, stale=True),
    )
    wp = FakeWordPress(
        get_posts=[old],
        post_searches=[(old,)],
        updated_post=current,
    )
    result = workflow(tmp_path, wp).update_execute(
        core, PEER, 77, site_key="medical-site"
    )
    assert result.outcome == "updated"
    update_calls = [call for call in wp.calls if call[0] == "update"]
    assert len(update_calls) == 1
    assert update_calls[0][1] == 500
    assert not any(call[0] == "create" for call in wp.calls)
    assert core.publications.record.status is PublicationStatus.PUBLISHED
    assert [call[0] for call in core.publications.calls] == ["get", "processing", "published"]


def test_update_preview_accepts_v03_slug_normalization_when_identity_marker_matches(tmp_path):
    legacy = replace(remote_post(), slug="wordpress-normalized-slug")
    core = FakeCore(
        message(), tmp_path,
        published_record(PublicationStatus.NEEDS_UPDATE, stale=True),
    )
    wp = FakeWordPress(get_posts=[legacy], post_searches=[()])
    result = workflow(tmp_path, wp).update_preview(
        core, PEER, 77, site_key="medical-site"
    )
    assert result.action == "update_required"
    assert result.post is not None and result.post.id == 500
    assert result.remote_matches_plan is False
    assert not any(call[0] == "update" for call in wp.calls)


def test_update_repairs_v03_slug_on_same_recorded_post(tmp_path):
    legacy = replace(remote_post(), slug="wordpress-normalized-slug")
    current = remote_post(hash_prefix="aaaaaaaaaaaa")
    core = FakeCore(
        message(), tmp_path,
        published_record(PublicationStatus.NEEDS_UPDATE, stale=True),
    )
    wp = FakeWordPress(
        get_posts=[legacy],
        post_searches=[()],
        updated_post=current,
    )
    result = workflow(tmp_path, wp).update_execute(
        core, PEER, 77, site_key="medical-site"
    )
    assert result.outcome == "updated"
    update_calls = [call for call in wp.calls if call[0] == "update"]
    assert len(update_calls) == 1
    assert update_calls[0][1] == 500
    assert update_calls[0][2]["slug"] == "eitaa-channel-181197-77"
    assert not any(call[0] == "create" for call in wp.calls)


def test_slug_mismatch_without_matching_bridge_identity_still_blocks(tmp_path):
    unrelated = replace(
        remote_post(),
        slug="unrelated-slug",
        content_raw="<p>Unrelated WordPress content</p>",
    )
    core = FakeCore(
        message(), tmp_path,
        published_record(PublicationStatus.NEEDS_UPDATE, stale=True),
    )
    wp = FakeWordPress(get_posts=[unrelated], post_searches=[()])
    with pytest.raises(PublicationCollisionError) as error:
        workflow(tmp_path, wp).update_preview(
            core, PEER, 77, site_key="medical-site"
        )
    assert error.value.code == "publication_post_identity_mismatch"
    assert not any(call[0] == "update" for call in wp.calls)


def test_slug_collision_with_another_post_still_blocks(tmp_path):
    legacy = replace(remote_post(), slug="wordpress-normalized-slug")
    other = replace(remote_post(post_id=501), slug="eitaa-channel-181197-77")
    core = FakeCore(
        message(), tmp_path,
        published_record(PublicationStatus.NEEDS_UPDATE, stale=True),
    )
    wp = FakeWordPress(get_posts=[legacy], post_searches=[(other,)])
    with pytest.raises(PublicationCollisionError) as error:
        workflow(tmp_path, wp).update_preview(
            core, PEER, 77, site_key="medical-site"
        )
    assert error.value.code == "publication_post_identity_collision"
    assert not any(call[0] == "update" for call in wp.calls)


def test_update_reconciles_when_remote_already_has_current_payload(tmp_path):
    current = remote_post(hash_prefix="aaaaaaaaaaaa")
    core = FakeCore(
        message(), tmp_path,
        published_record(PublicationStatus.NEEDS_UPDATE, stale=True),
    )
    wp = FakeWordPress(get_posts=[current], post_searches=[(current,)])
    result = workflow(tmp_path, wp).update_execute(
        core, PEER, 77, site_key="medical-site"
    )
    assert result.action == "reconciled_without_write"
    assert result.recovered is True
    assert not any(call[0] == "update" for call in wp.calls)
    assert core.publications.record.status is PublicationStatus.PUBLISHED


def test_live_post_update_is_blocked_without_explicit_flag(tmp_path):
    live = remote_post(status="publish")
    core = FakeCore(
        message(), tmp_path,
        published_record(PublicationStatus.NEEDS_UPDATE, stale=True),
    )
    wp = FakeWordPress(get_posts=[live], post_searches=[(live,)])
    with pytest.raises(PublicationBlockedError) as error:
        workflow(tmp_path, wp).update_execute(
            core, PEER, 77, site_key="medical-site"
        )
    assert error.value.code == "publication_live_update_blocked"
    assert not any(call[0] == "update" for call in wp.calls)


def test_remote_drift_is_blocked_when_core_message_is_unchanged(tmp_path):
    drift = remote_post(hash_prefix="aaaaaaaaaaaa", title="Manual title")
    core = FakeCore(message(), tmp_path, published_record())
    wp = FakeWordPress(get_posts=[drift], post_searches=[(drift,)])
    with pytest.raises(PublicationBlockedError) as error:
        workflow(tmp_path, wp).update_execute(
            core, PEER, 77, site_key="medical-site"
        )
    assert error.value.code == "publication_remote_drift"
    assert not any(call[0] == "update" for call in wp.calls)


def test_ambiguous_update_is_recovered_by_safe_get(tmp_path):
    old = remote_post()
    recovered = remote_post(hash_prefix="aaaaaaaaaaaa")
    core = FakeCore(
        message(), tmp_path,
        published_record(PublicationStatus.NEEDS_UPDATE, stale=True),
    )
    wp = FakeWordPress(
        get_posts=[old, recovered],
        post_searches=[(old,)],
        update_error=WordPressAmbiguousWriteError("unknown"),
    )
    result = workflow(tmp_path, wp).update_execute(
        core, PEER, 77, site_key="medical-site"
    )
    assert result.outcome == "recovered_update"
    assert result.recovered is True
    assert core.publications.record.status is PublicationStatus.PUBLISHED


def test_update_never_recreates_missing_remote_post(tmp_path):
    core = FakeCore(
        message(), tmp_path,
        published_record(PublicationStatus.NEEDS_UPDATE, stale=True),
    )
    missing = WordPressHttpError("missing", code="wordpress_http_404")
    wp = FakeWordPress(get_posts=[missing], post_searches=[()])
    with pytest.raises(PublicationBlockedError) as error:
        workflow(tmp_path, wp).update_execute(
            core, PEER, 77, site_key="medical-site"
        )
    assert error.value.code == "publication_remote_post_missing"
    assert not any(call[0] in {"create", "update"} for call in wp.calls)


def test_trashed_post_preview_is_separate_from_live_post(tmp_path):
    trashed = remote_post(status="trash")
    core = FakeCore(message(), tmp_path, published_record())
    wp = FakeWordPress(get_posts=[trashed], post_searches=[(trashed,)])

    result = workflow(tmp_path, wp).update_preview(
        core, PEER, 77, site_key="medical-site"
    )

    assert result.action == "blocked_trashed_post"
    assert result.live_update is False
    assert result.post is not None and result.post.status == "trash"
    assert not any(call[0] == "update" for call in wp.calls)


def test_trashed_post_update_requires_explicit_restore(tmp_path):
    trashed = remote_post(status="trash")
    core = FakeCore(message(), tmp_path, published_record())
    wp = FakeWordPress(get_posts=[trashed], post_searches=[(trashed,)])

    with pytest.raises(PublicationBlockedError) as error:
        workflow(tmp_path, wp).update_execute(
            core, PEER, 77, site_key="medical-site"
        )

    assert error.value.code == "publication_trashed_post_blocked"
    assert not any(call[0] == "update" for call in wp.calls)


def test_trashed_post_restore_preview_is_explicit_and_read_only(tmp_path):
    trashed = remote_post(status="trash")
    core = FakeCore(message(), tmp_path, published_record())
    wp = FakeWordPress(get_posts=[trashed], post_searches=[(trashed,)])

    result = workflow(tmp_path, wp).update_preview(
        core,
        PEER,
        77,
        site_key="medical-site",
        restore_trashed=True,
    )

    assert result.action == "restore_required"
    assert result.live_update is False
    assert not any(call[0] == "update" for call in wp.calls)


def test_explicit_restore_updates_same_trashed_post_as_draft(tmp_path):
    trashed = remote_post(status="trash")
    restored = remote_post(status="draft", hash_prefix="aaaaaaaaaaaa")
    core = FakeCore(message(), tmp_path, published_record())
    wp = FakeWordPress(
        get_posts=[trashed],
        post_searches=[(trashed,)],
        updated_post=restored,
    )

    result = workflow(tmp_path, wp).update_execute(
        core,
        PEER,
        77,
        site_key="medical-site",
        restore_trashed=True,
    )

    assert result.outcome == "restored_and_updated"
    assert result.action == "restored_existing_post"
    assert result.post is not None and result.post.id == 500
    assert result.post.status == "draft"
    update_calls = [call for call in wp.calls if call[0] == "update"]
    assert len(update_calls) == 1
    assert update_calls[0][1] == 500
    assert update_calls[0][2]["restore_to_draft"] is True
    assert not any(call[0] == "create" for call in wp.calls)
    assert core.publications.record.status is PublicationStatus.PUBLISHED
