"""Loopback JSON/HTTP server exposing the BaleApi facade.

This is the standalone modular entrypoint of the Bale branch: it runs inside
the quarantined ``bale_client`` package, uses only the Python standard
library for serving (``http.server`` threaded, same pattern as the project's
main ``http_api``), and binds 127.0.0.1 by default. It is intentionally NOT
wired into the main application server or provider registry.

Auth model: a local bearer token. When ``--token`` is not given a token is
generated per run and printed once to the console (never logged with
requests). Endpoints mirror :class:`BaleApi` one-to-one.

Run::

    python -m eitaa_bridge.application.bale_client.api_server \\
        --host 127.0.0.1 --port 8791 --token SECRET

Endpoints (JSON in/out, POST bodies unless noted)::

    GET  /health                       -> liveness + connection state
    GET  /account                      -> safe session card
    POST /auth/start      {phone}
    POST /auth/code       {transaction_hash, code, passphrase?}
    POST /auth/password   {transaction_hash, password, passphrase?}
    POST /connect         {passphrase?}
    POST /disconnect
    POST /contacts/list
    POST /contacts/search {query}
    POST /contacts/add-phone {phone, name, contact_type?}
    POST /contacts/add    {user_id, contact_type?}
    POST /contacts/remove {user_id, contact_type?}
    POST /dialogs/list    {limit?}
    POST /messages/send-text {user_id, text, silent?}
    POST /messages/send-file  {user_id, path, caption?, media_kind?}
    POST /messages/read-history {user_id, limit?, offset_date?}
    POST /messages/read-media {user_id, message_id, destination_dir}
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import logging
import os
import secrets
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .api import BaleApi, BaleApiError
from .errors import AuthenticationError, ProtocolError

log = logging.getLogger("bale_client.api_server")

_MAX_BODY_BYTES = 4 * 1024 * 1024

API_VERSION = "1"
ROUTE_PREFIX = f"/api/bale/v{API_VERSION}"


class BaleApiService:
    """Owns the singleton facade and serializes access to it."""

    def __init__(
        self,
        *,
        vault_path: Path,
        log_path: Path,
        vault_passphrase: str | None = None,
        auto_reconnect: bool = True,
    ) -> None:
        self.vault_path = vault_path
        self.log_path = log_path
        self.vault_passphrase = vault_passphrase
        self.auto_reconnect = auto_reconnect
        self.api: BaleApi | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.thread: Any = None  # asyncio runner thread handle
        self.transaction_hash: str | None = None
        self._expected_stage: str | None = None
        self._last_connect_error: str | None = None

    # ------------------------------ loop plumbing ---------------------------

    def ensure_loop(self) -> None:
        if self.loop is not None and self.loop.is_running():
            return
        import threading

        self.loop = asyncio.new_event_loop()

        def run() -> None:
            assert self.loop is not None
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()

        self.thread = threading.Thread(target=run, name="bale-api-loop", daemon=True)
        self.thread.start()

    def run_coro(self, coro: Any) -> Any:
        self.ensure_loop()
        assert self.loop is not None
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result(timeout=120)

    # ------------------------------- lifecycle -------------------------------

    def _ensure_api(self) -> BaleApi:
        if self.api is None:
            self.api = BaleApi.create(
                passphrase=self.vault_passphrase,
                vault_path=self.vault_path,
                log_path=self.log_path,
            )
        return self.api

    def _connect_locked(self, passphrase: str | None) -> dict[str, Any]:
        """Synchronous connect used by both /connect and startup reconnect."""
        api = self._ensure_api()
        effective = passphrase or self.vault_passphrase
        try:
            result = self.run_coro(api.connect(passphrase=effective, subscribe=True))
            self._last_connect_error = None
            return result
        except BaleApiError as exc:
            self._last_connect_error = exc.code
            raise

    def startup_reconnect(self) -> None:
        """Best-effort auto-reconnect when a vault session already exists."""
        if not self.auto_reconnect or not self.vault_path.exists():
            return
        try:
            self._connect_locked(None)
            log.info("Startup auto-reconnect succeeded")
        except BaleApiError as exc:
            log.info("Startup auto-reconnect skipped: %s", exc.code)
        except Exception:
            log.exception("Startup auto-reconnect failed unexpectedly")

    def health(self) -> dict[str, Any]:
        connected = bool(self.api and self.api._client.ws and self.api._client.ws.connected)
        return {
            "ok": True,
            "connected": connected,
            "has_vault": self.vault_path.exists(),
            "last_connect_error": self._last_connect_error,
        }

    def account(self) -> dict[str, Any]:
        return self.run_coro(self._ensure_api().account_card())

    def connect(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._connect_locked(payload.get("passphrase"))

    def disconnect(self) -> dict[str, Any]:
        if self.api is not None:
            self.run_coro(self.api.close())
        return {"disconnected": True}

    # --------------------------------- auth ---------------------------------

    def _notify_otp_sent(self) -> None:
        """Play the OTP alert sound (10s) in a background thread so the HTTP
        response is not blocked."""
        import threading

        wav = Path(__file__).parents[3] / "data" / "otp_alert.wav"

        def play() -> None:
            try:
                if not wav.exists():
                    log.warning("OTP alert file missing: %s", wav)
                    return
                if os.name == "nt":
                    import winsound

                    winsound.PlaySound(str(wav), winsound.SND_FILENAME)
                else:
                    import shutil
                    import subprocess

                    player = next(
                        (p for p in ("paplay", "aplay", "afplay") if shutil.which(p)),
                        None,
                    )
                    if player:
                        subprocess.run([player, str(wav)], check=False)
            except Exception:
                log.exception("OTP alert playback failed")

        threading.Thread(target=play, name="bale-otp-alert", daemon=True).start()

    def auth_start(self, payload: dict[str, Any]) -> dict[str, Any]:
        phone = _require(payload, "phone")
        result = self.run_coro(self._ensure_api().auth_start(phone))
        self.transaction_hash = result["transaction_hash"]
        self._expected_stage = "code"
        self._notify_otp_sent()
        return result

    def auth_code(self, payload: dict[str, Any]) -> dict[str, Any]:
        transaction_hash = payload.get("transaction_hash") or self.transaction_hash
        if not transaction_hash:
            raise BaleApiError("transaction_hash is required", code="bale_missing_transaction")
        code = _require(payload, "code")
        result = self.run_coro(
            self._ensure_api().auth_code(transaction_hash, code, passphrase=payload.get("passphrase"))
        )
        if result.get("transaction_hash"):
            self.transaction_hash = result["transaction_hash"]
            self._expected_stage = result.get("next")
        return result

    def auth_password(self, payload: dict[str, Any]) -> dict[str, Any]:
        transaction_hash = payload.get("transaction_hash") or self.transaction_hash
        if not transaction_hash:
            raise BaleApiError("transaction_hash is required", code="bale_missing_transaction")
        password = _require(payload, "password")
        return self.run_coro(
            self._ensure_api().auth_password(
                transaction_hash, password, passphrase=payload.get("passphrase")
            )
        )

    # ------------------------------- operations ------------------------------

    def _connected_api(self) -> BaleApi:
        api = self._ensure_api()
        if not api._client.ws or not api._client.ws.connected:
            if api._client.vault.exists():
                # Auto-connect using the server-managed vault passphrase.
                try:
                    self._connect_locked(None)
                except BaleApiError:
                    raise
            if not api._client.ws or not api._client.ws.connected:
                raise BaleApiError("Connect first via /connect", code="bale_not_connected")
        return api

    def send_file_upload(self, user_id: Any, file_bytes: bytes, filename: str, caption: str | None) -> dict[str, Any]:
        """Send a raw uploaded file (multipart) through the staging path."""
        api = self._connected_api()
        return self.run_coro(
            api.send_file_bytes(int(user_id), filename, file_bytes, caption=caption)
        )

    def contacts_list(self) -> list[dict[str, Any]]:
        api = self._connected_api()
        return self.run_coro(api.list_contacts())

    def contacts_search(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        api = self._connected_api()
        return self.run_coro(api.search_contacts(_require(payload, "query")))

    def contacts_add_phone(self, payload: dict[str, Any]) -> dict[str, Any]:
        api = self._connected_api()
        return self.run_coro(
            api.add_contact_by_phone(
                _require(payload, "phone"),
                payload.get("name") or "Bale Contact",
                contact_type=int(payload.get("contact_type", 1)),
            )
        )

    def contacts_add(self, payload: dict[str, Any]) -> dict[str, Any]:
        api = self._connected_api()
        return self.run_coro(
            api.add_contact(_require(payload, "user_id"), contact_type=int(payload.get("contact_type", 1)))
        )

    def contacts_remove(self, payload: dict[str, Any]) -> dict[str, Any]:
        api = self._connected_api()
        return self.run_coro(
            api.remove_contact(_require(payload, "user_id"), contact_type=int(payload.get("contact_type", 1)))
        )

    def dialogs_list(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        api = self._connected_api()
        limit = int(payload.get("limit", 20))
        kwargs: dict[str, Any] = {"limit": limit}
        if payload.get("offset_date") is not None:
            kwargs["offset_date"] = int(payload["offset_date"])
        return self.run_coro(api.list_dialogs(**kwargs))


    def send_text(self, payload: dict[str, Any]) -> dict[str, Any]:
        api = self._connected_api()
        return self.run_coro(
            api.send_text(
                _require(payload, "user_id"),
                _require(payload, "text"),
                silent=bool(payload.get("silent", False)),
            )
        )

    def send_file(self, payload: dict[str, Any]) -> dict[str, Any]:
        api = self._connected_api()
        return self.run_coro(
            api.send_file(
                _require(payload, "user_id"),
                _require(payload, "path"),
                caption=payload.get("caption"),
                media_kind=payload.get("media_kind"),
            )
        )

    def send_upload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a base64-encoded file upload from the browser UI."""
        user_id = _require(payload, "user_id")
        data_b64 = _require(payload, "data_base64")
        name = _require(payload, "name")
        import base64

        try:
            file_bytes = base64.b64decode(str(data_b64), validate=True)
        except Exception as exc:
            raise BaleApiError("data_base64 is not valid base64", code="bale_invalid_upload") from exc
        if len(file_bytes) > 50 * 1024 * 1024:
            raise BaleApiError("Upload exceeds the 50MB limit", code="bale_upload_too_large")
        return self.send_file_upload(user_id, file_bytes, str(name), payload.get("caption"))

    def read_history(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        api = self._connected_api()
        return self.run_coro(
            api.read_history(
                _require(payload, "user_id"),
                limit=int(payload.get("limit", 20)),
                offset_date=payload.get("offset_date"),
            )
        )

    def read_media(self, payload: dict[str, Any]) -> dict[str, Any]:
        api = self._connected_api()
        return self.run_coro(
            api.read_message_media(
                _require(payload, "user_id"),
                int(_require(payload, "message_id")),
                _require(payload, "destination_dir"),
            )
        )


ROUTES: dict[str, tuple[str, str]] = {
    # name -> (method, service_attr)
    "health": ("GET", "health"),
    "account": ("GET", "account"),
    "connect": ("POST", "connect"),
    "disconnect": ("POST", "disconnect"),
    "auth/start": ("POST", "auth_start"),
    "auth/code": ("POST", "auth_code"),
    "auth/password": ("POST", "auth_password"),
    "contacts/list": ("POST", "contacts_list"),
    "contacts/search": ("POST", "contacts_search"),
    "contacts/add-phone": ("POST", "contacts_add_phone"),
    "contacts/add": ("POST", "contacts_add"),
    "contacts/remove": ("POST", "contacts_remove"),
    "dialogs/list": ("POST", "dialogs_list"),
    "messages/send-text": ("POST", "send_text"),
    "messages/send-file": ("POST", "send_file"),
    "messages/send-upload": ("POST", "send_upload"),
    "messages/read-history": ("POST", "read_history"),
    "messages/read-media": ("POST", "read_media"),
}


def _require(payload: dict[str, Any], key: str) -> Any:
    value = payload.get(key)
    if value is None or (isinstance(value, str) and not value):
        raise BaleApiError(f"Field '{key}' is required", code="bale_missing_field")
    return value


class BaleApiRequestHandler(BaseHTTPRequestHandler):
    server_version = "BaleBranchAPI/1"
    protocol_version = "HTTP/1.1"
    service: BaleApiService
    token: str

    def log_message(self, fmt: str, *args: Any) -> None:
        # Privacy: the default handler logs the full request line including
        # any query string; keep logs to the HTTP verb only.
        verb = fmt.split(" ")[0].strip('"')
        log.debug("http %s %s", verb, self.path.split("?", 1)[0])

    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        return secrets.compare_digest(header, f"Bearer {self.token}")

    def _dispatch(self, handler_name: str, http_method: str, payload: dict[str, Any]) -> Any:
        """Call a service method with or without a payload parameter."""
        method = getattr(self.service, handler_name)
        signature = inspect.signature(method)
        accepts_payload = any(
            param.kind
            in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.POSITIONAL_ONLY)
            and param.name != "self"
            for param in signature.parameters.values()
        ) or any(param.kind == inspect.Parameter.VAR_POSITIONAL for param in signature.parameters.values())
        if http_method == "GET" or not accepts_payload:
            return method()
        return method(payload)

    def _serve_ui(self) -> None:
        """Serve the bundled single-file web UI (loopback-only)."""
        ui_path = Path(__file__).with_name("webui.html")
        try:
            body = ui_path.read_bytes()
        except OSError:
            return self._send_json(HTTPStatus.NOT_FOUND, {"error": "ui_missing"})
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _handle(self, http_method: str) -> None:
        path = (self.path or "/").split("?", 1)[0].rstrip("/") or "/"
        if path == "/":
            return self._send_json(HTTPStatus.OK, {"ok": True, "service": "bale-branch-api", "prefix": ROUTE_PREFIX, "ui": "/ui"})
        if path == "/ui":
            return self._serve_ui()
        prefix = ROUTE_PREFIX + "/"
        if not path.startswith(prefix):
            return self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
        name = path[len(prefix):]
        route = ROUTES.get(name)
        if route is None or route[0] != http_method:
            return self._send_json(HTTPStatus.NOT_FOUND, {"error": "unknown_route"})
        if not self._authorized():
            return self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
        payload: dict[str, Any] = {}
        if http_method == "POST":
            try:
                payload = self._read_json_body()
            except BaleApiError as exc:
                return self._send_json(HTTPStatus.BAD_REQUEST, {"error": exc.code, "message": str(exc)})
        handler_name = route[1]
        try:
            result = self._dispatch(handler_name, http_method, payload)
        except BaleApiError as exc:
            status = HTTPStatus.CONFLICT if exc.code == "bale_not_connected" else HTTPStatus.BAD_REQUEST
            return self._send_json(status, {"error": exc.code, "message": str(exc)})
        except (AuthenticationError, ProtocolError) as exc:
            return self._send_json(
                HTTPStatus.CONFLICT, {"error": "bale_protocol_error", "message": str(exc)}
            )
        except Exception as exc:  # last-resort: no internal detail leaks
            log.exception("Unhandled route failure")
            return self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "internal_error", "message": "The request failed without a safe detail."},
            )
        self._send_json(HTTPStatus.OK, result if result is not None else {"ok": True})

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0:
            return {}
        if length > _MAX_BODY_BYTES:
            raise BaleApiError("Request body too large", code="bale_body_too_large")
        raw = self.rfile.read(length)
        try:
            value = json.loads(raw.decode("utf-8")) if raw.strip() else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BaleApiError("Request body must be valid JSON", code="bale_invalid_json") from exc
        if not isinstance(value, dict):
            raise BaleApiError("Request body must be a JSON object", code="bale_invalid_json")
        return value

    def do_GET(self) -> None:
        self._handle("GET")

    def do_POST(self) -> None:
        self._handle("POST")


