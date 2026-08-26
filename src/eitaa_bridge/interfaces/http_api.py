"""Config-bound loopback/trusted-LAN HTTP adapter for the application API."""

from __future__ import annotations

import argparse
from collections import deque
import errno
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
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlsplit

from ..application.api import APP_USER_SESSION_COOKIE, ApiResponse, BridgeApplicationApi
from ..config import HttpDeploymentConfig
from ..errors import BridgeConfigurationError, BridgeError
from ..version import __version__

_MAX_REQUEST_BYTES = 2 * 1024 * 1024
_MAX_UPLOAD_BYTES = 1024 * 1024 * 1024
_MAX_TRUSTED_LAN_UPLOAD_BYTES = 128 * 1024 * 1024
_TRUSTED_LAN_REQUESTS_PER_MINUTE = 240
_TRUSTED_LAN_UPLOADS_PER_MINUTE = 12
_TRUSTED_LAN_RATE_WINDOW_SECONDS = 60.0
_SAFE_UPLOAD_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_HASHED_UI_ASSET_NAME = re.compile(r"^.+-[A-Za-z0-9_]{8,}-?\.[A-Za-z0-9]+$")
_RUNTIME_PROTOCOL = "1"
_UI_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "worker-src 'self' blob:"
)
_API_CONTENT_SECURITY_POLICY = (
    "default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)
_PERMISSIONS_POLICY = (
    "camera=(), microphone=(), geolocation=(), payment=(), usb=(), serial=()"
)
_UNSAFE_HTTP_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_REMOTE_MESSENGER_AUTH_PATHS = frozenset(
    {
        "/api/v1/auth/request-code",
        "/api/v1/auth/submit-code",
        "/api/v1/auth/submit-password",
        "/api/v1/auth/logout",
        "/api/v1/auth/reset-local-session",
    }
)


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


@dataclass(slots=True, frozen=True)
class DeploymentRequestContext:
    rejection_code: str | None
    client_address: str
    secure_request: bool = False


@dataclass(slots=True, frozen=True)
class DeploymentRequestPolicy:
    """Exact Host/Origin/client boundary derived only from validated Config."""

    deployment: HttpDeploymentConfig
    server_port: int

    def rejection_code(
        self,
        *,
        method: str,
        path: str,
        host_header: str | None,
        origin: str | None,
        client_address: str,
        forwarded: str | None = None,
        forwarded_for: str | None = None,
        forwarded_host: str | None = None,
        forwarded_port: str | None = None,
        forwarded_proto: str | None = None,
    ) -> str | None:
        return self.evaluate(
            method=method,
            path=path,
            host_header=host_header,
            origin=origin,
            client_address=client_address,
            forwarded=forwarded,
            forwarded_for=forwarded_for,
            forwarded_host=forwarded_host,
            forwarded_port=forwarded_port,
            forwarded_proto=forwarded_proto,
        ).rejection_code

    def evaluate(
        self,
        *,
        method: str,
        path: str,
        host_header: str | None,
        origin: str | None,
        client_address: str,
        forwarded: str | None = None,
        forwarded_for: str | None = None,
        forwarded_host: str | None = None,
        forwarded_port: str | None = None,
        forwarded_proto: str | None = None,
    ) -> DeploymentRequestContext:
        def rejected(code: str) -> DeploymentRequestContext:
            return DeploymentRequestContext(code, client_address)

        try:
            peer = ipaddress.ip_address(client_address)
        except ValueError:
            return rejected("deployment_client_address_invalid")
        forwarded_values = (
            forwarded,
            forwarded_for,
            forwarded_host,
            forwarded_port,
            forwarded_proto,
        )
        if self.deployment.mode == "web_reverse_proxy":
            try:
                proxy_networks = self.deployment.reverse_proxy.parsed_trusted_proxy_networks()
            except ValueError:
                return rejected("deployment_proxy_configuration_invalid")
            if not any(
                peer.version == network.version and peer in network
                for network in proxy_networks
            ):
                return rejected("deployment_proxy_not_trusted")
            if forwarded is not None or forwarded_host is not None or forwarded_port is not None:
                return rejected("deployment_forwarded_header_unsupported")
            if (forwarded_proto or "").strip().lower() != "https":
                return rejected("deployment_forwarded_proto_rejected")
            selected_forwarded_for = (forwarded_for or "").strip()
            if (
                not selected_forwarded_for
                or "," in selected_forwarded_for
                or any(character.isspace() for character in selected_forwarded_for)
            ):
                return rejected("deployment_forwarded_for_rejected")
            try:
                client = ipaddress.ip_address(selected_forwarded_for)
            except ValueError:
                return rejected("deployment_forwarded_for_rejected")
            if client.is_unspecified or client.is_multicast:
                return rejected("deployment_forwarded_for_rejected")
        else:
            if any(value is not None for value in forwarded_values):
                return rejected("deployment_forwarded_headers_rejected")
            client = peer
        client_is_loopback = client.is_loopback
        if self.deployment.mode == "desktop_loopback":
            if not client_is_loopback:
                return rejected("deployment_client_not_loopback")
        elif self.deployment.mode == "trusted_lan_http" and not client_is_loopback and not any(
            client.version == network.version and client in network
            for network in self.deployment.parsed_client_networks()
        ):
            return rejected("deployment_client_cidr_rejected")

        host = _request_authority(
            host_header,
            default_port=self.deployment.request_host_default_port(),
        )
        if host is None:
            return rejected("deployment_host_rejected")
        host_name, host_port, host_authority = host
        if self.deployment.mode == "desktop_loopback":
            if not _is_loopback(host_name) or host_port != self.server_port:
                return rejected("deployment_host_rejected")
        elif host_authority not in self.deployment.normalized_allowed_host_authorities():
            return rejected("deployment_host_rejected")

        selected_path = urlsplit(path).path.rstrip("/") or "/"
        selected_method = method.upper().strip()
        if (
            selected_method == "POST"
            and selected_path == "/api/v2/app-auth/setup"
            and self.deployment.bootstrap_admin_loopback_only
            and not client_is_loopback
        ):
            return rejected("app_auth_bootstrap_loopback_required")
        if (
            selected_method == "POST"
            and selected_path in _REMOTE_MESSENGER_AUTH_PATHS
            and not self.deployment.remote_messenger_auth.enabled
            and not client_is_loopback
        ):
            return rejected("remote_messenger_auth_disabled")

        if origin:
            selected_origin = _request_origin(origin)
            if selected_origin is None:
                return rejected("deployment_origin_rejected")
            origin_host, origin_port, normalized_origin = selected_origin
            if self.deployment.mode == "desktop_loopback":
                if (
                    not _is_loopback(origin_host)
                    or origin_port != self.server_port
                    or origin_port != host_port
                    or _network_authority(origin_host, origin_port) != host_authority
                ):
                    return rejected("deployment_origin_rejected")
            elif (
                normalized_origin not in self.deployment.normalized_allowed_origins()
                or _network_authority(origin_host, origin_port) != host_authority
            ):
                return rejected("deployment_origin_rejected")
        elif selected_method in _UNSAFE_HTTP_METHODS and (
            self.deployment.mode in {"trusted_lan_http", "web_reverse_proxy"}
            or not client_is_loopback
        ):
            return rejected("deployment_origin_required")
        return DeploymentRequestContext(
            None,
            client.compressed,
            secure_request=self.deployment.mode == "web_reverse_proxy",
        )


class TrustedLanAbuseLimiter:
    """Small bounded, source-address rate gate for the explicit LAN mode."""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._events: dict[tuple[str, str], deque[float]] = {}

    def allow(
        self,
        client_address: str,
        bucket: str,
        *,
        limit: int,
        window_seconds: float = _TRUSTED_LAN_RATE_WINDOW_SECONDS,
    ) -> bool:
        try:
            normalized = ipaddress.ip_address(client_address).compressed
        except ValueError:
            return False
        now = float(self._clock())
        cutoff = now - float(window_seconds)
        key = (normalized, bucket)
        with self._lock:
            events = self._events.setdefault(key, deque())
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                return False
            events.append(now)
            if len(self._events) > 4096:
                self._events = {
                    item_key: item_events
                    for item_key, item_events in self._events.items()
                    if item_events and item_events[-1] > cutoff
                }
                while len(self._events) > 4096:
                    self._events.pop(next(iter(self._events)))
            return True


@dataclass(slots=True)
class ServerLifecycleState:
    """Thread-safe readiness state with a deliberately small public payload."""

    _status: str = "starting"
    _reason: str = "startup_in_progress"
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def mark_ready(self) -> None:
        with self._lock:
            self._status = "ready"
            self._reason = "ready"

    def mark_not_ready(self, reason: str) -> None:
        selected = reason if re.fullmatch(r"[a-z0-9_]{1,64}", reason) else "not_ready"
        with self._lock:
            self._status = "not_ready"
            self._reason = selected

    def snapshot(self, *, deployment_mode: str) -> tuple[int, dict[str, Any]]:
        with self._lock:
            ready = self._status == "ready"
            reason = self._reason
        return (
            HTTPStatus.OK if ready else HTTPStatus.SERVICE_UNAVAILABLE,
            {
                "ok": ready,
                "service": "eitaa-bridge-api",
                "status": "ready" if ready else "not_ready",
                "deployment_mode": deployment_mode,
                "reason": reason,
            },
        )


def _network_authority(host: str, port: int) -> str:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        rendered = host.lower()
    else:
        rendered = f"[{address.compressed}]" if address.version == 6 else address.compressed
    return f"{rendered}:{port}"


def _request_authority(
    value: str | None,
    *,
    default_port: int,
) -> tuple[str, int, str] | None:
    selected = (value or "").strip().lower()
    if (
        not selected
        or selected.endswith(":")
        or any(character.isspace() or ord(character) < 33 or ord(character) == 127 for character in selected)
        or any(character in selected for character in "*/@\\,;")
    ):
        return None
    try:
        parsed = urlsplit("//" + selected)
        port = parsed.port or default_port
    except ValueError:
        return None
    if (
        not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        return None
    hostname = parsed.hostname.lower()
    return hostname, port, _network_authority(hostname, port)


def _request_origin(value: str) -> tuple[str, int, str] | None:
    selected = value.strip().lower()
    if (
        not selected
        or selected.endswith(":")
        or any(character.isspace() or ord(character) < 33 or ord(character) == 127 for character in selected)
        or any(character in selected for character in "*\\,;")
    ):
        return None
    try:
        parsed = urlsplit(selected)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        return None
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        return None
    hostname = parsed.hostname.lower()
    return hostname, port, f"{parsed.scheme}://{_network_authority(hostname, port)}"


class _ApiHandler(BaseHTTPRequestHandler):
    server_version = "EitaaBridgeAPI/0.7"
    sys_version = ""

    @property
    def api(self) -> BridgeApplicationApi:
        return self.server.api  # type: ignore[attr-defined]

    @property
    def deployment_policy(self) -> DeploymentRequestPolicy:
        return self.server.deployment_policy  # type: ignore[attr-defined]

    def do_GET(self) -> None:  # noqa: N802
        if not self._enforce_deployment_policy("GET"):
            return
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
        if not self._enforce_deployment_policy("POST"):
            return
        request_path = urlsplit(self.path).path
        if request_path == "/api/v1/runtime/heartbeat":
            self._runtime_heartbeat()
        elif request_path == "/api/v1/runtime/shutdown":
            self._runtime_shutdown()
        elif request_path == "/api/v1/files/upload":
            self._upload_file()
        else:
            self._dispatch("POST")

    def do_HEAD(self) -> None:  # noqa: N802
        """Reject HEAD without dispatching application code or mutating state."""

        if not self._enforce_deployment_policy("HEAD"):
            return
        self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
        self.send_header("Allow", "GET, POST, OPTIONS")
        self.send_header("Content-Length", "0")
        self._send_security_headers(
            cache_control="no-store, max-age=0",
            content_security_policy=_API_CONTENT_SECURITY_POLICY,
        )
        self.end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        if not self._enforce_deployment_policy("OPTIONS"):
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Allow", "GET, POST, OPTIONS")
        self._send_security_headers(
            cache_control="no-store, max-age=0",
            content_security_policy=_API_CONTENT_SECURITY_POLICY,
        )
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
        if not ownership.authorized(self._single_header("X-Eitaa-Runtime-Token")):
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
                authorization=self._single_header("Authorization"),
                app_session_token=self._app_session_token(),
                csrf_token=self._single_header("X-CSRF-Token"),
                client_kind=self._client_kind(),
                client_address=getattr(
                    self,
                    "_deployment_client_address",
                    str(self.client_address[0]),
                ),
                messenger_account_id=self._single_header(
                    "X-Eitaa-Messenger-Account"
                ),
                correlation_id=self._single_header("X-Eitaa-Correlation-Id"),
            )
            request_path = urlsplit(self.path).path.rstrip("/") or "/"
            if (
                method == "GET"
                and request_path == "/api/v1/readiness"
                and response.status == HTTPStatus.OK
            ):
                response = self.server.readiness_response()  # type: ignore[attr-defined]
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
        parsed = urlsplit(self.path)
        query = parse_qs(parsed.query, keep_blank_values=True)
        if "messenger_account_id" in query or "account_id" in query:
            self._write_json(
                ApiResponse(
                    400,
                    {
                        "ok": False,
                        "error": {
                            "component": "api",
                            "error_code": "api_account_context_not_writable",
                            "message": "Account context cannot be supplied in a URL.",
                            "safe_context": {},
                            "debug_file": None,
                        },
                    },
                )
            )
            return
        token = parsed.path.rsplit("/", 1)[-1].strip().lower()
        authorization = self.api.authorize_media_cache_token(
            token,
            authorization=self._single_header("Authorization"),
            app_session_token=self._app_session_token(),
            client_kind=self._client_kind(),
        )
        if authorization.status >= 400:
            self._write_json(authorization)
            return
        resolved = self.api.resolve_media_cache_file(
            token,
            messenger_account_id=authorization.payload.get("messenger_account_id"),
        )
        if resolved is None:
            try:
                remote = self.api.read_remote_media_cache_chunk(
                    token,
                    messenger_account_id=authorization.payload.get(
                        "messenger_account_id"
                    ),
                    offset=0,
                )
            except BridgeError as exc:
                self._write_json(self.api._error_response(exc))
                return
            if remote is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            data, mime_type, total, offset, eof = remote
            try:
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", mime_type)
                self.send_header("Content-Length", str(total))
                self._send_security_headers(
                    cache_control="no-store, max-age=0",
                    content_security_policy=_API_CONTENT_SECURITY_POLICY,
                )
                self.end_headers()
                self.wfile.write(data)
                while not eof:
                    remote = self.api.read_remote_media_cache_chunk(
                        token,
                        messenger_account_id=authorization.payload.get(
                            "messenger_account_id"
                        ),
                        offset=offset,
                    )
                    if remote is None:
                        return
                    data, next_mime, next_total, offset, eof = remote
                    if next_mime != mime_type or next_total != total:
                        return
                    self.wfile.write(data)
            except (
                BridgeError,
                OSError,
                BrokenPipeError,
                ConnectionResetError,
            ):
                return
            return
        path, mime_type = resolved
        try:
            size = path.stat().st_size
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(size))
            self._send_security_headers(
                cache_control="no-store, max-age=0",
                content_security_policy=_API_CONTENT_SECURITY_POLICY,
            )
            self.end_headers()
            with path.open("rb") as handle:
                while chunk := handle.read(256 * 1024):
                    self.wfile.write(chunk)
        except (OSError, BrokenPipeError, ConnectionResetError):
            return

    def _upload_file(self) -> None:
        authorization = self.api.authorize_local_resource(
            "POST",
            authorization=self._single_header("Authorization"),
            app_session_token=self._app_session_token(),
            csrf_token=self._single_header("X-CSRF-Token"),
            client_kind=self._client_kind(),
            messenger_account_id=self._single_header(
                "X-Eitaa-Messenger-Account"
            ),
        )
        if authorization.status >= 400:
            self._write_json(authorization)
            return
        if self._single_header("Transfer-Encoding") is not None:
            self._write_json(
                ApiResponse(
                    400,
                    {
                        "ok": False,
                        "error": {
                            "component": "api",
                            "error_code": "file_upload_transfer_encoding_unsupported",
                            "message": "Upload transfer encoding is not supported.",
                            "safe_context": {},
                        },
                    },
                )
            )
            return
        content_type = (
            self._single_header("Content-Type") or ""
        ).split(";", 1)[0].strip().lower()
        if (
            self.api.config.deployment.mode
            in {"trusted_lan_http", "web_reverse_proxy"}
            and content_type != "application/octet-stream"
        ):
            self._write_json(
                ApiResponse(
                    415,
                    {
                        "ok": False,
                        "error": {
                            "component": "api",
                            "error_code": "file_upload_content_type_invalid",
                            "message": "LAN uploads must use application/octet-stream.",
                            "safe_context": {},
                        },
                    },
                )
            )
            return
        raw_length = self._single_header("Content-Length")
        try:
            length = int(raw_length or "-1")
        except ValueError:
            length = -1
        max_upload_bytes = self.api.config.deployment.limits.max_upload_bytes
        if length < 0 or length > max_upload_bytes:
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
        encoded_name = self._single_header("X-Eitaa-Filename") or "upload.bin"
        original = Path(unquote(encoded_name)).name.strip() or "upload.bin"
        safe_name = _SAFE_UPLOAD_NAME.sub("_", original)[:180] or "upload.bin"
        selected_account_id = authorization.payload.get("messenger_account_id")
        upload_root = (
            self.api.upload_root_for_account(selected_account_id)
            if selected_account_id
            else self.server.upload_root  # type: ignore[attr-defined]
        )
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
            immutable_asset = bool(
                candidate.parent == (ui_root / "assets").resolve()
                and _HASHED_UI_ASSET_NAME.fullmatch(candidate.name)
            )
            self._send_security_headers(
                cache_control=(
                    "public, max-age=31536000, immutable"
                    if immutable_asset
                    else "no-store, max-age=0"
                ),
                content_security_policy=_UI_CONTENT_SECURITY_POLICY,
            )
            self.end_headers()
            with candidate.open("rb") as handle:
                while chunk := handle.read(256 * 1024):
                    self.wfile.write(chunk)
        except (OSError, BrokenPipeError, ConnectionResetError):
            return

    def _read_json(self) -> dict[str, Any]:
        if self._single_header("Transfer-Encoding") is not None:
            raise _RequestError(
                400,
                "api_transfer_encoding_unsupported",
                "Transfer-Encoding is not supported.",
            )
        raw_length = self._single_header("Content-Length")
        if raw_length is None:
            return {}
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise _RequestError(400, "api_invalid_content_length", "Content-Length is invalid.") from exc
        if length < 0 or length > self.api.config.deployment.limits.max_json_body_bytes:
            raise _RequestError(413, "api_request_too_large", "JSON request body is too large.")
        raw = self.rfile.read(length)
        if not raw:
            return {}
        content_type = (self._single_header("Content-Type") or "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise _RequestError(415, "api_json_required", "Content-Type must be application/json.")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise _RequestError(400, "api_invalid_json", "Request body is not valid UTF-8 JSON.") from exc
        if not isinstance(payload, dict):
            raise _RequestError(400, "api_json_object_required", "JSON request body must be an object.")
        return payload

    def _app_session_token(self) -> str | None:
        raw_cookie = self._single_header("Cookie")
        if not raw_cookie:
            return None
        parsed = SimpleCookie()
        try:
            parsed.load(raw_cookie)
        except CookieError:
            return None
        morsel = parsed.get(APP_USER_SESSION_COOKIE)
        return morsel.value if morsel is not None else None

    def _client_kind(self) -> str:
        selected = (self._single_header("X-Eitaa-Client-Kind") or "browser").strip().lower()
        return selected if selected in {"electron", "browser", "api", "test"} else "browser"

    def _single_header(self, name: str) -> str | None:
        values = self.headers.get_all(name) or []
        if not values:
            return None
        if len(values) != 1:
            return "\x00multiple-header-values"
        return values[0]

    def _enforce_deployment_policy(self, method: str) -> bool:
        context = self.deployment_policy.evaluate(
            method=method,
            path=self.path,
            host_header=self._single_header("Host"),
            origin=self._single_header("Origin"),
            client_address=str(self.client_address[0]),
            forwarded=self._single_header("Forwarded"),
            forwarded_for=self._single_header("X-Forwarded-For"),
            forwarded_host=self._single_header("X-Forwarded-Host"),
            forwarded_port=self._single_header("X-Forwarded-Port"),
            forwarded_proto=self._single_header("X-Forwarded-Proto"),
        )
        code = context.rejection_code
        if code is not None:
            self._write_json(
                ApiResponse(
                    403,
                    {
                        "ok": False,
                        "error": {
                            "component": "deployment",
                            "error_code": code,
                            "message": "درخواست با سیاست استقرار HTTP سازگار نیست.",
                            "safe_context": {"mode": self.api.config.deployment.mode},
                            "debug_file": None,
                        },
                    },
                )
            )
            return False
        self._deployment_client_address = context.client_address
        if self.api.config.deployment.mode not in {
            "trusted_lan_http",
            "web_reverse_proxy",
        }:
            return True
        limiter: TrustedLanAbuseLimiter = self.server.lan_abuse_limiter  # type: ignore[attr-defined]
        client_address = context.client_address
        limits = self.api.config.deployment.limits
        if not limiter.allow(
            client_address,
            "all",
            limit=limits.requests_per_minute,
        ):
            self._write_rate_limit_error("lan_request_rate_limited")
            return False
        request_path = urlsplit(self.path).path
        if (
            method.upper().strip() == "POST"
            and request_path == "/api/v1/files/upload"
            and not limiter.allow(
                client_address,
                "upload",
                limit=limits.uploads_per_minute,
            )
        ):
            self._write_rate_limit_error("lan_upload_rate_limited")
            return False
        return True

    def _write_rate_limit_error(self, code: str) -> None:
        self._write_json(
            ApiResponse(
                429,
                {
                    "ok": False,
                    "error": {
                        "component": "deployment",
                        "error_code": code,
                        "message": "درخواست‌های این Client موقتاً محدود شده‌اند.",
                        "safe_context": {
                            "mode": self.api.config.deployment.mode
                        },
                        "debug_file": None,
                    },
                },
            )
        )

    def _send_security_headers(
        self,
        *,
        cache_control: str,
        content_security_policy: str,
    ) -> None:
        self.send_header("Cache-Control", cache_control)
        if "no-store" in cache_control:
            self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", content_security_policy)
        self.send_header("Permissions-Policy", _PERMISSIONS_POLICY)
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("X-Permitted-Cross-Domain-Policies", "none")
        self.send_header("X-XSS-Protection", "0")
        if self.api.config.deployment.mode == "web_reverse_proxy":
            self.send_header(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )

    def _write_json(self, response: ApiResponse) -> None:
        data = json.dumps(response.payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(response.status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self._send_security_headers(
            cache_control="no-store, max-age=0",
            content_security_policy=_API_CONTENT_SECURITY_POLICY,
        )
        for name, value in response.headers.items():
            if name.lower() == "set-cookie":
                self.send_header("Set-Cookie", value)
        self.end_headers()
        self.wfile.write(data)

    def send_error(
        self,
        code: int,
        message: str | None = None,
        explain: str | None = None,
    ) -> None:
        del message, explain
        self._write_json(
            ApiResponse(
                int(code),
                {
                    "ok": False,
                    "error": {
                        "component": "http",
                        "error_code": f"http_{int(code)}",
                        "message": "HTTP request could not be completed.",
                        "safe_context": {},
                    },
                },
            )
        )

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
            stream.write(
                f"[eitaa-bridge-api] HTTP request rejected with status {status or 'unknown'}\n"
            )


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
        self.lifecycle = ServerLifecycleState()
        super().__init__(address, _ApiHandler)
        self.api = api
        self.ui_root = ui_root.resolve() if ui_root is not None else None
        self.upload_root = (upload_root or api.upload_root).resolve()
        self.runtime_ownership = runtime_ownership
        self.lan_abuse_limiter = TrustedLanAbuseLimiter()
        self.request_timeout_seconds = api.config.deployment.limits.request_timeout_seconds
        self.shutdown_grace_seconds = api.config.deployment.limits.shutdown_grace_seconds
        self._request_condition = threading.Condition()
        self._active_requests = 0
        self.last_shutdown_drained: bool | None = None
        self.deployment_policy = DeploymentRequestPolicy(
            api.config.deployment,
            int(self.server_address[1]),
        )
        if self.runtime_ownership is not None:
            self.runtime_ownership.write_state(self.api, self.server_address)
            threading.Thread(
                target=self._watch_runtime_heartbeat,
                name="bridge-runtime-heartbeat-watch",
                daemon=True,
            ).start()
        self.lifecycle.mark_ready()

    def get_request(self):
        request, client_address = super().get_request()
        request.settimeout(self.request_timeout_seconds)
        return request, client_address

    def process_request_thread(self, request, client_address) -> None:
        with self._request_condition:
            self._active_requests += 1
        try:
            super().process_request_thread(request, client_address)
        finally:
            with self._request_condition:
                self._active_requests -= 1
                self._request_condition.notify_all()

    def _wait_for_request_drain(self) -> bool:
        deadline = time.monotonic() + self.shutdown_grace_seconds
        with self._request_condition:
            while self._active_requests:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._request_condition.wait(timeout=remaining)
        return True

    def set_not_ready(self, reason: str) -> None:
        self.lifecycle.mark_not_ready(reason)

    def readiness_response(self) -> ApiResponse:
        status, payload = self.lifecycle.snapshot(
            deployment_mode=self.api.config.deployment.mode
        )
        return ApiResponse(int(status), payload)

    def shutdown(self) -> None:
        self.lifecycle.mark_not_ready("shutting_down")
        super().shutdown()

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
        self.lifecycle.mark_not_ready("stopped")
        try:
            super().server_close()
            self.last_shutdown_drained = self._wait_for_request_drain()
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
    parser.add_argument(
        "--host",
        help="Compatibility override; it must exactly match deployment.bind.host.",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="Compatibility override; it must exactly match deployment.bind.port.",
    )
    parser.add_argument("--token", help="Optional bearer token; prefer EITAA_BRIDGE_API_TOKEN in .env.")
    parser.add_argument("--ui-root", type=Path, help="Serve the built UI from this directory.")
    parser.add_argument("--open-browser", action="store_true", help="Open the local UI after the server starts.")
    parser.add_argument("--runtime-install-id", help="Install ID for an owned Office runtime.")
    parser.add_argument("--runtime-owner-root", type=Path, help="Canonical installation root for ownership checks.")
    parser.add_argument("--runtime-owner-token", help="Private token used by the owning Office launcher.")
    parser.add_argument("--runtime-state-file", type=Path, help="Owned backend state file written after binding.")
    parser.add_argument("--runtime-heartbeat-timeout", type=float, default=0.0, help="Shutdown after this many seconds without an owned UI heartbeat; zero disables it.")
    return parser


def _resolve_server_bind(
    deployment: HttpDeploymentConfig,
    *,
    host_override: str | None,
    port_override: int | None,
) -> tuple[str, int]:
    configured_host = deployment.bind_host.strip().lower()
    if host_override is not None and host_override.strip().lower() != configured_host:
        raise BridgeConfigurationError(
            "The command-line host must exactly match deployment.bind.host.",
            code="deployment_bind_host_override_mismatch",
            safe_context={"mode": deployment.mode},
        )
    if port_override is not None and port_override != deployment.bind_port:
        raise BridgeConfigurationError(
            "The command-line port must exactly match deployment.bind.port.",
            code="deployment_bind_port_override_mismatch",
            safe_context={"mode": deployment.mode},
        )
    return configured_host, deployment.bind_port


def _http_url_host(host: str) -> str:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return host
    return f"[{address.compressed}]" if address.version == 6 else address.compressed


def _bind_error_code(exc: OSError) -> str:
    if exc.errno in {errno.EADDRINUSE, 10048} or getattr(exc, "winerror", None) == 10048:
        return "port_conflict"
    return "bind_failed"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    api: BridgeApplicationApi | None = None
    try:
        api = BridgeApplicationApi(args.config, env_file=args.env_file, bearer_token=args.token)
        bind_host, bind_port = _resolve_server_bind(
            api.config.deployment,
            host_override=args.host,
            port_override=args.port,
        )
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
            (bind_host, bind_port),
            api,
            ui_root=ui_root,
            upload_root=api.upload_root,
            runtime_ownership=runtime_ownership,
        )
    except BridgeError as exc:
        print(f"{exc.component}: {exc.code}: {exc.message}", file=sys.stderr)
        if api is not None:
            api.close()
        return 1
    except OSError as exc:
        print(f"api: {_bind_error_code(exc)}: {type(exc).__name__}", file=sys.stderr)
        if api is not None:
            api.close()
        return 1

    auth = "enabled" if api.bearer_token is not None else "not configured"
    url_host = _http_url_host(bind_host)
    print(f"Eitaa Bridge API listening on http://{url_host}:{bind_port}/api/v1/health")
    print(f"Deployment mode: {api.config.deployment.mode}")
    print(f"Bearer authentication: {auth}")
    if args.open_browser and ui_root is not None:
        webbrowser.open(f"http://{url_host}:{bind_port}/", new=1)
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
