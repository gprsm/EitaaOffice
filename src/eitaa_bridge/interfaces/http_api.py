"""Minimal loopback HTTP adapter for :mod:`eitaa_bridge.application.api`."""

from __future__ import annotations

import argparse
import hmac
import ipaddress
import json
import os
import mimetypes
import re
import sys
import threading
import time
import uuid
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from ..application.api import ApiResponse, BridgeApplicationApi
from ..errors import BridgeError
from ..version import __version__

_MAX_REQUEST_BYTES = 2 * 1024 * 1024
_MAX_UPLOAD_BYTES = 1024 * 1024 * 1024
_SAFE_UPLOAD_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_RUNTIME_PROTOCOL = "1"


@dataclass(slots=True)
class RuntimeOwnership:
    install_id: str
    owner_root: Path
    owner_token: str
    state_file: Path
    heartbeat_timeout: float
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_heartbeat: float = field(default_factory=time.monotonic)

    def authorized(self, supplied: str | None) -> bool:
        return bool(supplied) and hmac.compare_digest(supplied or "", self.owner_token)

    def heartbeat(self) -> None:
        self.last_heartbeat = time.monotonic()

    def identity(self, api: BridgeApplicationApi, address: tuple[str, int]) -> dict[str, Any]:
        return {
            "ok": True,
            "service": "eitaa-bridge-runtime",
            "runtime_protocol": _RUNTIME_PROTOCOL,
            "api_version": api.API_VERSION,
            "bridge_version": __version__,
            "install_id": self.install_id,
            "owner_root": str(self.owner_root),
            "pid": os.getpid(),
            "host": str(address[0]),
            "port": int(address[1]),
            "started_at": self.started_at,
            "heartbeat_timeout_seconds": self.heartbeat_timeout,
        }

    def write_state(self, api: BridgeApplicationApi, address: tuple[str, int]) -> None:
        payload = self.identity(api, address)
        payload["format"] = "eitaa-bridge-backend-owner-v1"
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_file.with_suffix(self.state_file.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, self.state_file)

    def clear_state(self) -> None:
        try:
            payload = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        if int(payload.get("pid") or 0) != os.getpid():
            return
        try:
            self.state_file.unlink()
        except OSError:
            pass


