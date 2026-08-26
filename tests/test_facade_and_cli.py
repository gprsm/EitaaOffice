from __future__ import annotations

import json
from pathlib import Path

import pytest

from eitaa_bridge.errors import CredentialError
from eitaa_bridge.facade import EitaaBridge
from eitaa_bridge.interfaces.cli import main
from conftest import FakeResponse, FakeSession


def _multi_site_config(tmp_path: Path) -> Path:
    payload = {
        "schema_version": 1,
        "default_site_key": "site-one",
        "bridge": {"diagnostics_root": "diagnostics/bridge", "diagnostics_enabled": True},
        "core": {
            "session_file": ".eitaa_session.json",
            "database_file": "data/messages.sqlite3",
            "media_directory": "data/media",
            "diagnostics_root": "diagnostics/core",
            "diagnostics_enabled": True,
            "timeout_seconds": 30,
        },
        "wordpress_sites": [
            {
                "site_key": "site-one",
                "base_url": "https://one.example.test",
                "default_status": "draft",
                "default_category_id": None,
                "timeout_seconds": 3,
                "verify_tls": True,
                "retry_attempts": 1,
                "username_env": "SITE_ONE_USERNAME",
                "application_password_env": "SITE_ONE_APP_PASSWORD",
            },
            {
                "site_key": "site-two",
                "base_url": "https://two.example.test",
                "default_status": "draft",
                "default_category_id": 22,
                "timeout_seconds": 3,
                "verify_tls": True,
                "retry_attempts": 1,
                "username_env": "SITE_TWO_USERNAME",
                "application_password_env": "SITE_TWO_APP_PASSWORD",
            },
        ],
    }
    path = tmp_path / "bridge-multi.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_facade_creates_draft_without_opening_core(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    session = FakeSession([FakeResponse(201, {"id": 55, "status": "draft"})])
    with EitaaBridge.open(config_file, wordpress_session=session) as bridge:
        assert bridge._core is None
        result = bridge.create_text_draft(title="title", content="body")
        assert result.id == 55
    assert session.closed


def test_facade_opens_without_wordpress_credentials_and_validates_on_use(config_file, monkeypatch):
    monkeypatch.delenv("TEST_WP_USERNAME", raising=False)
    monkeypatch.delenv("TEST_WP_APP_PASSWORD", raising=False)
    session = FakeSession([])
    with EitaaBridge.open(config_file, wordpress_session=session) as bridge:
        assert bridge._core is None
        with pytest.raises(CredentialError) as error:
            bridge.wordpress_categories()
    assert error.value.safe_context["site_key"] == "medical-site"
    assert session.calls == []


def test_facade_uses_only_selected_site(tmp_path, monkeypatch):
    config = _multi_site_config(tmp_path)
    monkeypatch.setenv("SITE_ONE_USERNAME", "one-user")
    monkeypatch.setenv("SITE_ONE_APP_PASSWORD", "one-password")
    monkeypatch.setenv("SITE_TWO_USERNAME", "two-user")
    monkeypatch.setenv("SITE_TWO_APP_PASSWORD", "two-password")
    session = FakeSession([FakeResponse(201, {"id": 77, "status": "draft"})])

    with EitaaBridge.open(config, site_key="site-two", wordpress_session=session) as bridge:
        result = bridge.create_text_draft(title="title", content="body")

    assert result.site_key == "site-two"
    assert len(session.calls) == 1
    method, url, kwargs = session.calls[0]
    assert method == "POST"
    assert url == "https://two.example.test/wp-json/wp/v2/posts"
    assert kwargs["json"]["categories"] == [22]


