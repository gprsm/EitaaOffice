"""Offline tests for the Bale Bot scaffold adapter and its fail-closed status.

These tests are fully offline (httpx transport mocked). They prove adapter
shape and error mapping only; they are NOT live acceptance of Bale delivery.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from eitaa_bridge.application.provider_adapter import provider_adapter_catalog
from eitaa_bridge.errors import ProviderExtensionError
from eitaa_bridge.providers.bale_bot.adapter import BaleBotProviderAdapter
from eitaa_bridge.providers.contracts import (
    ProviderAccountContext,
    ProviderOperationContext,
    ProviderPeerReference,
    ProviderSendStatus,
    ProviderSendTextRequest,
    SensitiveProviderValue,
)
from eitaa_bridge.providers.registry import default_provider_registry

_ACCOUNT = ProviderAccountContext(
    messenger_account_id="00000000-0000-4000-a000-000000000000",
    phone_account_id="00000000-0000-4000-a000-000000000000",
    provider="bale_bot",
    storage_revision=1,
    session_generation=1,
)


class MockSessionStore:
    def load(self, context):
        return SensitiveProviderValue.from_text("mock_token")

    def save(self, context, value):
        pass

    def archive(self, context, reason_code):
        pass


@pytest.fixture
def adapter():
    return BaleBotProviderAdapter(_ACCOUNT, MockSessionStore())


@pytest.fixture
def op_context():
    return ProviderOperationContext(
        account=_ACCOUNT,
        correlation_id="12345678901234567890123456789012",
        deadline_unix_ms=int(time.time() * 1000) + 60_000,
    )


def _request():
    return ProviderSendTextRequest(
        peer=ProviderPeerReference(opaque_reference="123456", kind="private"),
        text="Hello",
        idempotency_key="idemp-key-1234567890",
    )


def test_send_text_success(adapter, op_context):
    async def _run():
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": {"message_id": 987}}
            mock_post.return_value = mock_response

            receipt = await adapter.send_text(op_context, _request())
            assert receipt.status == ProviderSendStatus.SUCCEEDED
            assert receipt.message_reference == "987"
            assert "mock_token" not in str(mock_post.call_args.kwargs)

    asyncio.run(_run())


def test_send_text_network_error_is_uncertain(adapter, op_context):
    async def _run():
        with patch("httpx.AsyncClient.post", side_effect=httpx.RequestError("Network error")):
            receipt = await adapter.send_text(op_context, _request())
            assert receipt.status == ProviderSendStatus.UNCERTAIN
            assert receipt.safe_reason_code == "bale_network_error"

    asyncio.run(_run())


def test_send_text_401_raises_auth_error(adapter, op_context):
    async def _run():
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status_code = 401
            mock_post.return_value = mock_response

            with pytest.raises(ProviderExtensionError) as exc:
                await adapter.send_text(op_context, _request())
            assert "bale_send_auth" in exc.value.code

    asyncio.run(_run())


def test_send_text_429_is_uncertain_transient(adapter, op_context):
    async def _run():
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status_code = 429
            mock_post.return_value = mock_response

            receipt = await adapter.send_text(op_context, _request())
            assert receipt.status == ProviderSendStatus.UNCERTAIN
            assert receipt.safe_reason_code == "bale_transient"

    asyncio.run(_run())


def test_unsupported_operations_stay_unimplemented(adapter, op_context):
    async def _run():
        with pytest.raises(ProviderExtensionError) as dialogs_exc:
            await adapter.list_dialogs(op_context, cursor=None, limit=10)
        assert dialogs_exc.value.code == "provider_capability_not_implemented"
        with pytest.raises(ProviderExtensionError) as history_exc:
            await adapter.load_history(
                op_context,
                peer=ProviderPeerReference(opaque_reference="user:1", kind="private"),
                cursor=None,
                limit=10,
            )
        assert history_exc.value.code == "provider_capability_not_implemented"

    asyncio.run(_run())


def test_bale_bot_is_not_registered_and_stays_fail_closed():
    registry = default_provider_registry()
    assert "bale_bot" not in registry.descriptor_catalog()
    catalog = provider_adapter_catalog()
    assert "bale_bot" not in catalog
    bale_descriptor = catalog.get("bale")
    assert bale_descriptor is not None
    assert bale_descriptor.runtime_enabled is False
    assert bale_descriptor.onboarding_enabled is False
