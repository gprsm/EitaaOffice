from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import UUID

from ...config import (
    AppUserAuthFeatureConfig,
    BridgeConfig,
    BridgeDiagnosticsConfig,
    BridgeFeaturesConfig,
    CoreDependencyConfig,
    HttpDeploymentConfig,
    HttpDeploymentLimitsConfig,
    MultiSessionFeatureConfig,
    RemoteMessengerAuthPolicyConfig,
    ReverseProxyConfig,
    WORKER_PROCESS_SCHEMA_VERSION,
    WorkerProcessFeatureConfig,
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
            features=cls._features(payload),
            deployment=cls._deployment(payload),
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

    @classmethod
    def _deployment(cls, payload: dict[str, Any]) -> HttpDeploymentConfig:
        selected = payload.get("deployment")
        if selected is None:
            return HttpDeploymentConfig.desktop_loopback()
        if not isinstance(selected, dict):
            raise BridgeConfigurationError(
                "deployment must be an object.",
                code="deployment_not_object",
            )
        required = {
            "schema_version",
            "mode",
            "bind",
            "allowed_hosts",
            "allowed_origins",
            "allowed_private_client_cidrs",
            "cleartext_http_risk_acknowledgement",
            "private_lan_only_acknowledgement",
            "bootstrap_admin_loopback_only",
            "same_origin_only",
            "remote_messenger_auth",
        }
        missing = sorted(required.difference(selected))
        if missing:
            raise BridgeConfigurationError(
                "deployment is incomplete.",
                code="deployment_required_field_missing",
                safe_context={"field": missing[0]},
            )
        bind = selected.get("bind")
        if not isinstance(bind, dict):
            raise BridgeConfigurationError(
                "deployment.bind must be an object.",
                code="deployment_bind_not_object",
            )
        remote = selected.get("remote_messenger_auth")
        if not isinstance(remote, dict):
            raise BridgeConfigurationError(
                "deployment.remote_messenger_auth must be an object.",
                code="deployment_remote_messenger_auth_not_object",
            )
        remote_required = {"enabled", "cleartext_http_risk_acknowledgement"}
        remote_missing = sorted(remote_required.difference(remote))
        if remote_missing:
            raise BridgeConfigurationError(
                "deployment.remote_messenger_auth is incomplete.",
                code="deployment_remote_messenger_auth_field_missing",
                safe_context={"field": remote_missing[0]},
            )
        schema_version = selected.get("schema_version")
        if isinstance(schema_version, bool) or not isinstance(schema_version, int):
            raise BridgeConfigurationError(
                "deployment.schema_version must be an integer.",
                code="deployment_schema_not_integer",
            )
        mode = selected.get("mode")
        if not isinstance(mode, str) or not mode.strip():
            raise BridgeConfigurationError(
                "deployment.mode must be a non-empty string.",
                code="deployment_mode_not_string",
            )
        normalized_mode = mode.strip().lower()
        bind_host = bind.get("host")
        if not isinstance(bind_host, str) or not bind_host.strip():
            raise BridgeConfigurationError(
                "deployment.bind.host must be a non-empty string.",
                code="deployment_bind_host_not_string",
            )
        bind_port = bind.get("port")
        if isinstance(bind_port, bool) or not isinstance(bind_port, int):
            raise BridgeConfigurationError(
                "deployment.bind.port must be an integer.",
                code="deployment_bind_port_not_integer",
            )
        return HttpDeploymentConfig(
            schema_version=schema_version,
            mode=normalized_mode,
            bind_host=bind_host.strip().lower(),
            bind_port=bind_port,
            allowed_hosts=cls._deployment_string_list(selected, "allowed_hosts"),
            allowed_origins=cls._deployment_string_list(selected, "allowed_origins"),
            allowed_private_client_cidrs=cls._deployment_string_list(
                selected, "allowed_private_client_cidrs"
            ),
            cleartext_http_risk_acknowledgement=cls._optional_string(
                selected, "cleartext_http_risk_acknowledgement"
            ),
            private_lan_only_acknowledgement=cls._optional_string(
                selected, "private_lan_only_acknowledgement"
            ),
            bootstrap_admin_loopback_only=cls._required_boolean(
                selected, "bootstrap_admin_loopback_only"
            ),
            same_origin_only=cls._required_boolean(selected, "same_origin_only"),
            secure_cookie=cls._optional_boolean(selected, "secure_cookie", False),
            limits=cls._deployment_limits(selected, normalized_mode),
            reverse_proxy=cls._reverse_proxy(selected),
            remote_messenger_auth=RemoteMessengerAuthPolicyConfig(
                enabled=cls._required_boolean(remote, "enabled"),
                cleartext_http_risk_acknowledgement=cls._optional_string(
                    remote, "cleartext_http_risk_acknowledgement"
                ),
            ),
        )

    @classmethod
    def _deployment_limits(
        cls,
        deployment: dict[str, Any],
        mode: str,
    ) -> HttpDeploymentLimitsConfig:
        selected = deployment.get("limits")
        if selected is None:
            return HttpDeploymentLimitsConfig.for_mode(mode)
        if not isinstance(selected, dict):
            raise BridgeConfigurationError(
                "deployment.limits must be an object.",
                code="deployment_limits_not_object",
            )
        required = {
            "max_json_body_bytes",
            "max_upload_bytes",
            "request_timeout_seconds",
            "requests_per_minute",
            "uploads_per_minute",
            "shutdown_grace_seconds",
        }
        missing = sorted(required.difference(selected))
        if missing:
            raise BridgeConfigurationError(
                "deployment.limits is incomplete.",
                code="deployment_limits_field_missing",
                safe_context={"field": missing[0]},
            )

        def required_integer(key: str) -> int:
            value = selected.get(key)
            if isinstance(value, bool) or not isinstance(value, int):
                raise BridgeConfigurationError(
                    f"deployment.limits.{key} must be an integer.",
                    code="deployment_limits_integer_invalid",
                    safe_context={"field": key},
                )
            return value

        def required_number(key: str) -> float:
            value = selected.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise BridgeConfigurationError(
                    f"deployment.limits.{key} must be a number.",
                    code="deployment_limits_number_invalid",
                    safe_context={"field": key},
                )
            return float(value)

        return HttpDeploymentLimitsConfig(
            max_json_body_bytes=required_integer("max_json_body_bytes"),
            max_upload_bytes=required_integer("max_upload_bytes"),
            request_timeout_seconds=required_number("request_timeout_seconds"),
            requests_per_minute=required_integer("requests_per_minute"),
            uploads_per_minute=required_integer("uploads_per_minute"),
            shutdown_grace_seconds=required_number("shutdown_grace_seconds"),
        )

    @classmethod
    def _reverse_proxy(cls, deployment: dict[str, Any]) -> ReverseProxyConfig:
        selected = deployment.get("reverse_proxy")
        if selected is None:
            return ReverseProxyConfig()
        if not isinstance(selected, dict):
            raise BridgeConfigurationError(
                "deployment.reverse_proxy must be an object.",
                code="deployment_reverse_proxy_not_object",
            )
        required = {
            "enabled",
            "trusted_proxy_cidrs",
            "required_forwarded_proto",
            "require_forwarded_for",
        }
        missing = sorted(required.difference(selected))
        if missing:
            raise BridgeConfigurationError(
                "deployment.reverse_proxy is incomplete.",
                code="deployment_reverse_proxy_field_missing",
                safe_context={"field": missing[0]},
            )
        return ReverseProxyConfig(
            enabled=cls._required_boolean(selected, "enabled"),
            trusted_proxy_cidrs=cls._deployment_string_list(
                selected, "trusted_proxy_cidrs"
            ),
            required_forwarded_proto=cls._optional_string(
                selected, "required_forwarded_proto"
            ),
            require_forwarded_for=cls._required_boolean(
                selected, "require_forwarded_for"
            ),
        )

    @staticmethod
    def _deployment_string_list(
        payload: dict[str, Any], key: str
    ) -> tuple[str, ...]:
        value = payload.get(key)
        if not isinstance(value, list):
            raise BridgeConfigurationError(
                f"deployment.{key} must be an array of strings.",
                code="deployment_list_invalid",
                safe_context={"field": key},
            )
        selected: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise BridgeConfigurationError(
                    f"deployment.{key} must contain only non-empty strings.",
                    code="deployment_list_item_invalid",
                    safe_context={"field": key},
                )
            selected.append(item.strip().lower())
        return tuple(selected)

    @staticmethod
    def _optional_string(payload: dict[str, Any], key: str) -> str | None:
        value = payload.get(key)
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise BridgeConfigurationError(
                f"{key} must be null or a non-empty string.",
                code="deployment_acknowledgement_invalid",
                safe_context={"field": key},
            )
        return value.strip()

    @staticmethod
    def _required_boolean(payload: dict[str, Any], key: str) -> bool:
        value = payload.get(key)
        if not isinstance(value, bool):
            raise BridgeConfigurationError(
                f"{key} must be boolean.",
                code="deployment_boolean_invalid",
                safe_context={"field": key},
            )
        return value

    @staticmethod
    def _optional_boolean(
        payload: dict[str, Any],
        key: str,
        default: bool,
    ) -> bool:
        value = payload.get(key, default)
        if not isinstance(value, bool):
            raise BridgeConfigurationError(
                f"{key} must be boolean.",
                code="deployment_boolean_invalid",
                safe_context={"field": key},
            )
        return value

    @classmethod
    def _features(cls, payload: dict[str, Any]) -> BridgeFeaturesConfig:
        features = payload.get("features")
        if features is None:
            return cls._default_features()
        if not isinstance(features, dict):
            return BridgeFeaturesConfig(
                multi_session=cls._disabled_multi_session("features_not_object"),
                app_user_auth=cls._disabled_app_user_auth("features_not_object"),
                worker_process=cls._disabled_worker_process("features_not_object"),
            )
        multi_session = cls._multi_session_feature(features)
        return BridgeFeaturesConfig(
            multi_session=multi_session,
            app_user_auth=cls._app_user_auth_feature(features),
            worker_process=cls._worker_process_feature(
                features,
                multi_session_enabled=multi_session.enabled,
            ),
        )

    @classmethod
    def _multi_session_feature(
        cls, features: dict[str, Any]
    ) -> MultiSessionFeatureConfig:
        multi_session = features.get("multi_session")
        if multi_session is None:
            return MultiSessionFeatureConfig()
        if not isinstance(multi_session, dict):
            return cls._disabled_multi_session("multi_session_not_object")
        enabled = multi_session.get("enabled", False)
        if not isinstance(enabled, bool):
            return cls._disabled_multi_session("enabled_not_boolean")
        legacy_id = multi_session.get("legacy_default_messenger_account_id")
        if legacy_id is not None:
            if not isinstance(legacy_id, str):
                return cls._disabled_multi_session("legacy_account_id_not_string")
            try:
                parsed = UUID(legacy_id)
            except (ValueError, AttributeError):
                return cls._disabled_multi_session("legacy_account_id_invalid")
            if parsed.version != 4 or str(parsed) != legacy_id:
                return cls._disabled_multi_session("legacy_account_id_invalid")
        if cls._environment_kill_switch():
            return cls._disabled_multi_session("environment_kill_switch", legacy_id=legacy_id)
        return MultiSessionFeatureConfig(
            enabled=enabled,
            legacy_default_messenger_account_id=legacy_id,
        )

    @staticmethod
    def _disabled_multi_session(
        reason: str,
        *,
        legacy_id: str | None = None,
    ) -> MultiSessionFeatureConfig:
        return MultiSessionFeatureConfig(
            enabled=False,
            legacy_default_messenger_account_id=legacy_id,
            fail_closed_reason=reason,
        )

    @classmethod
    def _app_user_auth_feature(
        cls, features: dict[str, Any]
    ) -> AppUserAuthFeatureConfig:
        selected = features.get("app_user_auth")
        if selected is None:
            return AppUserAuthFeatureConfig()
        if not isinstance(selected, dict):
            return cls._disabled_app_user_auth("app_user_auth_not_object")
        enabled = selected.get("enabled", False)
        if not isinstance(enabled, bool):
            return cls._disabled_app_user_auth("enabled_not_boolean")
        self_registration_enabled = selected.get("self_registration_enabled", True)
        if not isinstance(self_registration_enabled, bool):
            return cls._disabled_app_user_auth("self_registration_enabled_not_boolean")
        values = {
            "idle_timeout_minutes": (selected.get("idle_timeout_minutes", 525_600), 5, 525_600),
            "absolute_timeout_hours": (selected.get("absolute_timeout_hours", 8_760), 1, 8_760),
            "max_failed_attempts": (selected.get("max_failed_attempts", 5), 3, 20),
            "lockout_minutes": (selected.get("lockout_minutes", 15), 1, 1440),
        }
        parsed: dict[str, int] = {}
        for name, (value, minimum, maximum) in values.items():
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not minimum <= value <= maximum
            ):
                return cls._disabled_app_user_auth(f"{name}_invalid")
            parsed[name] = value
        if cls._app_user_auth_kill_switch():
            return cls._disabled_app_user_auth(
                "environment_kill_switch",
                self_registration_enabled=self_registration_enabled,
                **parsed,
            )
        return AppUserAuthFeatureConfig(
            enabled=enabled,
            self_registration_enabled=self_registration_enabled,
            **parsed,
        )

    @staticmethod
    def _disabled_app_user_auth(
        reason: str,
        *,
        self_registration_enabled: bool = False,
        idle_timeout_minutes: int = 525_600,
        absolute_timeout_hours: int = 8_760,
        max_failed_attempts: int = 5,
        lockout_minutes: int = 15,
    ) -> AppUserAuthFeatureConfig:
        return AppUserAuthFeatureConfig(
            enabled=False,
            self_registration_enabled=self_registration_enabled,
            idle_timeout_minutes=idle_timeout_minutes,
            absolute_timeout_hours=absolute_timeout_hours,
            max_failed_attempts=max_failed_attempts,
            lockout_minutes=lockout_minutes,
            fail_closed_reason=reason,
        )

    @classmethod
    def _worker_process_feature(
        cls,
        features: dict[str, Any],
        *,
        multi_session_enabled: bool,
    ) -> WorkerProcessFeatureConfig:
        selected = features.get("worker_process")
        if selected is None:
            return WorkerProcessFeatureConfig()
        if not isinstance(selected, dict):
            return cls._disabled_worker_process("worker_process_not_object")
        schema_version = selected.get("schema_version")
        if (
            isinstance(schema_version, bool)
            or not isinstance(schema_version, int)
            or schema_version != WORKER_PROCESS_SCHEMA_VERSION
        ):
            return cls._disabled_worker_process("schema_version_invalid")
        enabled = selected.get("enabled")
        if not isinstance(enabled, bool):
            return cls._disabled_worker_process("enabled_not_boolean")
        startup_timeout = selected.get("startup_timeout_seconds", 15)
        request_timeout = selected.get("request_timeout_seconds", 60)
        if (
            isinstance(startup_timeout, bool)
            or not isinstance(startup_timeout, int)
            or not 5 <= startup_timeout <= 60
        ):
            return cls._disabled_worker_process("startup_timeout_invalid")
        if (
            isinstance(request_timeout, bool)
            or not isinstance(request_timeout, int)
            or not 5 <= request_timeout <= 300
        ):
            return cls._disabled_worker_process(
                "request_timeout_invalid",
                startup_timeout_seconds=startup_timeout,
            )
        supervisor_defaults = {
            "heartbeat_interval_seconds": 5,
            "heartbeat_timeout_seconds": 15,
            "heartbeat_failure_threshold": 3,
            "restart_window_seconds": 300,
            "max_restarts": 3,
            "backoff_initial_seconds": 2,
            "backoff_max_seconds": 60,
            "quarantine_seconds": 300,
        }
        supervisor_limits = {
            "heartbeat_interval_seconds": (1, 60),
            "heartbeat_timeout_seconds": (2, 120),
            "heartbeat_failure_threshold": (1, 10),
            "restart_window_seconds": (30, 3600),
            "max_restarts": (1, 10),
            "backoff_initial_seconds": (1, 60),
            "backoff_max_seconds": (1, 600),
            "quarantine_seconds": (30, 86400),
        }
        supervisor_values: dict[str, int] = {}
        for field, default in supervisor_defaults.items():
            value = selected.get(field, default)
            minimum, maximum = supervisor_limits[field]
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not minimum <= value <= maximum
            ):
                return cls._disabled_worker_process(
                    f"{field}_invalid",
                    startup_timeout_seconds=startup_timeout,
                    request_timeout_seconds=request_timeout,
                )
            supervisor_values[field] = value
        if (
            supervisor_values["heartbeat_timeout_seconds"]
            <= supervisor_values["heartbeat_interval_seconds"]
        ):
            return cls._disabled_worker_process(
                "heartbeat_deadline_invalid",
                startup_timeout_seconds=startup_timeout,
                request_timeout_seconds=request_timeout,
            )
        if (
            supervisor_values["backoff_max_seconds"]
            < supervisor_values["backoff_initial_seconds"]
        ):
            return cls._disabled_worker_process(
                "backoff_range_invalid",
                startup_timeout_seconds=startup_timeout,
                request_timeout_seconds=request_timeout,
            )
        if enabled and not multi_session_enabled:
            return cls._disabled_worker_process(
                "multi_session_required",
                startup_timeout_seconds=startup_timeout,
                request_timeout_seconds=request_timeout,
            )
        if cls._worker_process_kill_switch():
            return cls._disabled_worker_process(
                "environment_kill_switch",
                startup_timeout_seconds=startup_timeout,
                request_timeout_seconds=request_timeout,
            )
        return WorkerProcessFeatureConfig(
            schema_version=schema_version,
            enabled=enabled,
            startup_timeout_seconds=startup_timeout,
            request_timeout_seconds=request_timeout,
            **supervisor_values,
        )

    @staticmethod
    def _disabled_worker_process(
        reason: str,
        *,
        startup_timeout_seconds: int = 15,
        request_timeout_seconds: int = 60,
    ) -> WorkerProcessFeatureConfig:
        return WorkerProcessFeatureConfig(
            enabled=False,
            startup_timeout_seconds=startup_timeout_seconds,
            request_timeout_seconds=request_timeout_seconds,
            fail_closed_reason=reason,
        )

    @staticmethod
    def _default_features() -> BridgeFeaturesConfig:
        return BridgeFeaturesConfig(
            multi_session=MultiSessionFeatureConfig(),
            app_user_auth=AppUserAuthFeatureConfig(),
            worker_process=WorkerProcessFeatureConfig(),
        )

    @staticmethod
    def _environment_kill_switch() -> bool:
        value = os.getenv("BRIDGE_FORCE_DISABLE_MULTI_SESSION", "")
        return value.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _app_user_auth_kill_switch() -> bool:
        value = os.getenv("BRIDGE_FORCE_DISABLE_APP_USER_AUTH", "")
        return value.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _worker_process_kill_switch() -> bool:
        value = os.getenv("BRIDGE_FORCE_DISABLE_WORKER_PROCESS", "")
        return value.strip().lower() in {"1", "true", "yes", "on"}

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
