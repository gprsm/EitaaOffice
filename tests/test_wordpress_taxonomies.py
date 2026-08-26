from __future__ import annotations

from eitaa_bridge.config import WordPressSiteConfig
from eitaa_bridge.infrastructure.wordpress import WordPressClient, WordPressCredentials
from conftest import FakeResponse, FakeSession


def client(responses):
    site = WordPressSiteConfig(
        site_key="medical-site",
        base_url="https://example.test",
        default_category_id=12,
        timeout_seconds=3,
        retry_attempts=0,
        username_env="TEST_USER",
        application_password_env="TEST_PASSWORD",
    )
    return WordPressClient(
        site,
        WordPressCredentials(username="editor", application_password="secret"),
        session=FakeSession(responses),
    )


def test_lists_categories_and_tags():
    session = FakeSession([
        FakeResponse(200, [{"id": 12, "name": "اخبار", "slug": "news", "count": 3, "parent": 0}]),
        FakeResponse(200, [{"id": 4, "name": "سلامت", "slug": "health", "count": 8}]),
    ])
    wp = client([])
    wp.session = session
    categories = wp.list_categories()
    tags = wp.list_tags(search="سلامت")
    assert categories[0].taxonomy == "category"
    assert tags[0].taxonomy == "post_tag"
    assert "wp-json/wp/v2/categories" in session.calls[0][1]
    assert "search=" in session.calls[1][1]


def test_create_draft_sends_multiple_categories_tags_and_excerpt():
    session = FakeSession([FakeResponse(201, {
        "id": 91,
        "status": "draft",
        "slug": "roundup",
        "featured_media": 0,
    })])
    wp = client([])
    wp.session = session
    post = wp.create_text_draft(
        title="عنوان",
        content="بدنه",
        excerpt="چکیده",
        slug="roundup",
        category_ids=(12, 15),
        tag_ids=(4, 9),
    )
    payload = session.calls[0][2]["json"]
    assert post.id == 91
    assert payload["categories"] == [12, 15]
    assert payload["tags"] == [4, 9]
    assert payload["excerpt"] == "چکیده"


def test_create_tag_reuses_exact_existing_name():
    session = FakeSession([
        FakeResponse(200, [{"id": 8, "name": "سلامت", "slug": "health", "count": 2}]),
    ])
    wp = client([])
    wp.session = session
    tag = wp.create_tag(name="سلامت")
    assert tag.id == 8
    assert len(session.calls) == 1
    assert session.calls[0][0] == "GET"


def test_create_tag_posts_new_term():
    session = FakeSession([
        FakeResponse(200, []),
        FakeResponse(201, {"id": 19, "name": "فیزیولوژی", "slug": "physiology", "count": 0}),
    ])
    wp = client([])
    wp.session = session
    tag = wp.create_tag(name="فیزیولوژی")
    assert tag.id == 19
    assert session.calls[1][0] == "POST"
    assert session.calls[1][2]["json"] == {"name": "فیزیولوژی"}
