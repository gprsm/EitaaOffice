"""Opt-in local acceptance fixture. Never connects to a messaging provider."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from uuid import uuid4

from test_bale_main_product import OfflineOwner, Protector, create_account, login
from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.application.bale_provider_worker import BaleProviderProcessWorker
import eitaa_bridge.application.bale_runtime as runtime
from eitaa_bridge.interfaces.http_api import BridgeApiHttpServer, _ApiHandler


def main():
    root = Path(__file__).resolve().parents[1]
    workspace = root / ".test-work"
    workspace.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bale-ui-", dir=workspace, ignore_cleanup_errors=True) as directory:
        path = Path(directory) / "bridge.json"
        config = {"schema_version": 1, "bridge": {"diagnostics_root": "diagnostics/bridge", "diagnostics_enabled": False}, "default_site_key": "fixture", "core": {"session_file": "session.json", "database_file": "data/messages.sqlite3", "media_directory": "data/media", "diagnostics_root": "diagnostics/core", "diagnostics_enabled": False, "timeout_seconds": 30},
            "features": {"multi_session": {"enabled": True}, "app_user_auth": {"enabled": True}},
            "wordpress_sites": [{"site_key": "fixture", "base_url": "https://example.test", "default_status": "draft", "username_env": "TEST_WP_USERNAME", "application_password_env": "TEST_WP_APP_PASSWORD"}]}
        path.write_text(json.dumps(config), encoding="utf-8")
        runtime.BaleProviderProcessWorker = lambda account, config: BaleProviderProcessWorker(account, config, owner_factory=OfflineOwner)
        app = BridgeApplicationApi(path, phone_protector=Protector())
        setup = app.dispatch("POST", "/api/v2/app-auth/setup", body={"username": "preview.admin", "password": "synthetic preview password", "display_name": "Preview Admin"}, client_kind="browser")
        if setup.status != 201:
            raise RuntimeError("Fixture setup failed")
        token = setup.headers["Set-Cookie"].split(";", 1)[0].split("=", 1)[1]
        def request(method, route, body=None):
            return app.dispatch(method, route, body=body, app_session_token=token, csrf_token=setup.payload["csrf_token"], client_kind="browser", correlation_id=uuid4().hex)
        first = create_account(request)
        login(request, first)
        paging_contacts = int(os.environ.get("BALE_UI_PREVIEW_CONTACT_COUNT", "0"))
        if paging_contacts:
            if not 1 <= paging_contacts <= 5000:
                raise ValueError("BALE_UI_PREVIEW_CONTACT_COUNT must be between 1 and 5000")
            OfflineOwner.states[first]["contacts"] = {
                index: f"Paging Fixture {index:04d}"
                for index in range(1, paging_contacts + 1)
            }
        second = create_account(request, "+10000000002")
        eitaa = create_account(request, "+10000000003", "eitaa")
        OfflineOwner.states[first]["messages"] = [{"message_id": 17, "sender_id": 1, "date": 100, "text": "Fixture reply"}]
        # Only synthetic fixture labels are written into this disposable database.
        with app._coordinator._connect() as connection:
            for account, label in [(first, "Bale Alpha"), (second, "Bale Beta"), (eitaa, "Eitaa Fixture")]:
                connection.execute("UPDATE messenger_accounts SET label=? WHERE id=?", (label, account))
            connection.commit()

        class FixtureHandler(_ApiHandler):
            def end_headers(self):
                if self.path == "/":
                    self.send_header("Set-Cookie", setup.headers["Set-Cookie"])
                super().end_headers()

            def do_GET(self):
                if self.path == "/__fixture__/receive":
                    OfflineOwner.states[first]["messages"].append({"message_id": 18, "sender_id": 42, "date": 101, "text": "Incoming fixture"})
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"ok":true}')
                    return
                super().do_GET()

            def log_message(self, *args):
                pass

        server = BridgeApiHttpServer(("127.0.0.1", 0), app, ui_root=root / "ui" / "dist")
        server.RequestHandlerClass = FixtureHandler
        print(f"http://127.0.0.1:{server.server_address[1]}/", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.shutdown()
            server.server_close()
            app.close()


if __name__ == "__main__":
    main()
