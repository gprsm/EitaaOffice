"""Validated, atomic editing of the internal HTTP deployment port."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import ipaddress
import json
from pathlib import Path
import shutil
from typing import Any, Mapping
from urllib.parse import urlsplit

from ...config import HttpDeploymentConfig
from ...errors import BridgeConfigurationError
from .loader import BridgeConfigLoader


class DeploymentPortSettings:
    """Keep the internal bind port and its same-origin allowlists in sync."""

    def __init__(self, config_path: str | Path) -> None:
        self.config_path = Path(config_path).expanduser().resolve()

    def details(self, *, restart_required: bool = False) -> dict[str, Any]:
        deployment = BridgeConfigLoader.load(self.config_path).deployment
        return {
            "mode": deployment.mode,
            "bind_host": deployment.bind_host,
            "bind_port": deployment.bind_port,
            "restart_required": restart_required,
            "proxy_update_required": deployment.mode == "web_reverse_proxy",
        }

    def update_port(
        self,
        port: object,
        *,
        confirm: bool = False,
    ) -> dict[str, Any]:
        if confirm is not True:
            raise BridgeConfigurationError(
                "Changing the internal HTTP port requires explicit confirmation.",
                code="deployment_port_confirmation_required",
            )
        if isinstance(port, bool) or not isinstance(port, int):
            raise BridgeConfigurationError(
                "HTTP bind port must be an integer.",
                code="deployment_bind_port_not_integer",
            )
        if not 1 <= port <= 65535:
            raise BridgeConfigurationError(
                "HTTP bind port must be between 1 and 65535.",
                code="deployment_bind_port_invalid",
            )
        if port == 443:
            raise BridgeConfigurationError(
                "The plain HTTP application server must not bind port 443; terminate TLS in a reverse proxy and use a separate Loopback backend port.",
                code="deployment_plain_http_443_forbidden",
            )

        config = BridgeConfigLoader.load(self.config_path)
        deployment = config.deployment
        allowed_hosts = deployment.allowed_hosts
        allowed_origins = deployment.allowed_origins
        if deployment.mode != "web_reverse_proxy":
            allowed_hosts = tuple(
                self._authority(self._authority_hostname(value), port)
                for value in deployment.allowed_hosts
            )
            allowed_origins = tuple(
                self._origin_with_port(value, port)
                for value in deployment.allowed_origins
            )
        candidate = replace(
            deployment,
            bind_port=port,
            allowed_hosts=allowed_hosts,
            allowed_origins=allowed_origins,
        )
        candidate.validate(
            app_user_auth_enabled=config.features.app_user_auth.enabled,
        )

        payload = self._load_payload()
        payload["deployment"] = self._deployment_payload(candidate)
        self._backup()
        self._write_json(payload)
        return self.details(restart_required=True)

    def _load_payload(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BridgeConfigurationError(
                "Bridge configuration could not be edited.",
                safe_context={"error_type": type(exc).__name__},
            ) from exc
        if not isinstance(payload, dict):
            raise BridgeConfigurationError("Bridge configuration root must be an object.")
        return payload

    def _backup(self) -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        directory = self.config_path.parent / "backups" / "settings"
        try:
            directory.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.config_path, directory / f"bridge.{stamp}.json")
        except OSError as exc:
            raise BridgeConfigurationError(
                "A safe configuration backup could not be created; the port was not changed.",
                code="deployment_settings_backup_failed",
                safe_context={"error_type": type(exc).__name__},
            ) from exc

    def _write_json(self, payload: Mapping[str, Any]) -> None:
        temporary = self.config_path.with_suffix(self.config_path.suffix + ".tmp")
        try:
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.replace(self.config_path)
        except OSError as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise BridgeConfigurationError(
                "The validated deployment settings could not be saved.",
                code="deployment_settings_write_failed",
                safe_context={"error_type": type(exc).__name__},
            ) from exc

    @staticmethod
    def _authority(hostname: str, port: int) -> str:
        selected = hostname.strip().lower()
        try:
            address = ipaddress.ip_address(selected)
        except ValueError:
            return f"{selected}:{port}"
        if address.version == 6:
            return f"[{address.compressed}]:{port}"
        return f"{address.compressed}:{port}"

    @staticmethod
    def _authority_hostname(value: str) -> str:
        parsed = urlsplit(f"//{value}")
        if parsed.hostname is None:
            raise BridgeConfigurationError(
                "An allowed Host could not be synchronized with the internal port.",
                code="deployment_allowed_host_invalid",
            )
        return parsed.hostname

    @classmethod
    def _origin_with_port(cls, value: str, port: int) -> str:
        parsed = urlsplit(value)
        if not parsed.scheme or parsed.hostname is None:
            raise BridgeConfigurationError(
                "An allowed Origin could not be synchronized with the internal port.",
                code="deployment_allowed_origin_invalid",
            )
        return f"{parsed.scheme.lower()}://{cls._authority(parsed.hostname, port)}"

    @staticmethod
    def _deployment_payload(deployment: HttpDeploymentConfig) -> dict[str, Any]:
        return {
            "schema_version": deployment.schema_version,
            "mode": deployment.mode,
            "bind": {
                "host": deployment.bind_host,
                "port": deployment.bind_port,
            },
            "allowed_hosts": list(deployment.allowed_hosts),
            "allowed_origins": list(deployment.allowed_origins),
            "allowed_private_client_cidrs": list(
                deployment.allowed_private_client_cidrs
            ),
            "cleartext_http_risk_acknowledgement": (
                deployment.cleartext_http_risk_acknowledgement
            ),
            "private_lan_only_acknowledgement": (
                deployment.private_lan_only_acknowledgement
            ),
            "bootstrap_admin_loopback_only": (
                deployment.bootstrap_admin_loopback_only
            ),
            "same_origin_only": deployment.same_origin_only,
            "secure_cookie": deployment.secure_cookie,
            "limits": {
                "max_json_body_bytes": deployment.limits.max_json_body_bytes,
                "max_upload_bytes": deployment.limits.max_upload_bytes,
                "request_timeout_seconds": (
                    deployment.limits.request_timeout_seconds
                ),
                "requests_per_minute": deployment.limits.requests_per_minute,
                "uploads_per_minute": deployment.limits.uploads_per_minute,
                "shutdown_grace_seconds": deployment.limits.shutdown_grace_seconds,
            },
            "reverse_proxy": {
                "enabled": deployment.reverse_proxy.enabled,
                "trusted_proxy_cidrs": list(
                    deployment.reverse_proxy.trusted_proxy_cidrs
                ),
                "required_forwarded_proto": (
                    deployment.reverse_proxy.required_forwarded_proto
                ),
                "require_forwarded_for": (
                    deployment.reverse_proxy.require_forwarded_for
                ),
            },
            "remote_messenger_auth": {
                "enabled": deployment.remote_messenger_auth.enabled,
                "cleartext_http_risk_acknowledgement": (
                    deployment.remote_messenger_auth.cleartext_http_risk_acknowledgement
                ),
            },
        }
