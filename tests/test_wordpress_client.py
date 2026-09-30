from __future__ import annotations

import json

import pytest
import requests

from eitaa_bridge.errors import (
    WordPressAmbiguousWriteError,
    WordPressAuthenticationError,
    WordPressConnectionError,
    WordPressHttpError,
    WordPressResponseError,
)
from eitaa_bridge.infrastructure.config import BridgeConfigLoader
from eitaa_bridge.infrastructure.diagnostics import BridgeDiagnosticManager
from eitaa_bridge.infrastructure.wordpress import WordPressClient, WordPressCredentials
from conftest import FakeResponse, FakeSession


def client(config_file, responses, tmp_path, sleep=lambda _: None):
    site = BridgeConfigLoader.load(config_file).site()
    diagnostics = BridgeDiagnosticManager(tmp_path / "diagnostics")
    session = FakeSession(responses)
    return WordPressClient(
        site,
        WordPressCredentials("editor", "secret app password"),
        diagnostics=diagnostics,
        session=session,
        sleep=sleep,
    ), session, diagnostics


def site_payload():
    return {
        "name": "Medical",
        "url": "https://example.test",
        "home": "https://example.test",
        "namespaces": ["wp/v2"],
    }


def test_get_site_info(config_file, tmp_path):
    wp, session, _ = client(config_file, [FakeResponse(200, site_payload())], tmp_path)
    result = wp.get_site_info()
    assert result.name == "Medical"
    assert session.calls[0][2]["auth"] is None


def test_connection_uses_auth_and_permissions(config_file, tmp_path):
    responses = [
        FakeResponse(200, site_payload()),
        FakeResponse(200, {"id": 7, "capabilities": {"edit_posts": True, "publish_posts": False}}),
    ]
    wp, session, _ = client(config_file, responses, tmp_path)
    result = wp.test_connection()
    assert result.authenticated
    assert result.can_edit_posts
    assert session.calls[1][2]["auth"] is not None


def test_create_draft_sends_only_draft_status(config_file, tmp_path):
    wp, session, diagnostics = client(
        config_file,
        [FakeResponse(201, {"id": 123, "status": "draft", "link": "https://example.test/?p=123", "slug": "test"})],
        tmp_path,
    )
    result = wp.create_text_draft(title="Private title", content="Private body")
    assert result.id == 123
    payload = session.calls[0][2]["json"]
    assert payload["status"] == "draft"
    assert payload["categories"] == [12]
    log = diagnostics.file_for("wordpress").read_text(encoding="utf-8")
    assert "Private title" not in log
    assert "Private body" not in log


def test_blank_draft_is_rejected(config_file, tmp_path):
    wp, _, _ = client(config_file, [], tmp_path)
    with pytest.raises(WordPressResponseError):
        wp.create_text_draft(title="", content="body")


def test_401_is_authentication_error(config_file, tmp_path):
    wp, _, _ = client(config_file, [FakeResponse(401, {"code": "rest_not_logged_in"})], tmp_path)
    with pytest.raises(WordPressAuthenticationError) as error:
        wp.create_text_draft(title="t", content="c")
    assert error.value.code == "wordpress_http_401"


def test_400_with_forbidden_status_detail_is_authentication_error(config_file, tmp_path):
    response_payload = {
        "code": "rest_invalid_param",
        "message": "Invalid parameter(s): status",
        "data": {
            "status": 400,
            "params": {"status": "Status is forbidden."},
            "details": {
                "status": {
                    "code": "rest_forbidden_status",
                    "message": "Status is forbidden.",
                    "data": {"status": 401},
                }
            },
        },
    }
    wp, _, _ = client(config_file, [FakeResponse(400, response_payload)], tmp_path)
    with pytest.raises(WordPressAuthenticationError) as error:
        wp.find_posts_by_slug("eitaa-test-post")
    assert error.value.code == "wordpress_http_401"
    assert error.value.safe_context["status"] == 401
    assert error.value.safe_context["wordpress_error_code"] == "rest_invalid_param"
    assert error.value.safe_context["rejected_fields"] == ["status"]


