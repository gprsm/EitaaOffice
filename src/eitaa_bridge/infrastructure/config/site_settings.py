"""Safe local editing of WordPress site configuration and credentials."""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ...config import WordPressSiteConfig
from ...errors import BridgeConfigurationError

_ENV_SAFE = re.compile(r"^[A-Z_][A-Z0-9_]*$")


class WordPressSiteSettings:
    """Atomically update Bridge site settings without exposing saved secrets."""

    def __init__(self, config_path: str | Path, env_path: str | Path) -> None:
        self.config_path = Path(config_path).expanduser().resolve()
        self.env_path = Path(env_path).expanduser().resolve()

    def details(self) -> dict[str, Any]:
        payload = self._load_payload()
        env = self._load_env()
        sites: list[dict[str, Any]] = []
        default_key = str(payload.get("default_site_key", ""))
        for raw in payload.get("wordpress_sites", []):
            if not isinstance(raw, dict):
                continue
            username_env = str(raw.get("username_env", ""))
            password_env = str(raw.get("application_password_env", ""))
            sites.append({
                "site_key": str(raw.get("site_key", "")),
                "base_url": str(raw.get("base_url", "")),
                "is_default": str(raw.get("site_key", "")) == default_key,
                "default_status": str(raw.get("default_status", "draft")),
                "default_category_id": raw.get("default_category_id"),
                "timeout_seconds": float(raw.get("timeout_seconds", 30.0)),
                "verify_tls": bool(raw.get("verify_tls", True)),
                "retry_attempts": int(raw.get("retry_attempts", 2)),
                "allow_insecure_http": bool(raw.get("allow_insecure_http", False)),
                "username_env": username_env,
                "application_password_env": password_env,
                "username_configured": bool(env.get(username_env, "").strip()),
                "application_password_configured": bool(env.get(password_env, "").strip()),
                "credentials_configured": bool(env.get(username_env, "").strip() and env.get(password_env, "").strip()),
            })
        return {"default_site_key": default_key, "sites": sites}

    def upsert(self, request: Mapping[str, Any]) -> dict[str, Any]:
        site_key = str(request.get("site_key", "")).strip().lower()
        suffix = site_key.upper().replace("-", "_")
        username_env = str(request.get("username_env") or f"EITAA_BRIDGE_WP_{suffix}_USERNAME").strip()
        password_env = str(request.get("application_password_env") or f"EITAA_BRIDGE_WP_{suffix}_APP_PASSWORD").strip()
        candidate = WordPressSiteConfig(
            site_key=site_key,
            base_url=str(request.get("base_url", "")).strip(),
            default_status=str(request.get("default_status", "draft")).strip(),
            default_category_id=(
                int(request["default_category_id"])
                if request.get("default_category_id") not in (None, "")
                else None
            ),
            timeout_seconds=float(request.get("timeout_seconds", 30.0)),
            verify_tls=bool(request.get("verify_tls", True)),
            retry_attempts=int(request.get("retry_attempts", 2)),
            username_env=username_env,
            application_password_env=password_env,
            allow_insecure_http=bool(request.get("allow_insecure_http", False)),
        )
        candidate.validate()

        payload = self._load_payload()
        sites = payload.get("wordpress_sites")
        if not isinstance(sites, list):
            raise BridgeConfigurationError("wordpress_sites must be an array.")
        raw_site = {
            "site_key": candidate.site_key,
            "base_url": candidate.normalized_base_url,
            "default_status": candidate.default_status,
            "default_category_id": candidate.default_category_id,
            "timeout_seconds": candidate.timeout_seconds,
            "verify_tls": candidate.verify_tls,
            "retry_attempts": candidate.retry_attempts,
            "username_env": candidate.username_env,
            "application_password_env": candidate.application_password_env,
        }
        if candidate.allow_insecure_http:
            raw_site["allow_insecure_http"] = True
        replaced = False
        for index, item in enumerate(sites):
            if isinstance(item, dict) and str(item.get("site_key", "")) == site_key:
                sites[index] = raw_site
                replaced = True
                break
        if not replaced:
            sites.append(raw_site)
        if bool(request.get("is_default")) or not str(payload.get("default_site_key", "")).strip():
            payload["default_site_key"] = site_key

        env_updates: dict[str, str] = {}
        if "username" in request:
            env_updates[username_env] = str(request.get("username", "")).strip()
        if "application_password" in request:
            env_updates[password_env] = str(request.get("application_password", "")).strip()
        self._validate_env_updates(env_updates)

        self._backup()
        self._write_json(payload)
        if env_updates:
            self._write_env(env_updates)
            for key, value in env_updates.items():
                os.environ[key] = value
        return self.details()

    def set_default(self, site_key: str) -> dict[str, Any]:
        payload = self._load_payload()
        keys = {
            str(item.get("site_key", ""))
            for item in payload.get("wordpress_sites", [])
            if isinstance(item, dict)
        }
        if site_key not in keys:
            raise BridgeConfigurationError("Unknown WordPress site_key.", safe_context={"site_key": site_key})
        payload["default_site_key"] = site_key
        self._backup()
        self._write_json(payload)
        return self.details()

    def delete(self, site_key: str, *, confirm: bool = False) -> dict[str, Any]:
        if not confirm:
            raise BridgeConfigurationError("Deleting a WordPress site requires explicit confirmation.")
        payload = self._load_payload()
        sites = [
            item for item in payload.get("wordpress_sites", [])
            if not (isinstance(item, dict) and str(item.get("site_key", "")) == site_key)
        ]
        if len(sites) == len(payload.get("wordpress_sites", [])):
            raise BridgeConfigurationError("Unknown WordPress site_key.", safe_context={"site_key": site_key})
        if not sites:
            raise BridgeConfigurationError("At least one WordPress site must remain configured.")
        payload["wordpress_sites"] = sites
        if payload.get("default_site_key") == site_key:
            payload["default_site_key"] = str(sites[0]["site_key"])
        self._backup()
        self._write_json(payload)
        return self.details()

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

    def _load_env(self) -> dict[str, str]:
        values: dict[str, str] = {}
        if not self.env_path.exists():
            return values
        for raw in self.env_path.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"\'')
        return values

    def _backup(self) -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        directory = self.config_path.parent / "backups" / "settings"
        directory.mkdir(parents=True, exist_ok=True)
        if self.config_path.exists():
            shutil.copy2(self.config_path, directory / f"bridge.{stamp}.json")
        if self.env_path.exists():
            shutil.copy2(self.env_path, directory / f"env.{stamp}.bak")

    def _write_json(self, payload: Mapping[str, Any]) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.config_path.with_suffix(self.config_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.config_path)

    @staticmethod
    def _validate_env_updates(updates: Mapping[str, str]) -> None:
        for key, value in updates.items():
            if not _ENV_SAFE.fullmatch(key):
                raise BridgeConfigurationError("Invalid environment variable name.")
            if "\n" in value or "\r" in value:
                raise BridgeConfigurationError("Credential values cannot contain line breaks.")

    def _write_env(self, updates: Mapping[str, str]) -> None:
        self._validate_env_updates(updates)
        lines = self.env_path.read_text(encoding="utf-8-sig").splitlines() if self.env_path.exists() else []
        remaining = dict(updates)
        output: list[str] = []
        for raw in lines:
            stripped = raw.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                if key in remaining:
                    output.append(f"{key}={remaining.pop(key)}")
                    continue
            output.append(raw)
        if output and output[-1].strip():
            output.append("")
        for key, value in remaining.items():
            output.append(f"{key}={value}")
        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.env_path.with_suffix(self.env_path.suffix + ".tmp")
        temporary.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
        temporary.replace(self.env_path)
