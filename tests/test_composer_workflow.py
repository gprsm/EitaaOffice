from __future__ import annotations

import json
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
    save_peer_file,
)
from eitaa_bridge.application.workflows import ComposeMessagesToWordPress
from eitaa_bridge.domain import (
    CompositionRecord,
    CompositionSource,
    WordPressCompositionRequest,
    WordPressConnection,
    WordPressMedia,
    WordPressPost,
    WordPressSiteInfo,
)
from eitaa_bridge.errors import CompositionBlockedError, CompositionCollisionError, CompositionValidationError
from eitaa_bridge.infrastructure.composition_manifest import CompositionManifestLoader
from eitaa_bridge.infrastructure.composition_store import JsonCompositionStore
from eitaa_bridge.infrastructure.diagnostics import BridgeDiagnosticManager


PEER = Peer(id=14394054, type=PeerType.CHANNEL, access_hash=987654321)


def msg(mid: int, text: str, media=None) -> Message:
    return Message(
        id=mid,
        peer=PEER,
        date=datetime(2026, 7, 17, tzinfo=timezone.utc),
        text=text,
        media=media,
    )


class Messages:
    def __init__(self, items):
        self.items = {(item.peer.type.value, item.peer.id, item.id): item for item in items}

    def get(self, peer, message_id):
        return self.items.get((peer.type.value, peer.id, message_id))

    def content_hash(self, peer, message_id):
        item = self.get(peer, message_id)
        return f"{message_id:064x}" if item else None


class Publications:
    def __init__(self):
        self.records = {}

    def _key(self, peer, message_id, target_type, target_key):
        return (peer.type.value, peer.id, message_id, target_type, target_key)

    def get(self, peer, message_id, *, target_type, target_key):
        return self.records.get(self._key(peer, message_id, target_type, target_key))

    def _save(self, peer, message_id, status, target_type, target_key, **changes):
        key = self._key(peer, message_id, target_type, target_key)
        old = self.records.get(key)
        record = PublicationRecord(
            peer=peer,
            message_id=message_id,
            target_type=target_type,
            target_key=target_key,
            status=status,
            external_post_id=changes.get("external_post_id", old.external_post_id if old else None),
            external_url=changes.get("external_url", old.external_url if old else None),
            published_content_hash=changes.get("published_content_hash", old.published_content_hash if old else None),
            attempts=(old.attempts if old else 0),
            current_content_hash=f"{message_id:064x}",
        )
        self.records[key] = record
        return record

    def mark_pending(self, peer, message_id, *, target_type, target_key):
        return self._save(peer, message_id, PublicationStatus.PENDING, target_type, target_key)

    def mark_processing(self, peer, message_id, *, target_type, target_key):
        return self._save(peer, message_id, PublicationStatus.PROCESSING, target_type, target_key)

    def mark_published(self, peer, message_id, *, external_post_id, external_url, target_type, target_key):
        return self._save(
            peer,
            message_id,
            PublicationStatus.PUBLISHED,
            target_type,
            target_key,
            external_post_id=external_post_id,
            external_url=external_url,
            published_content_hash=f"{message_id:064x}",
        )


class MediaDownloader:
    def __init__(self, root: Path):
        self.root = root
        self.calls = []

    def download(self, media, options):
        self.calls.append((media, options))
        path = Path(options.output_directory) / f"{options.file_name}.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"image")
        return SimpleNamespace(path=path)


class Core:
    def __init__(self, items, root):
        self.messages = Messages(items)
        self.publications = Publications()
        self.media = MediaDownloader(root)