def build_server(
    *,
    host: str = "127.0.0.1",
    port: int = 8791,
    token: str,
    vault_path: Path,
    log_path: Path,
) -> ThreadingHTTPServer:
    service = BaleApiService(vault_path=vault_path, log_path=log_path)
    handler = type(
        "BoundBaleApiRequestHandler",
        (BaleApiRequestHandler,),
        {"service": service, "token": token},
    )
    httpd = ThreadingHTTPServer((host, port), handler)
    httpd.daemon_threads = True
    return httpd


def build_server(
    *,
    host: str = "127.0.0.1",
    port: int = 8791,
    token: str,
    vault_path: Path,
    log_path: Path,
    vault_passphrase: str | None = None,
    auto_reconnect: bool = True,
) -> ThreadingHTTPServer:
    service = BaleApiService(
        vault_path=vault_path,
        log_path=log_path,
        vault_passphrase=vault_passphrase,
        auto_reconnect=auto_reconnect,
    )
    handler = type(
        "BoundBaleApiRequestHandler",
        (BaleApiRequestHandler,),
        {"service": service, "token": token},
    )
    httpd = ThreadingHTTPServer((host, port), handler)
    httpd.daemon_threads = True
    service.startup_reconnect()
    return httpd


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bale branch local API server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8791)
    parser.add_argument("--token", help="Bearer token; generated when omitted")
    parser.add_argument("--vault", default="data/bale_session.vault")
    parser.add_argument("--log", default="data/bale_client.log")
    parser.add_argument(
        "--vault-passphrase",
        help="Passphrase for the encrypted session vault; auto-generated and kept in data/bale_vault.key when omitted",
    )
    parser.add_argument("--no-auto-reconnect", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        print("Refusing non-loopback bind for the Bale branch API.", file=sys.stderr)
        return 2
    token = args.token or secrets.token_urlsafe(24)
    vault_path = Path(args.vault)
    log_path = Path(args.log)

    # Session persistence: with no explicit passphrase the server generates
    # one and keeps it beside the vault so restarts auto-reconnect without
    # asking the user again. Local-disk machine boundary, loopback-only API.
    if args.vault_passphrase:
        passphrase = args.vault_passphrase
    else:
        key_file = vault_path.parent / "bale_vault.key"
        try:
            passphrase = key_file.read_text(encoding="utf-8").strip()
        except OSError:
            key_file.parent.mkdir(parents=True, exist_ok=True)
            passphrase = secrets.token_urlsafe(32)
            key_file.write_text(passphrase, encoding="utf-8")
            if os.name == "nt":
                pass  # per-user profile dir already restricts access

    httpd = build_server(
        host=args.host,
        port=args.port,
        token=token,
        vault_path=vault_path,
        log_path=log_path,
        vault_passphrase=passphrase,
        auto_reconnect=not args.no_auto_reconnect,
    )
    print(f"Bale branch API listening on http://{args.host}:{args.port}{ROUTE_PREFIX}")
    print(f"UI: http://{args.host}:{args.port}/ui")
    print(f"Authorization: Bearer {token}" if not args.token else "Using caller-provided token.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