def test_non_transient_http_error_is_safe(config_file, tmp_path):
    wp, _, diagnostics = client(
        config_file,
        [FakeResponse(400, {"code": "rest_invalid_param", "message": "sensitive body"})],
        tmp_path,
    )
    with pytest.raises(WordPressHttpError) as error:
        wp.create_text_draft(title="t", content="c")
    assert error.value.safe_context["wordpress_error_code"] == "rest_invalid_param"
    assert "sensitive body" not in diagnostics.file_for("wordpress").read_text(encoding="utf-8")


def test_safe_get_transient_error_retries(config_file, tmp_path):
    delays = []
    wp, session, _ = client(
        config_file,
        [FakeResponse(503, {"code": "unavailable"}), FakeResponse(200, site_payload())],
        tmp_path,
        sleep=delays.append,
    )
    result = wp.get_site_info()
    assert result.name == "Medical"
    assert len(session.calls) == 2
    assert delays == [0.5]


def test_safe_get_network_error_retries_then_fails(config_file, tmp_path):
    wp, session, _ = client(
        config_file,
        [requests.ConnectionError("secret endpoint detail"), requests.ConnectionError("again")],
        tmp_path,
    )
    with pytest.raises(WordPressConnectionError):
        wp.get_site_info()
    assert len(session.calls) == 2


def test_post_transient_status_is_not_retried(config_file, tmp_path):
    wp, session, diagnostics = client(
        config_file,
        [FakeResponse(503, {"code": "unavailable"}), FakeResponse(201, {"id": 9, "status": "draft"})],
        tmp_path,
    )
    with pytest.raises(WordPressAmbiguousWriteError) as error:
        wp.create_text_draft(title="t", content="c")
    assert len(session.calls) == 1
    assert error.value.safe_context["outcome"] == "unknown"
    assert error.value.safe_context["automatic_retry"] is False
    assert "write_outcome_ambiguous" in diagnostics.file_for("wordpress").read_text(encoding="utf-8")


def test_post_network_error_is_not_retried(config_file, tmp_path):
    wp, session, _ = client(
        config_file,
        [requests.ConnectionError("response lost"), FakeResponse(201, {"id": 9, "status": "draft"})],
        tmp_path,
    )
    with pytest.raises(WordPressAmbiguousWriteError):
        wp.create_text_draft(title="t", content="c")
    assert len(session.calls) == 1


def test_post_success_with_non_json_response_is_ambiguous(config_file, tmp_path):
    wp, session, _ = client(config_file, [FakeResponse(201, json_error=ValueError("html"))], tmp_path)
    with pytest.raises(WordPressAmbiguousWriteError):
        wp.create_text_draft(title="t", content="c")
    assert len(session.calls) == 1


def test_post_success_without_post_identity_is_ambiguous(config_file, tmp_path):
    wp, session, _ = client(config_file, [FakeResponse(201, {"status": "draft"})], tmp_path)
    with pytest.raises(WordPressAmbiguousWriteError):
        wp.create_text_draft(title="t", content="c")
    assert len(session.calls) == 1


def test_non_json_get_success_is_rejected(config_file, tmp_path):
    wp, _, _ = client(config_file, [FakeResponse(200, json_error=ValueError("html"))], tmp_path)
    with pytest.raises(WordPressResponseError):
        wp.get_site_info()


def media_payload(media_id=88):
    return {
        "id": media_id,
        "status": "inherit",
        "media_type": "image",
        "mime_type": "image/jpeg",
        "source_url": f"https://example.test/uploads/{media_id}.jpg",
        "slug": f"media-{media_id}",
        "post": 0,
    }


def test_connection_reports_upload_permission(config_file, tmp_path):
    responses = [
        FakeResponse(200, site_payload()),
        FakeResponse(200, {"id": 7, "capabilities": {"edit_posts": True, "upload_files": True}}),
    ]
    wp, _, _ = client(config_file, responses, tmp_path)
    assert wp.test_connection().can_upload_files is True


