from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...config import (
    BridgeConfig,
    BridgeDiagnosticsConfig,
    CoreDependencyConfig,
    WordPressSiteConfig,
)
from ...errors import BridgeConfigurationError


class BridgeConfigLoader:
    @classmethod
    def load(cls, path: str | Path = "bridge.json", *, env_file: str | Path | None = None) -> BridgeConfig:
        source = Path(path).expanduser().resolve()
        try:
            payload = json.loads(source.read_text(encoding="utf-8-sig"))
        except FileNotFoundError as exc:
            raise BridgeConfigurationError(
                "Bridge configuration file was not found.",
                safe_context={"file_name": source.name},
            ) from exc
        except json.JSONDecodeError as exc:
            raise BridgeConfigurationError(
                "Bridge configuration is not valid JSON.",
                safe_context={"line": exc.lineno, "column": exc.colno},
            ) from exc
        except OSError as exc:
            raise BridgeConfigurationError(
                "Bridge configuration could not be read.",
                safe_context={"error_type": type(exc).__name__},
            ) from exc
        if not isinstance(payload, dict):
            raise BridgeConfigurationError("Bridge configuration root must be an object.")
        base = source.parent
        bridge_data = cls._mapping(payload, "bridge")
        core_data = cls._mapping(payload, "core")
        sites_data = payload.get("wordpress_sites")
        if not isinstance(sites_data, list):
            raise BridgeConfigurationError("wordpress_sites must be an array.")
        sites = tuple(cls._site(item) for item in sites_data)
        config = BridgeConfig(
            source_file=source,
            schema_version=cls._integer(payload, "schema_version"),
            default_site_key=cls._string(payload, "default_site_key"),
            diagnostics=BridgeDiagnosticsConfig(
                root=cls._path(base, bridge_data, "diagnostics_root"),
                enabled=cls._boolean(bridge_data, "diagnostics_enabled", True),
            ),
            composition_state_file=cls._optional_path(
                base, bridge_data, "composition_state_file", "data/bridge_compositions.json"
            ),
            core=CoreDependencyConfig(
                session_file=cls._path(base, core_data, "session_file"),
                database_file=cls._path(base, core_data, "database_file"),
                media_directory=cls._path(base, core_data, "media_directory"),
                diagnostics_root=cls._path(base, core_data, "diagnostics_root"),
                diagnostics_enabled=cls._boolean(core_data, "diagnostics_enabled", True),
                timeout_seconds=cls._number(core_data, "timeout_seconds", 30.0),
            ),
            wordpress_sites=sites,
            env_file=(Path(env_file).expanduser().resolve() if env_file else (base / ".env").resolve()),
        )
        config.validate()
        return config

    @staticmethod
    def _mapping(payload: dict[str, Any], key: str) -> dict[str, Any]:
        value = payload.get(key)
        if not isinstance(value, dict):
            raise BridgeConfigurationError(f"{key} must be an object.")
        return value

    @staticmethod
    def _site(value: Any) -> WordPressSiteConfig:
        if not isinstance(value, dict):
            raise BridgeConfigurationError("Each WordPress site must be an object.")
        try:
            return WordPressSiteConfig(
                site_key=str(value["site_key"]),
                base_url=str(value["base_url"]),
                default_status=str(value.get("default_status", "draft")),
                default_category_id=(
                    int(value["default_category_id"])
                    if value.get("default_category_id") is not None
                    else None
                ),
                timeout_seconds=float(value.get("timeout_seconds", 30.0)),
                verify_tls=bool(value.get("verify_tls", True)),
                retry_attempts=int(value.get("retry_attempts", 2)),
                username_env=str(value["username_env"]),
                application_password_env=str(value["application_password_env"]),
                allow_insecure_http=bool(value.get("allow_insecure_http", False)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise BridgeConfigurationError(
                "Invalid WordPress site configuration.",
                safe_context={"error_type": type(exc).__name__},
            ) from exc

    @staticmethod
    def _optional_path(base: Path, payload: dict[str, Any], key: str, default: str) -> Path:
        value = payload.get(key, default)
        if not isinstance(value, str) or not value.strip():
            raise BridgeConfigurationError(f"{key} must be a non-empty path string.")
        path = Path(value).expanduser()
        return (path if path.is_absolute() else base / path).resolve()

    @staticmethod
    def _path(base: Path, payload: dict[str, Any], key: str) -> Path:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise BridgeConfigurationError(f"{key} must be a non-empty path string.")
        path = Path(value).expanduser()
        return (path if path.is_absolute() else base / path).resolve()

    @staticmethod
    def _string(payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise BridgeConfigurationError(f"{key} must be a non-empty string.")
        return value.strip()

    @staticmethod
    def _integer(payload: dict[str, Any], key: str) -> int:
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise BridgeConfigurationError(f"{key} must be an integer.")
        return value

    @staticmethod
    def _number(payload: dict[str, Any], key: str, default: float) -> float:
        value = payload.get(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise BridgeConfigurationError(f"{key} must be a number.")
        return float(value)

    @staticmethod
    def _boolean(payload: dict[str, Any], key: str, default: bool) -> bool:
        value = payload.get(key, default)
        if not isinstance(value, bool):
            raise BridgeConfigurationError(f"{key} must be boolean.")
        return value