class WordPress:
    def __init__(self, *, can_publish=True):
        self.posts_by_slug = {}
        self.posts_by_id = {}
        self.media_by_slug = {}
        self.calls = []
        self.next_media = 900
        self.can_publish = can_publish

    def find_posts_by_slug(self, slug):
        self.calls.append(("find_post", slug))
        value = self.posts_by_slug.get(slug)
        return (value,) if value else ()

    def get_post(self, post_id):
        self.calls.append(("get_post", post_id))
        return self.posts_by_id[post_id]

    def find_media_by_slug(self, slug):
        self.calls.append(("find_media", slug))
        value = self.media_by_slug.get(slug)
        return (value,) if value else ()

    def upload_media(self, path, **kwargs):
        self.calls.append(("upload_media", Path(path), kwargs))
        media = WordPressMedia(
            id=self.next_media,
            status="inherit",
            media_type="image",
            mime_type=kwargs.get("mime_type") or "image/jpeg",
            source_url=f"https://example.test/uploads/{self.next_media}.jpg",
            slug=kwargs["slug"],
            site_key="medical-site",
        )
        self.next_media += 1
        self.media_by_slug[media.slug] = media
        return media

    def test_connection(self):
        return WordPressConnection(
            site_key="medical-site",
            authenticated=True,
            user_id=1,
            can_edit_posts=True,
            can_publish_posts=self.can_publish,
            can_upload_files=True,
            site=WordPressSiteInfo(name="Test", url="https://example.test"),
        )

    def create_post(self, **kwargs):
        self.calls.append(("create_post", kwargs))
        post = WordPressPost(
            id=597,
            status=kwargs["status"],
            link="https://example.test/?p=597",
            slug=kwargs["slug"],
            site_key="medical-site",
            featured_media_id=kwargs.get("featured_media_id"),
            title_raw=kwargs["title"],
            content_raw=kwargs["content"],
            excerpt_raw=kwargs.get("excerpt"),
            category_ids=tuple(kwargs.get("category_ids") or ()),
            tag_ids=tuple(kwargs.get("tag_ids") or ()),
        )
        self.posts_by_slug[post.slug] = post
        self.posts_by_id[post.id] = post
        return post

    def update_post(self, post_id, **kwargs):
        self.calls.append(("update_post", post_id, kwargs))
        old = self.posts_by_id[post_id]
        post = WordPressPost(
            id=post_id,
            status=kwargs.get("status") or old.status,
            link=old.link,
            slug=kwargs.get("slug") or old.slug,
            site_key="medical-site",
            featured_media_id=kwargs.get("featured_media_id"),
            title_raw=kwargs.get("title") or old.title_raw,
            content_raw=kwargs.get("content") or old.content_raw,
            excerpt_raw=kwargs.get("excerpt"),
            category_ids=tuple(kwargs.get("category_ids") or ()),
            tag_ids=tuple(kwargs.get("tag_ids") or ()),
        )
        self.posts_by_slug[post.slug] = post
        self.posts_by_id[post.id] = post
        return post

    def create_text_draft(self, **kwargs):
        self.calls.append(("create", kwargs))
        post = WordPressPost(
            id=596,
            status="draft",
            link="https://example.test/?p=596",
            slug=kwargs["slug"],
            site_key="medical-site",
            featured_media_id=kwargs.get("featured_media_id"),
            title_raw=kwargs["title"],
            content_raw=kwargs["content"],
            excerpt_raw=kwargs.get("excerpt"),
            category_ids=tuple(kwargs.get("category_ids") or ()),
            tag_ids=tuple(kwargs.get("tag_ids") or ()),
        )
        self.posts_by_slug[post.slug] = post
        self.posts_by_id[post.id] = post
        return post


def request(*, featured=0, key="roundup-1"):
    return WordPressCompositionRequest(
        composition_key=key,
        site_key="medical-site",
        title="عنوان ترکیبی",
        excerpt="چکیده دستی",
        sources=(
            CompositionSource(peer=PEER, message_id=11795),
            CompositionSource(peer=PEER, message_id=11817),
        ),
        category_ids=(12, 15),
        tag_ids=(4, 9),
        featured_source_index=featured,
        include_featured_in_body=True,
    )


def workflow(tmp_path, wp=None):
    return ComposeMessagesToWordPress(
        wp or WordPress(),
        BridgeDiagnosticManager(tmp_path / "diagnostics"),
        tmp_path / "media",
        JsonCompositionStore(tmp_path / "state" / "compositions.json"),
    )


def messages():
    photo = MediaReference(
        type=MediaType.PHOTO,
        remote_id=777,
        access_hash=1,
        file_reference=b"ref",
        mime_type="image/jpeg",
    )
    return (
        msg(11795, "متن اول", photo),
        msg(11817, "متن دوم"),
    )


def test_preview_preserves_non_contiguous_source_order(tmp_path):
    core = Core(messages(), tmp_path)
    result = workflow(tmp_path).preview(core, request())
    assert result.outcome == "composition_preview"
    assert [item.source.message_id for item in result.plan.sources] == [11795, 11817]
    assert result.plan.blocked_source_count == 0
    assert result.plan.request.category_ids == (12, 15)
    assert result.plan.request.tag_ids == (4, 9)


