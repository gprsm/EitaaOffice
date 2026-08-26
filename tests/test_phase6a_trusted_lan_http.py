from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.errors import BridgeConfigurationError
from eitaa_bridge.infrastructure.config import BridgeConfigLoader
from eitaa_bridge.interfaces.http_api import (
    BridgeApiHttpServer,
    DeploymentRequestPolicy,
    _resolve_server_bind,
)


CLEARTEXT_ACK = "I_ACCEPT_TRUSTED_LAN_HTTP_WITHOUT_TRANSPORT_SECURITY"
PRIVATE_LAN_ACK = "I_WILL_NOT_EXPOSE_THIS_SERVICE_TO_PUBLIC_OR_GUEST_NETWORKS"
REMOTE_AUTH_ACK = "I_ACCEPT_REMOTE_MESSENGER_AUTH_OVER_CLEARTEXT_HTTP"


def _trusted_payload(config_file):
    payload = json.loads(config_file.read_text(encoding="utf-8"))
    payload["features"] = {
        "app_user_auth": {
            "enabled": True,
            "idle_timeout_minutes": 30,
            "absolute_timeout_hours": 12,
            "max_failed_attempts": 5,
            "lockout_minutes": 15,
        },
        "multi_session": {
            "enabled": False,
            "legacy_default_messenger_account_id": None,
        },
    }
    payload["deployment"] = {
        "schema_version": 1,
        "mode": "trusted_lan_http",
        "bind": {"host": "192.168.1.20", "port": 8765},
        "allowed_hosts": ["192.168.1.20:8765"],
        "allowed_origins": ["http://192.168.1.20:8765"],
        "allowed_private_client_cidrs": ["192.168.1.0/24"],
        "cleartext_http_risk_acknowledgement": CLEARTEXT_ACK,
        "private_lan_only_acknowledgement": PRIVATE_LAN_ACK,
        "bootstrap_admin_loopback_only": True,
        "same_origin_only": True,
        "remote_messenger_auth": {
            "enabled": False,
            "cleartext_http_risk_acknowledgement": None,
        },
    }
    return payload


def _write(config_file, payload):
    config_file.write_text(json.dumps(payload), encoding="utf-8")


def test_trusted_lan_contract_loads_only_with_explicit_safe_values(config_file):
    _write(config_file, _trusted_payload(config_file))
    deployment = BridgeConfigLoader.load(config_file).deployment

    assert deployment.schema_version == 1
    assert deployment.mode == "trusted_lan_http"
    assert deployment.bind_authority == "192.168.1.20:8765"
    assert deployment.allowed_hosts == ("192.168.1.20:8765",)
    assert deployment.allowed_origins == ("http://192.168.1.20:8765",)
    assert tuple(str(value) for value in deployment.parsed_client_networks()) == (
        "192.168.1.0/24",
    )
    assert deployment.bootstrap_admin_loopback_only is True
    assert deployment.same_origin_only is True
    assert deployment.remote_messenger_auth.enabled is False


def test_published_loopback_and_trusted_lan_examples_are_valid():
    root = Path(__file__).resolve().parents[1]
    loopback = BridgeConfigLoader.load(root / "bridge.example.json")
    trusted = BridgeConfigLoader.load(root / "bridge.trusted-lan-http.example.json")

    assert loopback.deployment.mode == "desktop_loopback"
    assert trusted.deployment.mode == "trusted_lan_http"


