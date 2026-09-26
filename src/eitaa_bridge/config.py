"""Typed Bridge configuration independent of secret values."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .errors import BridgeConfigurationError

_SITE_KEY = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_ALLOWED_STATUSES = {"draft", "pending", "private", "publish"}
DEPLOYMENT_SCHEMA_VERSION = 1
WORKER_PROCESS_SCHEMA_VERSION = 1
DEPLOYMENT_MODES = frozenset(
    {"desktop_loopback", "trusted_lan_http", "web_reverse_proxy"}
)
TRUSTED_LAN_HTTP_ACKNOWLEDGEMENT = (
    "I_ACCEPT_TRUSTED_LAN_HTTP_WITHOUT_TRANSPORT_SECURITY"
)
PRIVATE_LAN_ONLY_ACKNOWLEDGEMENT = (
    "I_WILL_NOT_EXPOSE_THIS_SERVICE_TO_PUBLIC_OR_GUEST_NETWORKS"
)
REMOTE_MESSENGER_AUTH_ACKNOWLEDGEMENT = (
    "I_ACCEPT_REMOTE_MESSENGER_AUTH_OVER_CLEARTEXT_HTTP"
)
_PRIVATE_LAN_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("fc00::/7"),
)


def _safe_local_http_host(hostname: str | None) -> bool:
    host = (hostname or "").strip().lower()
    if host in {"localhost", "localhost.localdomain"}:
        return True
    if host.endswith((".localhost", ".test", ".local")):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_loopback or address.is_private


def _parse_authority(value: str) -> tuple[str, int | None]:
    selected = value.strip().lower()
    if not selected or "*" in selected or "/" in selected or "@" in selected:
        raise ValueError("invalid authority")
    try:
        parsed = urlparse("//" + selected)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("invalid authority") from exc
    if (
        not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("invalid authority")
    return parsed.hostname.lower(), port


def _format_authority(host: str, port: int) -> str:
    try:
        parsed = ipaddress.ip_address(host)
    except ValueError:
        rendered = host.lower()
    else:
        rendered = f"[{parsed.compressed}]" if parsed.version == 6 else parsed.compressed
    return f"{rendered}:{port}"


def _parse_origin(value: str) -> tuple[str, str, int]:
    selected = value.strip().lower()
    if not selected or "*" in selected:
        raise ValueError("invalid origin")
    try:
        parsed = urlparse(selected)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("invalid origin") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("invalid origin")
    return (
        parsed.scheme,
        parsed.hostname.lower(),
        port or (443 if parsed.scheme == "https" else 80),
    )


def _is_private_lan_address(address: ipaddress._BaseAddress) -> bool:
    return any(
        address.version == network.version and address in network
        for network in _PRIVATE_LAN_NETWORKS
    )


def _is_private_lan_network(network: ipaddress._BaseNetwork) -> bool:
    return any(
        network.version == allowed.version and network.subnet_of(allowed)
        for allowed in _PRIVATE_LAN_NETWORKS
    )


def _is_loopback_hostname(hostname: str) -> bool:
    if hostname == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


@dataclass(slots=True, frozen=True)
class BridgeDiagnosticsConfig:
    root: Path
    enabled: bool = True


@dataclass(slots=True, frozen=True)
class MultiSessionFeatureConfig:
    """Fail-closed configuration for the not-yet-active coordinator runtime."""

    enabled: bool = False
    legacy_default_messenger_account_id: str | None = None
    fail_closed_reason: str | None = None


@dataclass(slots=True, frozen=True)
class WorkerProcessFeatureConfig:
    """Versioned opt-in for one provider-runtime Child per MessengerAccount."""

    schema_version: int = WORKER_PROCESS_SCHEMA_VERSION
    enabled: bool = False
    startup_timeout_seconds: int = 15
    request_timeout_seconds: int = 60
    heartbeat_interval_seconds: int = 5
    heartbeat_timeout_seconds: int = 15
    heartbeat_failure_threshold: int = 3
    restart_window_seconds: int = 300
    max_restarts: int = 3
    backoff_initial_seconds: int = 2
    backoff_max_seconds: int = 60
    quarantine_seconds: int = 300
    fail_closed_reason: str | None = None


@dataclass(slots=True, frozen=True)
class AppUserAuthFeatureConfig:
    """Fail-closed local AppUser authentication policy."""

    enabled: bool = False
    self_registration_enabled: bool = True
    idle_timeout_minutes: int = 525_600
    absolute_timeout_hours: int = 8_760
    max_failed_attempts: int = 5
    lockout_minutes: int = 15
    fail_closed_reason: str | None = None


@dataclass(slots=True, frozen=True)
class RemoteMessengerAuthPolicyConfig:
    """Explicit gate for browser-driven messenger authentication."""

    enabled: bool = False
    cleartext_http_risk_acknowledgement: str | None = None


@dataclass(slots=True, frozen=True)
class HttpDeploymentLimitsConfig:
    """Bounded HTTP resource and lifecycle limits for one deployment profile."""

    max_json_body_bytes: int = 2 * 1024 * 1024
    max_upload_bytes: int = 1024 * 1024 * 1024
    request_timeout_seconds: float = 30.0
    requests_per_minute: int = 240
    uploads_per_minute: int = 12
    shutdown_grace_seconds: float = 15.0

    @classmethod
    def for_mode(cls, mode: str) -> HttpDeploymentLimitsConfig:
        return cls(
            max_upload_bytes=(
                128 * 1024 * 1024
                if mode in {"trusted_lan_http", "web_reverse_proxy"}
                else 1024 * 1024 * 1024
            )
        )

    def validate(self) -> None:
        if not 1024 <= self.max_json_body_bytes <= 16 * 1024 * 1024:
            raise BridgeConfigurationError(
                "HTTP JSON body limit must be between 1 KiB and 16 MiB.",
                code="deployment_json_body_limit_invalid",
            )
        if not self.max_json_body_bytes <= self.max_upload_bytes <= 4 * 1024 * 1024 * 1024:
            raise BridgeConfigurationError(
                "HTTP upload limit must be at least the JSON limit and no more than 4 GiB.",
                code="deployment_upload_limit_invalid",
            )
        if not 1.0 <= self.request_timeout_seconds <= 300.0:
            raise BridgeConfigurationError(
                "HTTP request timeout must be between 1 and 300 seconds.",
                code="deployment_request_timeout_invalid",
            )
        if not 1 <= self.requests_per_minute <= 100_000:
            raise BridgeConfigurationError(
                "HTTP request rate limit must be between 1 and 100000 per minute.",
                code="deployment_request_rate_limit_invalid",
            )
        if not 1 <= self.uploads_per_minute <= 10_000:
            raise BridgeConfigurationError(
                "HTTP upload rate limit must be between 1 and 10000 per minute.",
                code="deployment_upload_rate_limit_invalid",
            )
        if not 1.0 <= self.shutdown_grace_seconds <= 120.0:
            raise BridgeConfigurationError(
                "HTTP shutdown grace must be between 1 and 120 seconds.",
                code="deployment_shutdown_grace_invalid",
            )


@dataclass(slots=True, frozen=True)
class ReverseProxyConfig:
    """Fail-closed trust boundary for an external TLS terminator."""

    enabled: bool = False
    trusted_proxy_cidrs: tuple[str, ...] = ()
    required_forwarded_proto: str | None = None
    require_forwarded_for: bool = False

    def parsed_trusted_proxy_networks(self) -> tuple[ipaddress._BaseNetwork, ...]:
        return tuple(
            ipaddress.ip_network(value, strict=True)
            for value in self.trusted_proxy_cidrs
        )


@dataclass(slots=True, frozen=True)
class HttpDeploymentConfig:
    """Versioned, fail-closed HTTP bind and request-boundary contract."""

    schema_version: int = DEPLOYMENT_SCHEMA_VERSION
    mode: str = "desktop_loopback"
    bind_host: str = "127.0.0.1"
    bind_port: int = 8765
    allowed_hosts: tuple[str, ...] = ("127.0.0.1:8765", "localhost:8765")
    allowed_origins: tuple[str, ...] = (
        "http://127.0.0.1:8765",
        "http://localhost:8765",
    )
    allowed_private_client_cidrs: tuple[str, ...] = ("127.0.0.0/8", "::1/128")
    cleartext_http_risk_acknowledgement: str | None = None
    private_lan_only_acknowledgement: str | None = None
    bootstrap_admin_loopback_only: bool = True
    same_origin_only: bool = True
    secure_cookie: bool = False
    limits: HttpDeploymentLimitsConfig = HttpDeploymentLimitsConfig()
    reverse_proxy: ReverseProxyConfig = ReverseProxyConfig()
    remote_messenger_auth: RemoteMessengerAuthPolicyConfig = (
        RemoteMessengerAuthPolicyConfig()
    )

    @classmethod
    def desktop_loopback(cls) -> HttpDeploymentConfig:
        return cls(limits=HttpDeploymentLimitsConfig.for_mode("desktop_loopback"))

    @property
    def bind_authority(self) -> str:
        return _format_authority(self.bind_host, self.bind_port)

    def parsed_client_networks(self) -> tuple[ipaddress._BaseNetwork, ...]:
        return tuple(
            ipaddress.ip_network(value, strict=True)
            for value in self.allowed_private_client_cidrs
        )

    def request_host_default_port(self) -> int:
        if self.mode != "web_reverse_proxy":
            return self.bind_port
        if not self.allowed_origins:
            return 443
        return _parse_origin(self.allowed_origins[0])[2]

    def normalized_allowed_host_authorities(self) -> frozenset[str]:
        default_port = self.request_host_default_port()
        return frozenset(
            _format_authority(hostname, port or default_port)
            for hostname, port in (_parse_authority(value) for value in self.allowed_hosts)
        )

    def normalized_allowed_origins(self) -> frozenset[str]:
        return frozenset(
            f"{scheme}://{_format_authority(hostname, port)}"
            for scheme, hostname, port in (
                _parse_origin(value) for value in self.allowed_origins
            )
        )

    def validate(self, *, app_user_auth_enabled: bool) -> None:
        if self.schema_version != DEPLOYMENT_SCHEMA_VERSION:
            raise BridgeConfigurationError(
                "Unsupported HTTP deployment schema.",
                code="deployment_schema_unsupported",
                safe_context={"schema_version": self.schema_version},
            )
        if self.mode not in DEPLOYMENT_MODES:
            raise BridgeConfigurationError(
                "Unsupported HTTP deployment mode.",
                code="deployment_mode_invalid",
            )
        self.limits.validate()
        if not 1 <= self.bind_port <= 65535:
            raise BridgeConfigurationError(
                "HTTP bind port must be between 1 and 65535.",
                code="deployment_bind_port_invalid",
            )
        if self.bind_port == 443:
            raise BridgeConfigurationError(
                "The plain HTTP application server must not bind port 443; terminate TLS in a reverse proxy and use a separate Loopback backend port.",
                code="deployment_plain_http_443_forbidden",
            )
        if not self.bootstrap_admin_loopback_only:
            raise BridgeConfigurationError(
                "Initial administrator bootstrap must remain loopback-only.",
                code="deployment_bootstrap_must_be_loopback_only",
            )
        if not self.same_origin_only:
            raise BridgeConfigurationError(
                "The UI and API must remain same-origin; public CORS is not supported.",
                code="deployment_same_origin_required",
            )
        if (
            self.remote_messenger_auth.enabled
            and self.mode != "web_reverse_proxy"
        ):
            if (
                self.remote_messenger_auth.cleartext_http_risk_acknowledgement
                != REMOTE_MESSENGER_AUTH_ACKNOWLEDGEMENT
            ):
                raise BridgeConfigurationError(
                    "Remote messenger authentication requires a separate cleartext-risk acknowledgement.",
                    code="deployment_remote_messenger_auth_risk_not_acknowledged",
                )
            raise BridgeConfigurationError(
                "Remote messenger authentication is available only behind the validated HTTPS reverse-proxy profile.",
                code="deployment_remote_messenger_auth_not_available",
            )

        try:
            bind_address = ipaddress.ip_address(self.bind_host)
        except ValueError as exc:
            raise BridgeConfigurationError(
                "HTTP bind host must be an IP address literal.",
                code="deployment_bind_host_invalid",
            ) from exc

        if not self.allowed_hosts:
            raise BridgeConfigurationError(
                "At least one exact allowed Host is required.",
                code="deployment_allowed_hosts_empty",
            )
        if not self.allowed_origins:
            raise BridgeConfigurationError(
                "At least one exact allowed Origin is required.",
                code="deployment_allowed_origins_empty",
            )
        if self.mode != "web_reverse_proxy" and not self.allowed_private_client_cidrs:
            raise BridgeConfigurationError(
                "At least one allowed client CIDR is required.",
                code="deployment_allowed_client_cidrs_empty",
            )
        if len(set(self.allowed_hosts)) != len(self.allowed_hosts):
            raise BridgeConfigurationError(
                "Duplicate allowed Hosts are not permitted.",
                code="deployment_allowed_hosts_duplicate",
            )
        if len(set(self.allowed_origins)) != len(self.allowed_origins):
            raise BridgeConfigurationError(
                "Duplicate allowed Origins are not permitted.",
                code="deployment_allowed_origins_duplicate",
            )

        parsed_hosts: list[tuple[str, int | None]] = []
        for value in self.allowed_hosts:
            try:
                parsed_hosts.append(_parse_authority(value))
            except ValueError as exc:
                raise BridgeConfigurationError(
                    "Every allowed Host must be an exact host:port authority without wildcards.",
                    code="deployment_allowed_host_invalid",
                ) from exc
        parsed_origins: list[tuple[str, str, int]] = []
        for value in self.allowed_origins:
            try:
                parsed_origins.append(_parse_origin(value))
            except ValueError as exc:
                raise BridgeConfigurationError(
                    "Every allowed Origin must be an exact HTTP origin without a path or wildcard.",
                    code="deployment_allowed_origin_invalid",
                ) from exc
        try:
            networks = self.parsed_client_networks()
        except ValueError as exc:
            raise BridgeConfigurationError(
                "Every allowed client CIDR must be canonical and valid.",
                code="deployment_allowed_client_cidr_invalid",
            ) from exc

        if self.mode == "desktop_loopback":
            if self.secure_cookie:
                raise BridgeConfigurationError(
                    "desktop_loopback cannot mark an HTTP-only cookie Secure.",
                    code="deployment_desktop_secure_cookie_invalid",
                )
            if self.reverse_proxy.enabled or self.reverse_proxy.trusted_proxy_cidrs:
                raise BridgeConfigurationError(
                    "desktop_loopback cannot trust forwarded proxy headers.",
                    code="deployment_desktop_proxy_invalid",
                )
            if not bind_address.is_loopback:
                raise BridgeConfigurationError(
                    "desktop_loopback may bind only to a loopback address.",
                    code="deployment_desktop_bind_not_loopback",
                )
            for hostname, port in parsed_hosts:
                if not _is_loopback_hostname(hostname):
                    raise BridgeConfigurationError(
                        "desktop_loopback allowed Hosts must be loopback-only.",
                        code="deployment_desktop_allowed_host_not_loopback",
                    )
                if port not in {None, self.bind_port}:
                    raise BridgeConfigurationError(
                        "desktop_loopback allowed Host ports must match the bind port.",
                        code="deployment_allowed_host_port_mismatch",
                    )
            for scheme, hostname, port in parsed_origins:
                if scheme != "http":
                    raise BridgeConfigurationError(
                        "desktop_loopback Origins must use HTTP.",
                        code="deployment_desktop_origin_scheme_invalid",
                    )
                if not _is_loopback_hostname(hostname):
                    raise BridgeConfigurationError(
                        "desktop_loopback allowed Origins must be loopback-only.",
                        code="deployment_desktop_allowed_origin_not_loopback",
                    )
                if port != self.bind_port:
                    raise BridgeConfigurationError(
                        "desktop_loopback allowed Origin ports must match the bind port.",
                        code="deployment_allowed_origin_port_mismatch",
                    )
            if any(not network.is_loopback for network in networks):
                raise BridgeConfigurationError(
                    "desktop_loopback client CIDRs must be loopback-only.",
                    code="deployment_desktop_client_cidr_not_loopback",
                )
            return

        if self.mode == "web_reverse_proxy":
            if not bind_address.is_loopback:
                raise BridgeConfigurationError(
                    "web_reverse_proxy backend must bind only to Loopback.",
                    code="deployment_web_backend_not_loopback",
                )
            if not app_user_auth_enabled:
                raise BridgeConfigurationError(
                    "web_reverse_proxy requires AppUser authentication.",
                    code="deployment_app_user_auth_required",
                )
            if not self.secure_cookie:
                raise BridgeConfigurationError(
                    "web_reverse_proxy requires Secure AppUser cookies.",
                    code="deployment_web_secure_cookie_required",
                )
            if self.allowed_private_client_cidrs:
                raise BridgeConfigurationError(
                    "web_reverse_proxy must use trusted_proxy_cidrs instead of LAN client CIDRs.",
                    code="deployment_web_client_cidrs_ambiguous",
                )
            if not self.reverse_proxy.enabled:
                raise BridgeConfigurationError(
                    "web_reverse_proxy requires the explicit reverse proxy contract.",
                    code="deployment_web_proxy_required",
                )
            if self.reverse_proxy.required_forwarded_proto != "https":
                raise BridgeConfigurationError(
                    "web_reverse_proxy must require forwarded proto https.",
                    code="deployment_web_forwarded_proto_invalid",
                )
            if not self.reverse_proxy.require_forwarded_for:
                raise BridgeConfigurationError(
                    "web_reverse_proxy must require one sanitized forwarded client address.",
                    code="deployment_web_forwarded_for_required",
                )
            if not self.reverse_proxy.trusted_proxy_cidrs:
                raise BridgeConfigurationError(
                    "web_reverse_proxy requires at least one trusted proxy CIDR.",
                    code="deployment_web_trusted_proxy_empty",
                )
            try:
                trusted_proxies = self.reverse_proxy.parsed_trusted_proxy_networks()
            except ValueError as exc:
                raise BridgeConfigurationError(
                    "Every trusted proxy CIDR must be canonical and valid.",
                    code="deployment_web_trusted_proxy_invalid",
                ) from exc
            if any(not network.is_loopback for network in trusted_proxies):
                raise BridgeConfigurationError(
                    "A Loopback backend may trust only same-host Loopback proxy addresses.",
                    code="deployment_web_trusted_proxy_not_loopback",
                )
            origin_ports: set[int] = set()
            allowed_authorities: set[str] = set()
            for scheme, hostname, port in parsed_origins:
                if scheme != "https":
                    raise BridgeConfigurationError(
                        "web_reverse_proxy Origins must use HTTPS.",
                        code="deployment_web_origin_not_https",
                    )
                origin_ports.add(port)
                allowed_authorities.add(_format_authority(hostname, port))
            if len(origin_ports) != 1:
                raise BridgeConfigurationError(
                    "web_reverse_proxy Origins must share one external HTTPS port.",
                    code="deployment_web_origin_port_ambiguous",
                )
            public_port = next(iter(origin_ports))
            for hostname, port in parsed_hosts:
                if (port or 443) != public_port:
                    raise BridgeConfigurationError(
                        "Every web Host must match the external HTTPS port.",
                        code="deployment_web_host_port_mismatch",
                    )
                if _format_authority(hostname, port or 443) not in allowed_authorities:
                    raise BridgeConfigurationError(
                        "Every web Host must have one exact same-origin HTTPS Origin.",
                        code="deployment_web_host_without_origin",
                    )
            if self.cleartext_http_risk_acknowledgement is not None or self.private_lan_only_acknowledgement is not None:
                raise BridgeConfigurationError(
                    "LAN cleartext acknowledgements do not belong to web_reverse_proxy.",
                    code="deployment_web_lan_acknowledgement_invalid",
                )
            return

        if not _is_private_lan_address(bind_address):
            raise BridgeConfigurationError(
                "trusted_lan_http must bind to one concrete RFC1918 or IPv6 ULA address.",
                code="deployment_lan_bind_not_private",
            )
        if self.secure_cookie:
            raise BridgeConfigurationError(
                "trusted_lan_http cannot mark a cleartext HTTP cookie Secure.",
                code="deployment_lan_secure_cookie_invalid",
            )
        if self.reverse_proxy.enabled or self.reverse_proxy.trusted_proxy_cidrs:
            raise BridgeConfigurationError(
                "trusted_lan_http does not accept forwarded proxy headers.",
                code="deployment_lan_proxy_invalid",
            )
        if not app_user_auth_enabled:
            raise BridgeConfigurationError(
                "trusted_lan_http requires AppUser authentication.",
                code="deployment_app_user_auth_required",
            )
        if self.cleartext_http_risk_acknowledgement != TRUSTED_LAN_HTTP_ACKNOWLEDGEMENT:
            raise BridgeConfigurationError(
                "trusted_lan_http requires the exact cleartext HTTP risk acknowledgement.",
                code="deployment_cleartext_risk_not_acknowledged",
            )
        if self.private_lan_only_acknowledgement != PRIVATE_LAN_ONLY_ACKNOWLEDGEMENT:
            raise BridgeConfigurationError(
                "trusted_lan_http requires the exact private-LAN-only acknowledgement.",
                code="deployment_private_lan_not_acknowledged",
            )
        for hostname, port in parsed_hosts:
            try:
                host_address = ipaddress.ip_address(hostname)
            except ValueError as exc:
                raise BridgeConfigurationError(
                    "trusted_lan_http allowed Hosts must use private IP literals.",
                    code="deployment_lan_allowed_host_not_private_ip",
                ) from exc
            if host_address != bind_address or port != self.bind_port:
                raise BridgeConfigurationError(
                    "trusted_lan_http allowed Hosts must exactly match the configured bind address and port.",
                    code="deployment_lan_allowed_host_mismatch",
                )
        allowed_authorities = {
            _format_authority(hostname, port or self.bind_port)
            for hostname, port in parsed_hosts
        }
        for scheme, hostname, port in parsed_origins:
            if scheme != "http":
                raise BridgeConfigurationError(
                    "trusted_lan_http Origins must use HTTP.",
                    code="deployment_lan_origin_scheme_invalid",
                )
            if _format_authority(hostname, port) not in allowed_authorities:
                raise BridgeConfigurationError(
                    "Every trusted_lan_http Origin must be same-origin with an allowed Host.",
                    code="deployment_lan_origin_not_same_origin",
                )
        if any(not _is_private_lan_network(network) for network in networks):
            raise BridgeConfigurationError(
                "trusted_lan_http client CIDRs must stay inside RFC1918 or IPv6 ULA space.",
                code="deployment_lan_client_cidr_not_private",
            )
        if not any(bind_address.version == network.version and bind_address in network for network in networks):
            raise BridgeConfigurationError(
                "At least one allowed client CIDR must contain the configured LAN bind address.",
                code="deployment_lan_bind_outside_client_cidrs",
            )


@dataclass(slots=True, frozen=True)
class BridgeFeaturesConfig:
    multi_session: MultiSessionFeatureConfig
    app_user_auth: AppUserAuthFeatureConfig
    worker_process: WorkerProcessFeatureConfig


@dataclass(slots=True, frozen=True)
class CoreDependencyConfig:
    session_file: Path
    database_file: Path
    media_directory: Path
    diagnostics_root: Path
    diagnostics_enabled: bool = True
    timeout_seconds: float = 30.0

    def validate(self) -> None:
        if self.timeout_seconds <= 0:
            raise BridgeConfigurationError("Core timeout_seconds must be positive.")


@dataclass(slots=True, frozen=True)
class WordPressSiteConfig:
    site_key: str
    base_url: str
    default_status: str = "draft"
    default_category_id: int | None = None
    timeout_seconds: float = 30.0
    verify_tls: bool = True
    retry_attempts: int = 2
    username_env: str = ""
    application_password_env: str = ""
    allow_insecure_http: bool = False

    def validate(self) -> None:
        if not _SITE_KEY.fullmatch(self.site_key):
            raise BridgeConfigurationError(
                "site_key must start with a lowercase letter and contain only lowercase letters, digits, or hyphens.",
                safe_context={"site_key": self.site_key},
            )
        parsed = urlparse(self.base_url)
        local_host = _safe_local_http_host(parsed.hostname)
        if not parsed.netloc or parsed.scheme not in {"http", "https"}:
            raise BridgeConfigurationError(
                "WordPress base_url must be an absolute HTTP(S) URL.",
                safe_context={"site_key": self.site_key},
            )
        if parsed.scheme != "https" and not (self.allow_insecure_http and local_host):
            raise BridgeConfigurationError(
                "WordPress base_url must use HTTPS; insecure HTTP is allowed only for localhost, private LAN addresses, or local development hosts when explicitly enabled.",
                safe_context={"site_key": self.site_key},
            )
        if parsed.query or parsed.fragment:
            raise BridgeConfigurationError(
                "WordPress base_url cannot contain a query or fragment.",
                safe_context={"site_key": self.site_key},
            )
        if self.default_status not in _ALLOWED_STATUSES:
            raise BridgeConfigurationError(
                "Unsupported WordPress default_status.",
                safe_context={"site_key": self.site_key, "status": self.default_status},
            )
        if self.default_category_id is not None and self.default_category_id <= 0:
            raise BridgeConfigurationError("default_category_id must be positive or null.")
        if self.timeout_seconds <= 0:
            raise BridgeConfigurationError("WordPress timeout_seconds must be positive.")
        if not 0 <= self.retry_attempts <= 5:
            raise BridgeConfigurationError("retry_attempts must be between 0 and 5.")
        for name, value in (
            ("username_env", self.username_env),
            ("application_password_env", self.application_password_env),
        ):
            if not _ENV_NAME.fullmatch(value):
                raise BridgeConfigurationError(
                    f"{name} must be an uppercase environment variable name.",
                    safe_context={"site_key": self.site_key},
                )

    @property
    def normalized_base_url(self) -> str:
        return self.base_url.rstrip("/")

    def safe_summary(
        self,
        *,
        is_default: bool = False,
        credentials_configured: bool | None = None,
    ) -> dict[str, object]:
        summary: dict[str, object] = {
            "site_key": self.site_key,
            "base_url": self.normalized_base_url,
            "is_default": is_default,
            "default_status": self.default_status,
            "default_category_id": self.default_category_id,
            "verify_tls": self.verify_tls,
            "retry_attempts": self.retry_attempts,
            "allow_insecure_http": self.allow_insecure_http,
            "username_env": self.username_env,
            "application_password_env": self.application_password_env,
        }
        if credentials_configured is not None:
            summary["credentials_configured"] = credentials_configured
        return summary


@dataclass(slots=True, frozen=True)
class BridgeConfig:
    source_file: Path
    schema_version: int
    default_site_key: str
    diagnostics: BridgeDiagnosticsConfig
    features: BridgeFeaturesConfig
    deployment: HttpDeploymentConfig
    composition_state_file: Path
    core: CoreDependencyConfig
    wordpress_sites: tuple[WordPressSiteConfig, ...]
    env_file: Path

    def validate(self) -> None:
        if self.schema_version != 1:
            raise BridgeConfigurationError(
                "Unsupported Bridge configuration schema.",
                safe_context={"schema_version": self.schema_version},
            )
        self.deployment.validate(
            app_user_auth_enabled=self.features.app_user_auth.enabled
        )
        if (
            self.features.worker_process.enabled
            and not self.features.multi_session.enabled
        ):
            raise BridgeConfigurationError(
                "Worker process isolation requires multi-session account ownership.",
                code="worker_process_multi_session_required",
            )
        self.core.validate()
        if not self.wordpress_sites:
            raise BridgeConfigurationError("At least one WordPress site is required.")
        keys: set[str] = set()
        for site in self.wordpress_sites:
            site.validate()
            if site.site_key in keys:
                raise BridgeConfigurationError(
                    "Duplicate WordPress site_key.",
                    safe_context={"site_key": site.site_key},
                )
            keys.add(site.site_key)
        if self.default_site_key not in keys:
            raise BridgeConfigurationError(
                "default_site_key does not match a configured WordPress site.",
                safe_context={"site_key": self.default_site_key},
            )

    def site(self, site_key: str | None = None) -> WordPressSiteConfig:
        selected = site_key or self.default_site_key
        for site in self.wordpress_sites:
            if site.site_key == selected:
                return site
        raise BridgeConfigurationError(
            "Unknown WordPress site_key.", safe_context={"site_key": selected}
        )