def test_publish_creates_one_draft_and_links_all_sources(tmp_path):
    core = Core(messages(), tmp_path)
    wp = WordPress()
    result = workflow(tmp_path, wp).execute(core, request())

    assert result.outcome == "composition_created"
    assert result.post.id == 596
    assert result.post.featured_media_id == 900
    assert len(result.publications) == 2
    assert {item.external_post_id for item in result.publications} == {"596"}
    create = next(call for call in wp.calls if call[0] == "create")[1]
    assert create["category_ids"] == (12, 15)
    assert create["tag_ids"] == (4, 9)
    assert create["excerpt"] == "چکیده دستی"
    assert create["content"].index("متن اول") < create["content"].index("متن دوم")
    assert create["content"].index("wp-block-image") < create["content"].index("متن اول")
    assert result.record.source_keys == (
        "channel:14394054:11795",
        "channel:14394054:11817",
    )


def test_publish_blocks_message_already_used_in_another_post(tmp_path):
    core = Core(messages(), tmp_path)
    core.publications.mark_published(
        PEER,
        11795,
        external_post_id="321",
        external_url="https://example.test/?p=321",
        target_type="wordpress",
        target_key="medical-site",
    )
    with pytest.raises(CompositionBlockedError) as error:
        workflow(tmp_path).execute(core, request())
    assert error.value.code == "composition_source_already_used"


def test_existing_matching_post_recovers_before_duplicate_block(tmp_path):
    core = Core(messages(), tmp_path)
    wp = WordPress()
    flow = workflow(tmp_path, wp)
    first = flow.execute(core, request())
    state = tmp_path / "state" / "compositions.json"
    state.unlink()

    second = flow.execute(core, request())
    assert first.post.id == second.post.id == 596
    assert second.outcome == "composition_recovered_post"
    assert second.recovered is True
    assert len([call for call in wp.calls if call[0] == "create"]) == 1


def test_featured_source_must_be_an_image(tmp_path):
    core = Core(messages(), tmp_path)
    bad = request(featured=1)
    with pytest.raises(CompositionValidationError) as error:
        workflow(tmp_path).preview(core, bad)
    assert error.value.code == "composition_featured_source_not_image"


def test_composition_key_cannot_be_reused_for_different_sources(tmp_path):
    core = Core(messages() + (msg(11900, "متن سوم"),), tmp_path)
    wp = WordPress()
    flow = workflow(tmp_path, wp)
    flow.execute(core, request())
    changed = WordPressCompositionRequest(
        composition_key="roundup-1",
        site_key="medical-site",
        title="عنوان ترکیبی",
        excerpt="",
        sources=(CompositionSource(peer=PEER, message_id=11900),),
    )
    with pytest.raises(CompositionCollisionError) as error:
        flow.execute(core, changed)
    assert error.value.code == "composition_key_reused"


def test_message_usage_reports_composition_relation(tmp_path):
    core = Core(messages(), tmp_path)
    flow = workflow(tmp_path)
    flow.execute(core, request())
    usage = flow.message_usage(core, site_key="medical-site", peer=PEER, message_id=11795)
    assert usage["used"] is True
    assert usage["composition_count"] == 1
    assert usage["compositions"][0]["post_id"] == 596