class _ApiHandler(BaseHTTPRequestHandler):
    server_version = "EitaaBridgeAPI/0.7"
    sys_version = ""

    @property
    def api(self) -> BridgeApplicationApi:
        return self.server.api  # type: ignore[attr-defined]

    def do_GET(self) -> None:  # noqa: N802
        request_path = urlsplit(self.path).path
        if request_path == "/api/v1/runtime/identity":
            self._runtime_identity()
        elif request_path.startswith("/api/v1/media-cache/"):
            self._serve_media_cache()
        elif request_path.startswith("/api/"):
            self._dispatch("GET")
        else:
            self._serve_static()

    def do_POST(self) -> None:  # noqa: N802
        request_path = urlsplit(self.path).path
        if request_path == "/api/v1/runtime/heartbeat":
            self._runtime_heartbeat()
        elif request_path == "/api/v1/runtime/shutdown":
            self._runtime_shutdown()
        elif request_path == "/api/v1/files/upload":
            self._upload_file()
        else:
            self._dispatch("POST")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Allow", "GET, POST, OPTIONS")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()

    @property
    def runtime_ownership(self) -> RuntimeOwnership | None:
        return self.server.runtime_ownership  # type: ignore[attr-defined]

    def _runtime_authorized(self) -> RuntimeOwnership | None:
        ownership = self.runtime_ownership
        if ownership is None:
            self._write_json(
                ApiResponse(
                    404,
                    {
                        "ok": False,
                        "error": {
                            "component": "runtime",
                            "error_code": "runtime_ownership_disabled",
                            "message": "This API process is not managed by the Office runtime.",
                            "safe_context": {},
                        },
                    },
                )
            )
            return None
        if not ownership.authorized(self.headers.get("X-Eitaa-Runtime-Token")):
            self._write_json(
                ApiResponse(
                    403,
                    {
                        "ok": False,
                        "error": {
                            "component": "runtime",
                            "error_code": "runtime_owner_unauthorized",
                            "message": "Runtime ownership token is invalid.",
                            "safe_context": {},
                        },
                    },
                )
            )
            return None
        return ownership

    def _runtime_identity(self) -> None:
        ownership = self._runtime_authorized()
        if ownership is None:
            return
        self._write_json(ApiResponse(200, ownership.identity(self.api, self.server.server_address)))

    def _runtime_heartbeat(self) -> None:
        ownership = self._runtime_authorized()
        if ownership is None:
            return
        try:
            payload = self._read_json()
        except _RequestError as exc:
            self._write_json(ApiResponse(exc.status, {"ok": False, "error": {"component": "runtime", "error_code": exc.code, "message": exc.message, "safe_context": {}}}))
            return
        if str(payload.get("install_id") or "") != ownership.install_id:
            self._write_json(ApiResponse(409, {"ok": False, "error": {"component": "runtime", "error_code": "runtime_install_id_mismatch", "message": "Runtime install ID does not match.", "safe_context": {}}}))
            return
        ownership.heartbeat()
        self._write_json(ApiResponse(200, {"ok": True, "pid": os.getpid()}))

    def _runtime_shutdown(self) -> None:
        ownership = self._runtime_authorized()
        if ownership is None:
            return
        try:
            payload = self._read_json()
        except _RequestError as exc:
            self._write_json(ApiResponse(exc.status, {"ok": False, "error": {"component": "runtime", "error_code": exc.code, "message": exc.message, "safe_context": {}}}))
            return
        if str(payload.get("install_id") or "") != ownership.install_id:
            self._write_json(ApiResponse(409, {"ok": False, "error": {"component": "runtime", "error_code": "runtime_install_id_mismatch", "message": "Runtime install ID does not match.", "safe_context": {}}}))
            return
        self._write_json(ApiResponse(202, {"ok": True, "status": "shutting_down", "pid": os.getpid()}))
        threading.Thread(target=self.server.shutdown, name="bridge-runtime-shutdown", daemon=True).start()

    def _dispatch(self, method: str) -> None:
        try:
            body = self._read_json() if method == "POST" else None
            response = self.api.dispatch(
                method,
                self.path,
                body=body,
                authorization=self.headers.get("Authorization"),
            )
        except _RequestError as exc:
            response = ApiResponse(
                exc.status,
                {
                    "ok": False,
                    "error": {
                        "component": "api",
                        "error_code": exc.code,
                        "message": exc.message,
                        "safe_context": {},
                        "debug_file": None,
                    },
                },
            )
        self._write_json(response)

    def _serve_media_cache(self) -> None:
        token = urlsplit(self.path).path.rsplit("/", 1)[-1].strip().lower()
        resolved = self.api.resolve_media_cache_file(token)
        if resolved is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        path, mime_type = resolved
        try:
            size = path.stat().st_size
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(size))
            self.send_header("Cache-Control", "private, max-age=86400")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            with path.open("rb") as handle:
                while chunk := handle.read(256 * 1024):
                    self.wfile.write(chunk)
        except (OSError, BrokenPipeError, ConnectionResetError):
            return

    def _upload_file(self) -> None:
        raw_length = self.headers.get("Content-Length")
        try:
            length = int(raw_length or "-1")
        except ValueError:
            length = -1
        if length < 0 or length > _MAX_UPLOAD_BYTES:
            self._write_json(
                ApiResponse(
                    413,
                    {
                        "ok": False,
                        "error": {
                            "component": "api",
                            "error_code": "file_upload_too_large",
                            "message": "فایل انتخاب‌شده بیش از حد مجاز است.",
                            "safe_context": {},
                        },
                    },
                )
            )
            return
        encoded_name = self.headers.get("X-Eitaa-Filename", "upload.bin")
        original = Path(unquote(encoded_name)).name.strip() or "upload.bin"
        safe_name = _SAFE_UPLOAD_NAME.sub("_", original)[:180] or "upload.bin"
        upload_root: Path = self.server.upload_root  # type: ignore[attr-defined]
        upload_root.mkdir(parents=True, exist_ok=True)
        target = upload_root / f"{uuid.uuid4().hex}_{safe_name}"
        remaining = length
        try:
            with target.open("wb") as stream:
                while remaining:
                    chunk = self.rfile.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise OSError("incomplete upload")
                    stream.write(chunk)
                    remaining -= len(chunk)
        except OSError:
            target.unlink(missing_ok=True)
            self._write_json(
                ApiResponse(
                    500,
                    {
                        "ok": False,
                        "error": {
                            "component": "api",
                            "error_code": "file_upload_failed",
                            "message": "ذخیره فایل انتخاب‌شده ناموفق بود.",
                            "safe_context": {},
                        },
                    },
                )
            )
            return
        self._write_json(ApiResponse(200, {"ok": True, "path": str(target.resolve())}))

    def _serve_static(self) -> None:
        ui_root: Path | None = self.server.ui_root  # type: ignore[attr-defined]
        if ui_root is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        request_path = unquote(urlsplit(self.path).path)
        relative = request_path.lstrip("/") or "index.html"
        candidate = (ui_root / relative).resolve()
        try:
            candidate.relative_to(ui_root)
        except ValueError:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not candidate.is_file():
            candidate = ui_root / "index.html"
        if not candidate.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            size = candidate.stat().st_size
            content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
            self.send_response(HTTPStatus.OK)
            self.send_header(
                "Content-Type",
                content_type + ("; charset=utf-8" if content_type.startswith("text/") else ""),
            )
            self.send_header("Content-Length", str(size))
            self.send_header(
                "Cache-Control",
                "no-store" if candidate.name == "index.html" else "public, max-age=31536000, immutable",
            )
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            with candidate.open("rb") as handle:
                while chunk := handle.read(256 * 1024):
                    self.wfile.write(chunk)
        except (OSError, BrokenPipeError, ConnectionResetError):
            return

    def _read_json(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            return {}
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise _RequestError(400, "api_invalid_content_length", "Content-Length is invalid.") from exc
        if length < 0 or length > _MAX_REQUEST_BYTES:
            raise _RequestError(413, "api_request_too_large", "JSON request body is too large.")
        raw = self.rfile.read(length)
        if not raw:
            return {}
        content_type = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise _RequestError(415, "api_json_required", "Content-Type must be application/json.")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise _RequestError(400, "api_invalid_json", "Request body is not valid UTF-8 JSON.") from exc
        if not isinstance(payload, dict):
            raise _RequestError(400, "api_json_object_required", "JSON request body must be an object.")
        return payload

    def _write_json(self, response: ApiResponse) -> None:
        data = json.dumps(response.payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(response.status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        # Successful API requests already have structured duration/status entries
        # in runtime/logs/application.jsonl. Keep the console log quiet and only
        # retain HTTP adapter warnings/errors so slow office machines do not spend
        # time writing one line for every static asset or thumbnail request.
        try:
            status = int(args[1]) if len(args) > 1 else 0
        except (TypeError, ValueError):
            status = 0
        if status and status < 400:
            return
        stream = sys.stderr
        if stream is not None:
            stream.write("[eitaa-bridge-api] " + (format % args) + "\n")


class _RequestError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class BridgeApiHttpServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        address: tuple[str, int],
        api: BridgeApplicationApi,
        *,
        ui_root: Path | None = None,
        upload_root: Path | None = None,
        runtime_ownership: RuntimeOwnership | None = None,
    ) -> None:
        super().__init__(address, _ApiHandler)
        self.api = api
        self.ui_root = ui_root.resolve() if ui_root is not None else None
        self.upload_root = (upload_root or Path.cwd() / "runtime" / "uploads").resolve()
        self.runtime_ownership = runtime_ownership
        if self.runtime_ownership is not None:
            self.runtime_ownership.write_state(self.api, self.server_address)
            threading.Thread(
                target=self._watch_runtime_heartbeat,
                name="bridge-runtime-heartbeat-watch",
                daemon=True,
            ).start()

    def _watch_runtime_heartbeat(self) -> None:
        ownership = self.runtime_ownership
        if ownership is None or ownership.heartbeat_timeout <= 0:
            return
        interval = min(2.0, max(0.25, ownership.heartbeat_timeout / 4.0))
        while True:
            time.sleep(interval)
            if time.monotonic() - ownership.last_heartbeat <= ownership.heartbeat_timeout:
                continue
            print("api: runtime_heartbeat_expired: owned UI heartbeat stopped", file=sys.stderr)
            self.shutdown()
            return

    def server_close(self) -> None:
        try:
            super().server_close()
        finally:
            if self.runtime_ownership is not None:
                self.runtime_ownership.clear_state()


def _is_loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local Eitaa Bridge application API.")
    parser.add_argument("--config", default="bridge.json")
    parser.add_argument("--env-file")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token", help="Optional bearer token; prefer EITAA_BRIDGE_API_TOKEN in .env.")
    parser.add_argument("--ui-root", type=Path, help="Serve the built UI from this directory.")
    parser.add_argument("--open-browser", action="store_true", help="Open the local UI after the server starts.")
    parser.add_argument("--runtime-install-id", help="Install ID for an owned Office runtime.")
    parser.add_argument("--runtime-owner-root", type=Path, help="Canonical installation root for ownership checks.")
    parser.add_argument("--runtime-owner-token", help="Private token used by the owning Office launcher.")
    parser.add_argument("--runtime-state-file", type=Path, help="Owned backend state file written after binding.")
    parser.add_argument("--runtime-heartbeat-timeout", type=float, default=0.0, help="Shutdown after this many seconds without an owned UI heartbeat; zero disables it.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not 1 <= args.port <= 65535:
        print("API port must be between 1 and 65535.", file=sys.stderr)
        return 2
    api: BridgeApplicationApi | None = None
    try:
        api = BridgeApplicationApi(args.config, env_file=args.env_file, bearer_token=args.token)
        if not _is_loopback(args.host) and api.bearer_token is None:
            print("Non-loopback API binding requires EITAA_BRIDGE_API_TOKEN or --token.", file=sys.stderr)
            api.close()
            return 2
        ui_root = args.ui_root.expanduser().resolve() if args.ui_root else None
        if ui_root is not None and not (ui_root / "index.html").is_file():
            print("api: ui_root_missing: index.html was not found", file=sys.stderr)
            api.close()
            return 1
        runtime_owner_token = args.runtime_owner_token or os.getenv("EITAA_BRIDGE_RUNTIME_OWNER_TOKEN")
        runtime_values = [args.runtime_install_id, args.runtime_owner_root, runtime_owner_token, args.runtime_state_file]
        if any(runtime_values) and not all(runtime_values):
            print("api: runtime_ownership_incomplete: all runtime ownership arguments are required", file=sys.stderr)
            api.close()
            return 2
        if args.runtime_heartbeat_timeout < 0:
            print("api: runtime_heartbeat_timeout_invalid: timeout must be zero or positive", file=sys.stderr)
            api.close()
            return 2
        runtime_ownership = None
        if all(runtime_values):
            runtime_ownership = RuntimeOwnership(
                install_id=str(args.runtime_install_id),
                owner_root=args.runtime_owner_root.expanduser().resolve(),
                owner_token=str(runtime_owner_token),
                state_file=args.runtime_state_file.expanduser().resolve(),
                heartbeat_timeout=float(args.runtime_heartbeat_timeout),
            )
        server = BridgeApiHttpServer(
            (args.host, args.port),
            api,
            ui_root=ui_root,
            upload_root=Path(args.config).expanduser().resolve().parent / "runtime" / "uploads",
            runtime_ownership=runtime_ownership,
        )
    except BridgeError as exc:
        print(f"{exc.component}: {exc.code}: {exc.message}", file=sys.stderr)
        if api is not None:
            api.close()
        return 1
    except OSError as exc:
        print(f"api: bind_failed: {type(exc).__name__}", file=sys.stderr)
        if api is not None:
            api.close()
        return 1

    auth = "enabled" if api.bearer_token is not None else "disabled (loopback only)"
    print(f"Eitaa Bridge API listening on http://{args.host}:{args.port}/api/v1/health")
    print(f"Bearer authentication: {auth}")
    if args.open_browser and ui_root is not None:
        webbrowser.open(f"http://{args.host}:{args.port}/", new=1)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        api.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
