from __future__ import annotations

import threading
from urllib.request import urlopen

from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.interfaces.http_api import BridgeApiHttpServer


def test_loopback_media_cache_streams_file(config_file, tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = BridgeApplicationApi(config_file)
    source = tmp_path / "thumbnail.jpg"
    source.write_bytes(b"small-image")
    token = api.register_media_cache_file(source, "image/jpeg")
    server = BridgeApiHttpServer(("127.0.0.1", 0), api)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        with urlopen(f"http://{host}:{port}/api/v1/media-cache/{token}", timeout=3) as response:
            assert response.status == 200
            assert response.headers.get_content_type() == "image/jpeg"
            assert response.read() == b"small-image"
    finally:
        server.shutdown()
        server.server_close()
        api.close()
        thread.join(timeout=3)


def test_loopback_server_serves_ui_and_accepts_browser_file_upload(config_file, tmp_path, monkeypatch):
    from urllib.request import Request

    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = BridgeApplicationApi(config_file)
    ui_root = tmp_path / "ui"
    ui_root.mkdir()
    (ui_root / "index.html").write_text("<html>bridge-ui</html>", encoding="utf-8")
    uploads = tmp_path / "uploads"
    server = BridgeApiHttpServer(("127.0.0.1", 0), api, ui_root=ui_root, upload_root=uploads)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        with urlopen(f"http://{host}:{port}/", timeout=3) as response:
            assert response.status == 200
            assert b"bridge-ui" in response.read()
        request = Request(
            f"http://{host}:{port}/api/v1/files/upload",
            data=b"office-file",
            method="POST",
            headers={
                "Content-Type": "application/octet-stream",
                "X-Eitaa-Filename": "sample.txt",
            },
        )
        with urlopen(request, timeout=3) as response:
            payload = __import__("json").loads(response.read().decode("utf-8"))
            assert response.status == 200
            assert payload["ok"] is True
            assert __import__("pathlib").Path(payload["path"]).read_bytes() == b"office-file"
    finally:
        server.shutdown()
        server.server_close()
        api.close()
        thread.join(timeout=3)