def test_manifest_resolves_relative_peer_files(tmp_path):
    peer_file = tmp_path / "selected_private_channel.json"
    save_peer_file(peer_file, PEER)
    manifest = tmp_path / "composition.json"
    manifest.write_text(
        json.dumps(
            {
                "composition_key": "daily-roundup",
                "site_key": "medical-site",
                "title": "عنوان",
                "excerpt": "چکیده",
                "category_ids": [12],
                "tag_ids": [4, 9],
                "featured_source_index": 0,
                "sources": [
                    {"peer_file": "selected_private_channel.json", "message_id": 11795},
                    {"peer_file": "selected_private_channel.json", "message_id": 11817},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    loaded = CompositionManifestLoader.load(manifest, default_site_key="default")
    assert loaded.site_key == "medical-site"
    assert loaded.sources[0].peer_file == peer_file
    assert [item.message_id for item in loaded.sources] == [11795, 11817]


def test_json_store_preserves_created_at_and_finds_source(tmp_path):
    store = JsonCompositionStore(tmp_path / "state.json")
    now = datetime.now(timezone.utc)
    record = CompositionRecord(
        composition_key="one",
        site_key="medical-site",
        post_id=1,
        post_url=None,
        post_slug="one",
        status="draft",
        title="t",
        excerpt="",
        category_ids=(),
        tag_ids=(),
        source_keys=("channel:1:2",),
        source_hashes=("a" * 64,),
        featured_source_key=None,
        featured_media_id=None,
        created_at=now,
        updated_at=now,
    )
    first = store.save(record)
    second = store.save(record)
    assert second.created_at == first.created_at
    assert store.get("medical-site", "one").post_id == 1
    assert store.find_by_source("medical-site", "channel:1:2")[0].composition_key == "one"


def test_publish_status_requires_explicit_confirmation():
    selected = request()
    published = WordPressCompositionRequest(
        composition_key=selected.composition_key,
        site_key=selected.site_key,
        title=selected.title,
        excerpt=selected.excerpt,
        sources=selected.sources,
        category_ids=selected.category_ids,
        tag_ids=selected.tag_ids,
        featured_source_index=selected.featured_source_index,
        post_status="publish",
        confirm_publish=False,
    )
    with pytest.raises(ValueError, match="confirm_publish"):
        published.validate()


def test_publish_status_creates_live_post_after_permission_check(tmp_path):
    core = Core(messages(), tmp_path)
    wp = WordPress(can_publish=True)
    selected = request(key="roundup-publish")
    published = WordPressCompositionRequest(
        composition_key=selected.composition_key,
        site_key=selected.site_key,
        title=selected.title,
        excerpt=selected.excerpt,
        sources=selected.sources,
        category_ids=selected.category_ids,
        tag_ids=selected.tag_ids,
        featured_source_index=selected.featured_source_index,
        post_status="publish",
        confirm_publish=True,
    )
    result = workflow(tmp_path, wp).execute(core, published)
    assert result.post.status == "publish"
    call = next(item for item in wp.calls if item[0] == "create_post")
    assert call[1]["status"] == "publish"


def test_publish_status_blocks_account_without_permission(tmp_path):
    core = Core(messages(), tmp_path)
    selected = request(key="roundup-publish-blocked")
    published = WordPressCompositionRequest(
        composition_key=selected.composition_key,
        site_key=selected.site_key,
        title=selected.title,
        excerpt=selected.excerpt,
        sources=selected.sources,
        featured_source_index=selected.featured_source_index,
        post_status="publish",
        confirm_publish=True,
    )
    with pytest.raises(CompositionBlockedError) as error:
        workflow(tmp_path, WordPress(can_publish=False)).execute(core, published)
    assert error.value.code == "composition_publish_permission_missing"


def test_update_changes_same_post_without_creating_replacement(tmp_path):
    core = Core(messages(), tmp_path)
    wp = WordPress()
    flow = workflow(tmp_path, wp)
    first = flow.execute(core, request())
    changed = WordPressCompositionRequest(
        composition_key="roundup-1",
        site_key="medical-site",
        title="عنوان اصلاح‌شده",
        excerpt="چکیده اصلاح‌شده",
        sources=(
            CompositionSource(peer=PEER, message_id=11817),
            CompositionSource(peer=PEER, message_id=11795),
        ),
        category_ids=(15,),
        tag_ids=(9, 11),
        featured_source_index=1,
        include_featured_in_body=True,
        post_status="draft",
    )
    result = flow.update(core, changed)
    assert result.outcome == "composition_updated"
    assert result.post.id == first.post.id == 596
    assert result.record.created_at == first.record.created_at
    assert result.record.source_keys == ("channel:14394054:11817", "channel:14394054:11795")
    assert len([call for call in wp.calls if call[0] == "create"]) == 1
    update_call = next(call for call in wp.calls if call[0] == "update_post")
    assert update_call[1] == 596
    assert update_call[2]["title"] == "عنوان اصلاح‌شده"
    assert update_call[2]["category_ids"] == (15,)
    assert update_call[2]["tag_ids"] == (9, 11)


def test_update_allows_appending_new_sources_to_same_post(tmp_path):
    core = Core(messages() + (msg(11900, "متن سوم"),), tmp_path)
    wp = WordPress()
    flow = workflow(tmp_path, wp)
    first = flow.execute(core, request())
    changed = WordPressCompositionRequest(
        composition_key="roundup-1",
        site_key="medical-site",
        title="عنوان تکمیل‌شده",
        excerpt="",
        sources=(
            CompositionSource(peer=PEER, message_id=11795),
            CompositionSource(peer=PEER, message_id=11817),
            CompositionSource(peer=PEER, message_id=11900),
        ),
    )

    result = flow.update(core, changed)

    assert result.outcome == "composition_updated"
    assert result.post.id == first.post.id == 596
    assert result.record.source_keys == (
        "channel:14394054:11795",
        "channel:14394054:11817",
        "channel:14394054:11900",
    )
    assert {item.external_post_id for item in result.publications} == {"596"}
    update_call = next(call for call in wp.calls if call[0] == "update_post")
    assert "متن سوم" in update_call[2]["content"]



def test_appended_source_remains_used_when_publication_row_is_temporarily_unavailable(tmp_path):
    core = Core(messages() + (msg(11900, "متن سوم"),), tmp_path)
    wp = WordPress()
    flow = workflow(tmp_path, wp)
    flow.execute(core, request())
    changed = WordPressCompositionRequest(
        composition_key="roundup-1",
        site_key="medical-site",
        title="عنوان تکمیل‌شده",
        excerpt="",
        sources=(
            CompositionSource(peer=PEER, message_id=11795),
            CompositionSource(peer=PEER, message_id=11817),
            CompositionSource(peer=PEER, message_id=11900),
        ),
    )
    flow.update(core, changed)

    publication_key = core.publications._key(PEER, 11900, "wordpress", "medical-site")
    del core.publications.records[publication_key]

    usage = flow.message_usage(core, site_key="medical-site", peer=PEER, message_id=11900)
    assert usage["used"] is True
    assert usage["external_post_id"] == "596"

    duplicate = WordPressCompositionRequest(
        composition_key="roundup-2",
        site_key="medical-site",
        title="مطلب دیگر",
        excerpt="",
        sources=(CompositionSource(peer=PEER, message_id=11900),),
    )
    preview = flow.preview(core, duplicate)
    assert preview.plan.blocked_source_count == 1
    with pytest.raises(CompositionBlockedError) as error:
        flow.execute(core, duplicate)
    assert error.value.code == "composition_source_already_used"

def test_update_blocks_removing_or_replacing_recorded_sources(tmp_path):
    core = Core(messages() + (msg(11900, "متن سوم"),), tmp_path)
    wp = WordPress()
    flow = workflow(tmp_path, wp)
    flow.execute(core, request())
    changed = WordPressCompositionRequest(
        composition_key="roundup-1",
        site_key="medical-site",
        title="عنوان",
        excerpt="",
        sources=(
            CompositionSource(peer=PEER, message_id=11817),
            CompositionSource(peer=PEER, message_id=11900),
        ),
    )
    with pytest.raises(CompositionCollisionError) as error:
        flow.update(core, changed)
    assert error.value.code == "composition_update_source_removal_blocked"


def test_success_summary_confirms_every_committed_source_key(tmp_path):
    core = Core(messages() + (msg(11900, "متن سوم"),), tmp_path)
    wp = WordPress()
    flow = workflow(tmp_path, wp)
    first = flow.execute(core, request())
    changed = WordPressCompositionRequest(
        composition_key="roundup-1",
        site_key="medical-site",
        title="عنوان تکمیل‌شده",
        excerpt="",
        sources=(
            CompositionSource(peer=PEER, message_id=11795),
            CompositionSource(peer=PEER, message_id=11817),
            CompositionSource(peer=PEER, message_id=11900),
        ),
    )

    result = flow.update(core, changed)
    summary = result.safe_summary()

    assert result.post.id == first.post.id == 596
    assert summary["confirmed_source_keys"] == [
        "channel:14394054:11795",
        "channel:14394054:11817",
        "channel:14394054:11900",
    ]
    for source_key in summary["confirmed_source_keys"]:
        matches = flow.store.find_by_source("medical-site", source_key)
        assert any(item.post_id == 596 and item.composition_key == "roundup-1" for item in matches)