@pytest.mark.parametrize(
    ("case", "expected_code"),
    [
        ("auth_disabled", "deployment_app_user_auth_required"),
        ("cleartext_ack_missing", "deployment_cleartext_risk_not_acknowledged"),
        ("private_ack_missing", "deployment_private_lan_not_acknowledged"),
        ("bind_unspecified", "deployment_lan_bind_not_private"),
        ("bind_public", "deployment_lan_bind_not_private"),
        ("host_wildcard", "deployment_allowed_host_invalid"),
        ("host_mismatch", "deployment_lan_allowed_host_mismatch"),
        ("origin_wildcard", "deployment_allowed_origin_invalid"),
        ("origin_cross_host", "deployment_lan_origin_not_same_origin"),
        ("cidr_empty", "deployment_allowed_client_cidrs_empty"),
        ("cidr_public", "deployment_lan_client_cidr_not_private"),
        ("bootstrap_remote", "deployment_bootstrap_must_be_loopback_only"),
        ("cross_origin_enabled", "deployment_same_origin_required"),
        ("remote_auth_no_ack", "deployment_remote_messenger_auth_risk_not_acknowledged"),
        ("remote_auth_enabled", "deployment_remote_messenger_auth_not_available"),
        ("required_field_missing", "deployment_required_field_missing"),
    ],
)
def test_trusted_lan_invalid_or_open_configuration_fails_closed(
    config_file,
    case,
    expected_code,
):
    payload = _trusted_payload(config_file)
    deployment = payload["deployment"]
    if case == "auth_disabled":
        payload["features"]["app_user_auth"]["enabled"] = False
    elif case == "cleartext_ack_missing":
        deployment["cleartext_http_risk_acknowledgement"] = None
    elif case == "private_ack_missing":
        deployment["private_lan_only_acknowledgement"] = None
    elif case == "bind_unspecified":
        deployment["bind"]["host"] = "0.0.0.0"
    elif case == "bind_public":
        deployment["bind"]["host"] = "8.8.8.8"
    elif case == "host_wildcard":
        deployment["allowed_hosts"] = ["*"]
    elif case == "host_mismatch":
        deployment["allowed_hosts"] = ["192.168.1.21:8765"]
    elif case == "origin_wildcard":
        deployment["allowed_origins"] = ["http://*"]
    elif case == "origin_cross_host":
        deployment["allowed_origins"] = ["http://192.168.1.21:8765"]
    elif case == "cidr_empty":
        deployment["allowed_private_client_cidrs"] = []
    elif case == "cidr_public":
        deployment["allowed_private_client_cidrs"] = ["0.0.0.0/0"]
    elif case == "bootstrap_remote":
        deployment["bootstrap_admin_loopback_only"] = False
    elif case == "cross_origin_enabled":
        deployment["same_origin_only"] = False
    elif case == "remote_auth_no_ack":
        deployment["remote_messenger_auth"]["enabled"] = True
    elif case == "remote_auth_enabled":
        deployment["remote_messenger_auth"] = {
            "enabled": True,
            "cleartext_http_risk_acknowledgement": REMOTE_AUTH_ACK,
        }
    elif case == "required_field_missing":
        deployment.pop("allowed_hosts")
    _write(config_file, payload)

    with pytest.raises(BridgeConfigurationError) as raised:
        BridgeConfigLoader.load(config_file)
    assert raised.value.code == expected_code


def test_environment_auth_kill_switch_also_closes_lan_startup(config_file, monkeypatch):
    _write(config_file, _trusted_payload(config_file))
    monkeypatch.setenv("BRIDGE_FORCE_DISABLE_APP_USER_AUTH", "1")

    with pytest.raises(BridgeConfigurationError) as raised:
        BridgeConfigLoader.load(config_file)
    assert raised.value.code == "deployment_app_user_auth_required"


def test_startup_bind_comes_from_config_and_cli_cannot_bypass_it(config_file):
    _write(config_file, _trusted_payload(config_file))
    deployment = BridgeConfigLoader.load(config_file).deployment

    assert _resolve_server_bind(
        deployment,
        host_override=None,
        port_override=None,
    ) == ("192.168.1.20", 8765)
    assert _resolve_server_bind(
        deployment,
        host_override="192.168.1.20",
        port_override=8765,
    ) == ("192.168.1.20", 8765)
    with pytest.raises(BridgeConfigurationError) as host_error:
        _resolve_server_bind(
            deployment,
            host_override="0.0.0.0",
            port_override=8765,
        )
    assert host_error.value.code == "deployment_bind_host_override_mismatch"
    with pytest.raises(BridgeConfigurationError) as port_error:
        _resolve_server_bind(
            deployment,
            host_override="192.168.1.20",
            port_override=9999,
        )
    assert port_error.value.code == "deployment_bind_port_override_mismatch"


