"""Regression test for AI admin API routes (defect 3).

Asserts:
- Calling admin AI routes via handle_dispatch with real admin session and CSRF
- Fails with AttributeError when coordinator._database is accessed
- And succeeds when stores are properly constructed in composition root with real DB and protector.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from eitaa_bridge.application import agent_gateway
from eitaa_bridge.application.api import BridgeApplicationApi


def test_admin_ai_routes_composition_and_csrf(config_file: Path):
    orig_adapter = agent_gateway.default_agent_adapter
    orig_conn_store = agent_gateway.ai_connection_store
    orig_pol_store = agent_gateway.ai_data_policy_store
    try:
        from tests.test_clean_install_http_boot import _write_clean_install_config
        _write_clean_install_config(config_file)
        api = BridgeApplicationApi(config_file)
        assert api.app_user_auth_enabled
        # Bootstrap admin
        auth_service = api._app_auth
        assert auth_service is not None
        issued = auth_service.bootstrap_admin(
            username="admin_user",
            password="ValidPassword123!",
            display_name="Admin User",
            client_kind="desktop_app",
        )
        token = issued.token
        csrf = issued.csrf_token

        # 1. GET /api/v2/admin/ai-connection with admin token
        res = api.dispatch(
            method="GET",
            raw_path="/api/v2/admin/ai-connection",
            app_session_token=token,
        )
        assert res.status == 200
        assert res.payload["ok"] is True
        assert "connection" in res.payload

        # 2. PUT /api/v2/admin/ai-connection
        res_put = api.dispatch(
            method="PUT",
            raw_path="/api/v2/admin/ai-connection",
            body={
                "enabled": True,
                "endpoint": "https://api.openai.com/v1/chat/completions",
                "model_id": "gpt-4o",
                "secret_key": "sk-admin-configured-key",
                "expected_revision": 1,
            },
            app_session_token=token,
            csrf_token=csrf,
        )
        assert res_put.status == 200
        assert res_put.payload["ok"] is True
        assert res_put.payload["connection"]["key_configured"] is True
        assert res_put.payload["connection"]["revision"] == 2

        # 3. GET /api/v2/admin/ai-data-policy/{id}
        res_pol_get = api.dispatch(
            method="GET",
            raw_path="/api/v2/admin/ai-data-policy/svc-web-client",
            app_session_token=token,
        )
        assert res_pol_get.status == 200
        assert res_pol_get.payload["ok"] is True
        assert res_pol_get.payload["policy"]["service_id"] == "svc-web-client"
        assert res_pol_get.payload["policy"]["policy_level"] == "disabled"

        # 4. PUT /api/v2/admin/ai-data-policy/{id}
        res_pol_put = api.dispatch(
            method="PUT",
            raw_path="/api/v2/admin/ai-data-policy/svc-web-client",
            body={
                "policy_level": "current_message",
                "max_history_turns": 3,
                "allowed_context_types": ["catalog"],
                "expected_revision": 0,
            },
            app_session_token=token,
            csrf_token=csrf,
        )
        assert res_pol_put.status == 200
        assert res_pol_put.payload["ok"] is True
        assert res_pol_put.payload["policy"]["policy_level"] == "current_message"
        assert res_pol_put.payload["policy"]["revision"] == 1
    finally:
        agent_gateway.default_agent_adapter = orig_adapter
        agent_gateway.ai_connection_store = orig_conn_store
        agent_gateway.ai_data_policy_store = orig_pol_store