def test_upload_media_uses_single_multipart_post(config_file, tmp_path):
    local_file = tmp_path / "sample.jpg"
    local_file.write_bytes(b"jpeg-data")
    wp, session, diagnostics = client(config_file, [FakeResponse(201, media_payload())], tmp_path)

    result = wp.upload_media(
        local_file,
        title="Private media title",
        caption="Private media caption",
        alt_text="Private media alt",
    )

    assert result.id == 88
    assert result.is_image is True
    assert len(session.calls) == 1
    method, url, kwargs = session.calls[0]
    assert method == "POST"
    assert url == "https://example.test/wp-json/wp/v2/media"
    assert "json" not in kwargs
    assert kwargs["data"]["title"] == "Private media title"
    filename, handle, mime_type = kwargs["files"]["file"]
    assert filename == "sample.jpg"
    assert mime_type == "image/jpeg"
    assert handle.closed is True
    log = diagnostics.file_for("wordpress").read_text(encoding="utf-8")
    assert "Private media title" not in log
    assert "Private media caption" not in log
    assert "Private media alt" not in log
    assert "jpeg-data" not in log


def test_upload_media_accepts_explicit_mime_type(config_file, tmp_path):
    local_file = tmp_path / "sample.unknown"
    local_file.write_bytes(b"data")
    wp, session, _ = client(config_file, [FakeResponse(201, {
        **media_payload(), "media_type": "file", "mime_type": "application/pdf"
    })], tmp_path)
    result = wp.upload_media(local_file, mime_type="application/pdf")
    assert result.mime_type == "application/pdf"
    assert session.calls[0][2]["files"]["file"][2] == "application/pdf"


def test_upload_media_unknown_mime_is_rejected_before_network(config_file, tmp_path):
    from eitaa_bridge.errors import MediaFileError

    local_file = tmp_path / "sample.unknown-extension"
    local_file.write_bytes(b"data")
    wp, session, _ = client(config_file, [], tmp_path)
    with pytest.raises(MediaFileError):
        wp.upload_media(local_file)
    assert session.calls == []


def test_upload_media_missing_file_is_typed(config_file, tmp_path):
    from eitaa_bridge.errors import MediaFileError

    wp, session, _ = client(config_file, [], tmp_path)
    with pytest.raises(MediaFileError):
        wp.upload_media(tmp_path / "missing.jpg")
    assert session.calls == []


def test_upload_media_transient_status_is_not_retried(config_file, tmp_path):
    local_file = tmp_path / "sample.jpg"
    local_file.write_bytes(b"data")
    wp, session, _ = client(
        config_file,
        [FakeResponse(503, {"code": "unavailable"}), FakeResponse(201, media_payload())],
        tmp_path,
    )
    with pytest.raises(WordPressAmbiguousWriteError):
        wp.upload_media(local_file)
    assert len(session.calls) == 1


def test_upload_success_without_media_identity_is_ambiguous(config_file, tmp_path):
    local_file = tmp_path / "sample.jpg"
    local_file.write_bytes(b"data")
    wp, _, _ = client(config_file, [FakeResponse(201, {"status": "inherit"})], tmp_path)
    with pytest.raises(WordPressAmbiguousWriteError):
        wp.upload_media(local_file)


def test_get_media_is_safe_get(config_file, tmp_path):
    wp, session, _ = client(config_file, [FakeResponse(200, media_payload(91))], tmp_path)
    result = wp.get_media(91)
    assert result.id == 91
    assert session.calls[0][0] == "GET"
    assert session.calls[0][1].endswith("/wp-json/wp/v2/media/91?context=edit")


def test_draft_can_set_existing_featured_media(config_file, tmp_path):
    wp, session, _ = client(
        config_file,
        [FakeResponse(201, {"id": 123, "status": "draft", "featured_media": 88})],
        tmp_path,
    )
    result = wp.create_text_draft(title="t", content="c", featured_media_id=88)
    assert session.calls[0][2]["json"]["featured_media"] == 88
    assert result.featured_media_id == 88


def test_find_posts_by_slug_uses_authenticated_safe_collection_get(config_file, tmp_path):
    payload = [{
        "id": 301,
        "status": "draft",
        "link": "https://example.test/?p=301",
        "slug": "eitaa-channel-1-2",
        "featured_media": 0,
    }]
    wp, session, _ = client(config_file, [FakeResponse(200, payload)], tmp_path)
    posts = wp.find_posts_by_slug("eitaa-channel-1-2")
    assert len(posts) == 1
    assert posts[0].id == 301
    method, url, kwargs = session.calls[0]
    assert method == "GET"
    assert "slug=eitaa-channel-1-2" in url
    assert "status=any" in url
    assert kwargs["auth"] is not None