def test_cli_sites_list_is_safe_and_marks_default(tmp_path, monkeypatch, capsys):
    config = _multi_site_config(tmp_path)
    monkeypatch.setenv("SITE_ONE_USERNAME", "one-user")
    monkeypatch.setenv("SITE_ONE_APP_PASSWORD", "one-secret")
    monkeypatch.delenv("SITE_TWO_USERNAME", raising=False)
    monkeypatch.delenv("SITE_TWO_APP_PASSWORD", raising=False)

    code = main(["--config", str(config), "sites", "list"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["site_count"] == 2
    assert payload["default_site_key"] == "site-one"
    assert payload["sites"][0]["is_default"] is True
    assert payload["sites"][0]["credentials_configured"] is True
    assert payload["sites"][1]["credentials_configured"] is False
    rendered = json.dumps(payload)
    assert "one-secret" not in rendered
    assert "one-user" not in rendered


def test_cli_doctor_skip_core_open(config_file, monkeypatch, capsys):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    code = main(["--config", str(config_file), "doctor", "--skip-core-open"])
    payload = json.loads(capsys.readouterr().out)
    assert code in {0, 1}
    assert payload["version"] == "0.7.0-ui-mvp6.1.1-gmi4.2"
    names = {item["name"] for item in payload["checks"]}
    assert "core_version" in names


def test_cli_missing_config_returns_safe_error(tmp_path, capsys):
    code = main(["--config", str(tmp_path / "missing.json"), "doctor"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["error_code"] == "configuration_error"
    assert "token" not in json.dumps(payload).lower()


def test_facade_uploads_media_without_opening_core(config_file, monkeypatch, tmp_path):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    media_file = tmp_path / "photo.jpg"
    media_file.write_bytes(b"photo")
    session = FakeSession([FakeResponse(201, {
        "id": 42,
        "status": "inherit",
        "media_type": "image",
        "mime_type": "image/jpeg",
        "source_url": "https://example.test/photo.jpg",
        "slug": "photo",
        "post": 0,
    })])
    with EitaaBridge.open(config_file, wordpress_session=session) as bridge:
        result = bridge.upload_wordpress_media(media_file, alt_text="safe alt")
        assert bridge._core is None
        assert result.id == 42


def test_cli_media_upload_outputs_safe_summary(config_file, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    media_file = tmp_path / "photo.jpg"
    media_file.write_bytes(b"photo")

    original_open = EitaaBridge.open

    class OpenContext:
        def __enter__(self):
            self.bridge = original_open(
                config_file,
                wordpress_session=FakeSession([FakeResponse(201, {
                    "id": 43,
                    "status": "inherit",
                    "media_type": "image",
                    "mime_type": "image/jpeg",
                    "source_url": "https://example.test/photo.jpg",
                    "slug": "photo",
                    "post": 0,
                })]),
            )
            return self.bridge

        def __exit__(self, exc_type, exc, tb):
            self.bridge.close()

    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: OpenContext())
    code = main([
        "--config", str(config_file),
        "wp", "media", "upload",
        "--file", str(media_file),
        "--alt-text", "private alt text",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["id"] == 43
    assert "private alt text" not in json.dumps(payload)


def test_cli_composer_preview_loads_manifest_and_returns_safe_plan(
    config_file, monkeypatch, tmp_path, capsys
):
    from types import SimpleNamespace
    from eitaa_core import Peer, PeerType, save_peer_file

    peer_file = tmp_path / "selected_private_channel.json"
    save_peer_file(
        peer_file,
        Peer(id=14394054, type=PeerType.CHANNEL, access_hash=123456789),
    )
    manifest = tmp_path / "composition.json"
    manifest.write_text(json.dumps({
        "composition_key": "roundup-1",
        "site_key": "medical-site",
        "title": "عنوان",
        "sources": [
            {"peer_file": peer_file.name, "message_id": 11795},
            {"peer_file": peer_file.name, "message_id": 11817},
        ],
    }), encoding="utf-8")

    captured = {}

    class FakeBridge:
        def preview_wordpress_composition(self, request):
            captured["request"] = request
            return SimpleNamespace(safe_summary=lambda: {
                "outcome": "composition_preview",
                "source_count": len(request.sources),
            })

        def close(self):
            pass

    class Context:
        def __enter__(self):
            return FakeBridge()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context())
    code = main([
        "--config", str(config_file),
        "composer", "preview", "--file", str(manifest),
    ])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["outcome"] == "composition_preview"
    assert payload["source_count"] == 2
    assert captured["request"].sources[1].message_id == 11817


def test_cli_taxonomy_list_outputs_term_ids(config_file, monkeypatch, capsys):
    from eitaa_bridge.domain import WordPressTerm

    class FakeBridge:
        def wordpress_categories(self, *, search=None, per_page=100):
            return (WordPressTerm(id=12, name="اخبار", slug="news", taxonomy="category"),)

        def close(self):
            pass

    class Context:
        def __enter__(self):
            return FakeBridge()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context())
    code = main(["--config", str(config_file), "wp", "categories"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["taxonomy"] == "category"
    assert payload["terms"][0]["id"] == 12
