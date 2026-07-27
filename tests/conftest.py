from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    payload = {
        "schema_version": 1,
        "default_site_key": "medical-site",
        "bridge": {"diagnostics_root": "diagnostics/bridge", "diagnostics_enabled": True},
        "core": {
            "session_file": ".eitaa_session.json",
            "database_file": "data/messages.sqlite3",
            "media_directory": "data/media",
            "diagnostics_root": "diagnostics/core",
            "diagnostics_enabled": True,
            "timeout_seconds": 30,
        },
        "wordpress_sites": [{
            "site_key": "medical-site",
            "base_url": "https://example.test",
            "default_status": "draft",
            "default_category_id": 12,
            "timeout_seconds": 3,
            "verify_tls": True,
            "retry_attempts": 1,
            "username_env": "TEST_WP_USERNAME",
            "application_password_env": "TEST_WP_APP_PASSWORD",
        }],
    }
    path = tmp_path / "bridge.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class FakeResponse:
    def __init__(self, status_code: int, payload=None, headers=None, json_error: Exception | None = None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise self._json_error
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.closed = False

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def close(self):
        self.closed = True