def test_find_media_by_slug_uses_collection_get(config_file, tmp_path):
    wp, session, _ = client(
        config_file,
        [FakeResponse(200, [{**media_payload(302), "slug": "eitaa-media"}])],
        tmp_path,
    )
    items = wp.find_media_by_slug("eitaa-media")
    assert len(items) == 1
    assert items[0].id == 302
    assert "slug=eitaa-media" in session.calls[0][1]


def test_upload_media_can_send_deterministic_slug(config_file, tmp_path):
    local_file = tmp_path / "sample.jpg"
    local_file.write_bytes(b"jpeg-data")
    wp, session, _ = client(config_file, [FakeResponse(201, media_payload())], tmp_path)
    wp.upload_media(local_file, slug="eitaa-channel-1-2-media")
    assert session.calls[0][2]["data"]["slug"] == "eitaa-channel-1-2-media"


def test_update_post_preserves_remote_status_and_can_clear_featured_media(config_file, tmp_path):
    response = {
        "id": 123,
        "status": "draft",
        "link": "https://example.test/?p=123",
        "slug": "eitaa-channel-1-2",
        "featured_media": 0,
        "title": {"raw": "Updated title"},
        "content": {"raw": "Updated content"},
        "categories": [12],
        "modified_gmt": "2026-07-17T06:00:00",
    }
    wp, session, _ = client(config_file, [FakeResponse(200, response)], tmp_path)
    result = wp.update_post(
        123,
        title="Updated title",
        content="Updated content",
        slug="eitaa-channel-1-2",
        featured_media_id=None,
    )
    method, url, kwargs = session.calls[0]
    assert method == "POST"
    assert url.endswith("/wp-json/wp/v2/posts/123")
    assert "status" not in kwargs["json"]
    assert kwargs["json"]["featured_media"] == 0
    assert kwargs["json"]["categories"] == [12]
    assert result.title_raw == "Updated title"
    assert result.content_raw == "Updated content"
    assert result.category_ids == (12,)


def test_update_post_network_error_is_ambiguous_and_not_retried(config_file, tmp_path):
    wp, session, _ = client(
        config_file,
        [requests.ConnectionError("lost response"), FakeResponse(200, {"id": 123, "status": "draft"})],
        tmp_path,
    )
    with pytest.raises(WordPressAmbiguousWriteError):
        wp.update_post(123, title="t", content="c")
    assert len(session.calls) == 1


def test_update_post_can_explicitly_restore_trash_to_draft(config_file, tmp_path):
    payload = {
        "id": 596,
        "status": "draft",
        "link": "https://example.test/?p=596",
        "slug": "eitaa-channel-14394054-11795",
        "featured_media": 595,
        "title": {"raw": "Restored title"},
        "content": {"raw": "Restored content"},
        "categories": [12],
    }
    wp, session, _ = client(config_file, [FakeResponse(200, payload)], tmp_path)

    result = wp.update_post(
        596,
        title="Restored title",
        content="Restored content",
        slug="eitaa-channel-14394054-11795",
        featured_media_id=595,
        restore_to_draft=True,
    )

    assert result.id == 596
    assert result.status == "draft"
    request_payload = session.calls[0][2]["json"]
    assert request_payload["status"] == "draft"
    assert request_payload["featured_media"] == 595


def test_create_post_can_request_publish_status(config_file, tmp_path):
    wp, session, _ = client(
        config_file,
        [FakeResponse(201, {
            "id": 124,
            "status": "publish",
            "link": "https://example.test/?p=124",
            "slug": "published-post",
        })],
        tmp_path,
    )
    result = wp.create_post(title="Published", content="Body", status="publish")
    assert result.status == "publish"
    assert session.calls[0][2]["json"]["status"] == "publish"


def test_create_post_rejects_unsupported_status(config_file, tmp_path):
    wp, session, _ = client(config_file, [], tmp_path)
    with pytest.raises(WordPressResponseError):
        wp.create_post(title="t", content="c", status="trash")
    assert session.calls == []