def test_request_policy_enforces_exact_host_origin_cidr_and_sensitive_local_only_paths(
    config_file,
):
    _write(config_file, _trusted_payload(config_file))
    policy = DeploymentRequestPolicy(
        BridgeConfigLoader.load(config_file).deployment,
        8765,
    )
    base = {
        "path": "/api/v1/health",
        "host_header": "192.168.1.20:8765",
        "client_address": "192.168.1.42",
    }

    assert policy.rejection_code(method="GET", origin=None, **base) is None
    assert policy.rejection_code(
        method="POST",
        origin="http://192.168.1.20:8765",
        **base,
    ) is None
    assert policy.rejection_code(
        method="GET",
        origin=None,
        **{**base, "client_address": "192.168.2.42"},
    ) == "deployment_client_cidr_rejected"
    assert policy.rejection_code(
        method="GET",
        origin=None,
        **{**base, "host_header": "192.168.1.21:8765"},
    ) == "deployment_host_rejected"
    assert policy.rejection_code(
        method="GET",
        origin="http://192.168.1.21:8765",
        **base,
    ) == "deployment_origin_rejected"
    assert policy.rejection_code(method="POST", origin=None, **base) == (
        "deployment_origin_required"
    )
    assert policy.rejection_code(
        method="POST",
        path="/api/v2/app-auth/setup",
        host_header=base["host_header"],
        origin="http://192.168.1.20:8765",
        client_address=base["client_address"],
    ) == "app_auth_bootstrap_loopback_required"
    assert policy.rejection_code(
        method="POST",
        path="/api/v1/auth/request-code",
        host_header=base["host_header"],
        origin="http://192.168.1.20:8765",
        client_address=base["client_address"],
    ) == "remote_messenger_auth_disabled"
    assert policy.rejection_code(
        method="POST",
        path="/api/v2/app-auth/setup",
        host_header=base["host_header"],
        origin=None,
        client_address="127.0.0.1",
    ) == "deployment_origin_required"
    assert policy.rejection_code(
        method="POST",
        path="/api/v2/app-auth/setup",
        host_header=base["host_header"],
        origin="http://192.168.1.20:8765",
        client_address="127.0.0.1",
    ) is None


def test_loopback_http_adapter_preserves_legacy_and_never_emits_cors_wildcard(
    config_file,
    monkeypatch,
):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = BridgeApplicationApi(config_file)
    server = BridgeApiHttpServer(("127.0.0.1", 0), api)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        base = f"http://{host}:{port}"
        with urlopen(base + "/api/v1/health", timeout=5) as response:
            assert response.status == 200
            assert response.headers.get("Access-Control-Allow-Origin") is None

        bad_host = Request(
            base + "/api/v1/health",
            headers={"Host": "example.com"},
        )
        with pytest.raises(HTTPError) as host_error:
            urlopen(bad_host, timeout=5)
        assert host_error.value.code == 403
        payload = json.loads(host_error.value.read().decode("utf-8"))
        assert payload["error"]["error_code"] == "deployment_host_rejected"

        bad_origin = Request(
            base + "/api/v1/health",
            headers={"Origin": "http://example.com"},
        )
        with pytest.raises(HTTPError) as origin_error:
            urlopen(bad_origin, timeout=5)
        assert origin_error.value.code == 403
        payload = json.loads(origin_error.value.read().decode("utf-8"))
        assert payload["error"]["error_code"] == "deployment_origin_rejected"
    finally:
        server.shutdown()
        server.server_close()
        api.close()
        thread.join(timeout=3)
