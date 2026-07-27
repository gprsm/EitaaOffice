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


@dataclass(slots=True, frozen=True)
class BridgeDiagnosticsConfig:
    root: Path
    enabled: bool = True


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
