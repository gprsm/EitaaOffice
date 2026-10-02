"""Owner-authorized Bale personal provider: contract tests (F-086/ADR-60).

The personal-account path is authorized as a first-class provider alongside
the official Bale Bot scaffold. These tests prove the registration manifest,
the offline adapter contract and honest fail-closed staging
(onboarding/worker wiring still pending) with a fully synthetic backend.
No network, vault or real identity is involved.
"""

from __future__ import annotations

import asyncio
import json
import time
from uuid import uuid4

import pytest

from eitaa_bridge.application.bale_provider_adapter import BaleProviderApplicationAdapter
from eitaa_bridge.application.provider_adapter import provider_adapter_catalog
from eitaa_bridge.errors import ProviderExtensionError
from eitaa_bridge.providers import (
    ProviderAccountContext,
    ProviderSendStatus,
    ProviderSendTextRequest,
    ProviderSessionState,
    ProviderSessionStore,
    SensitiveProviderValue,
    default_provider_registry,
)
from eitaa_bridge.providers.bale import bale_extension_registration
from eitaa_bridge.providers.contracts import (
    ProviderDialogPage,
    ProviderMessagePage,
    ProviderOperationContext,
    ProviderPeerReference,
)
from eitaa_bridge.providers.testing import (
    InMemoryProviderSessionStore,
    verify_provider_adapter_contract,
)

_SYNTHETIC_PASSPHRASE = "synthetic-passphrase"


def _account() -> ProviderAccountContext:
    return ProviderAccountContext(
        messenger_account_id=str(uuid4()),
        phone_account_id=str(uuid4()),
        provider="bale",
        storage_revision=1,
        session_generation=1,
    )


def _op_context(account: ProviderAccountContext | None = None) -> ProviderOperationContext:
    return ProviderOperationContext(
        account=account or _account(),
        correlation_id="a" * 32,
        deadline_unix_ms=int(time.time() * 1000) + 60_000,
    )


class FakeBaleBackend:
    """Synthetic stand-in for the Bale personal client facade."""

    def __init__(self, *, fail_send_code: str | None = None, vault_locked: bool = False) -> None:
        self.fail_send_code = fail_send_code
        self.vault_locked = vault_locked
        self.auth_started_with: str | None = None

    async def auth_start(self, phone_number):
        self.auth_started_with = phone_number
        return {"transaction_hash": "tx-1", "next": "code"}

    async def auth_code(self, transaction_hash, code, *, passphrase=None):
        if code == "999999":
            return {"authenticated": False, "next": "password", "transaction_hash": transaction_hash}
        return {"authenticated": True, "next": None, "user_id": 7}

    async def auth_password(self, transaction_hash, password, *, passphrase=None):
        return {"authenticated": True, "user_id": 7}

    async def connect(self, *, passphrase=None, subscribe=True, presence=True):
        if not self.vault_locked:
            return {"connected": True}
        from eitaa_bridge.application.bale_client.api import BaleApiError

        raise BaleApiError("locked", code="bale_vault_locked")

    async def list_dialogs(self, *, limit=20, offset_date=None):
        return [
            {"peer": {"id": 42, "type": 1}, "unread_count": 2, "last_text": "سلام"},
            {"peer": {"id": 55, "type": 2}, "unread_count": 0},
        ]

    async def read_history(self, user_id, *, limit=20, offset_date=None, peer_type=1):
        return [
            {"message_id": 11, "sender_id": 42, "date": 1758900000, "text": "پیام آزمایشی"},
            {"message_id": 12, "sender_id": None, "date": 1758900001, "text": None},
        ]

    async def send_text(self, user_id, text, *, silent=False, peer_type=1):
        if self.fail_send_code is not None:
            from eitaa_bridge.application.bale_client.api import BaleApiError

            raise BaleApiError("send failed", code=self.fail_send_code)
        return {"user_id": user_id, "random_id": 4242, "sent": True, "response_size": 8}

    async def close(self):
        return None


def _adapter(backend: FakeBaleBackend | None = None) -> BaleProviderApplicationAdapter:
    registration = bale_extension_registration()
    return BaleProviderApplicationAdapter(
        _account(),
        InMemoryProviderSessionStore(),
        registration.manifest,
        backend_factory=lambda: backend or FakeBaleBackend(),
    )


def test_bale_manifest_records_owner_authorization_and_real_capabilities() -> None:
    registration = bale_extension_registration()
    manifest = registration.manifest

    assert manifest.implementation_state.value == "contract_verified"
    assert manifest.authorization_reference == "document:F-086"
    assert manifest.configured is True
    # Product wiring is offline verified; this is not Live acceptance.
    assert manifest.runtime_enabled is True
    assert manifest.onboarding_enabled is True
    assert manifest.reason_code is None
    assert manifest.account_identity_kind == "phone_e164"
    assert [stage.value for stage in manifest.auth_steps] == [
        "identity",
        "challenge",
        "second_factor_optional",
    ]
    capability_names = {capability.value for capability in manifest.capabilities}
    assert {"auth.phone", "messages.send", "history.read", "contacts.read"} <= capability_names
    assert registration.catalog_visible is True
    assert registration.adapter_factory is not None
    assert registration.worker_factory is not None


def test_registry_requires_owned_backend_and_worker_config(tmp_path) -> None:
    registry = default_provider_registry()
    adapter = registry.create_adapter("bale", _account(), InMemoryProviderSessionStore())
    with pytest.raises(ProviderExtensionError) as unowned:
        adapter._get_backend()
    assert unowned.value.code == "provider_account_runtime_unavailable"
    with pytest.raises(ProviderExtensionError) as missing_config:
        registry.create_worker("bale", str(uuid4()), None)
    assert missing_config.value.code == "bale_worker_config_required"
    worker = registry.create_worker("bale", str(uuid4()), str(tmp_path / "bridge.json"))
    assert worker.provider == "bale"
    assert worker.owner is None
    worker.close()


def test_descriptor_advertises_authorized_pending_state() -> None:
    descriptor = provider_adapter_catalog()["bale"]
    payload = descriptor.safe_payload()
    assert payload["configured"] is True
    assert payload["runtime_enabled"] is True
    assert payload["onboarding_enabled"] is True
    assert payload["implementation_state"] == "contract_verified"
    assert payload.get("reason_code") is None
    assert len(payload["capabilities"]) > 0


def test_personal_and_bot_paths_coexist() -> None:
    catalog = provider_adapter_catalog()
    assert "bale" in catalog  # authorized personal path
    import eitaa_bridge.providers.bale_bot as bale_bot

    assert bale_bot.manifest.provider == "bale_bot"
    assert bale_bot.manifest.runtime_enabled is False
    assert "bale_bot" not in catalog  # bot stays an unregistered official-API scaffold


def test_adapter_passes_offline_contract_probe() -> None:
    registration = bale_extension_registration()
    adapter = _adapter()
    report = verify_provider_adapter_contract(
        adapter,
        expected_manifest=registration.manifest,
    )
    assert report.safe_payload()["adapter_shape_valid"] is True


def test_send_text_maps_success_and_keeps_secrets_out() -> None:
    async def _run():
        adapter = _adapter()
        request = ProviderSendTextRequest(
            peer=ProviderPeerReference("bale:peer:42", "private"),
            text="سلام",
            idempotency_key="idemp-bale-00000001",
        )
        receipt = await adapter.send_text(_op_context(), request)
        assert receipt.status is ProviderSendStatus.SUCCEEDED
        assert receipt.message_reference == "bale:submission:4242"
        assert "سلام" not in repr(receipt)

    asyncio.run(_run())


def test_send_text_unrecoverable_connection_is_uncertain_with_safe_code() -> None:
    async def _run():
        adapter = _adapter(FakeBaleBackend(fail_send_code="bale_not_connected"))
        request = ProviderSendTextRequest(
            peer=ProviderPeerReference("bale:peer:42", "private"),
            text="hello",
            idempotency_key="idemp-bale-00000002",
        )
        receipt = await adapter.send_text(_op_context(), request)
        assert receipt.status is ProviderSendStatus.UNCERTAIN
        assert receipt.safe_reason_code == "bale_not_connected"

    asyncio.run(_run())


def test_send_text_permanent_failure_raises_safe_code_without_client_text() -> None:
    async def _run():
        adapter = _adapter(FakeBaleBackend(fail_send_code="bale_empty_text"))
        request = ProviderSendTextRequest(
            peer=ProviderPeerReference("bale:peer:42", "private"),
            text="hello",
            idempotency_key="idemp-bale-00000003",
        )
        with pytest.raises(ProviderExtensionError) as exc:
            await adapter.send_text(_op_context(), request)
        assert exc.value.code == "bale_empty_text"
        assert "send failed" not in str(exc.value.safe_context)

    asyncio.run(_run())


def test_invalid_peer_reference_is_rejected_before_any_client_call() -> None:
    async def _run():
        backend = FakeBaleBackend()
        adapter = _adapter(backend)
        request = ProviderSendTextRequest(
            peer=ProviderPeerReference("user:42", "private"),
            text="hello",
            idempotency_key="idemp-bale-00000004",
        )
        with pytest.raises(ProviderExtensionError) as exc:
            await adapter.send_text(_op_context(), request)
        assert exc.value.code == "provider_peer_reference_invalid"
        assert backend.auth_started_with is None

    asyncio.run(_run())


def test_auth_flow_maps_challenge_second_factor_and_sealed_session() -> None:
    async def _run():
        adapter = _adapter()
        context = _op_context()

        challenge = await adapter.request_challenge(
            context, SensitiveProviderValue.from_text("+989120000000")
        )
        assert challenge.state is ProviderSessionState.CHALLENGE_PENDING
        assert challenge.challenge_kind == "otp"
        assert "+989120000000" not in repr(challenge)

        response = SensitiveProviderValue.from_text(
            json.dumps({"code": "999999"})
        )
        outcome = await adapter.submit_challenge(
            context, challenge.challenge_state, response
        )
        assert outcome.state is ProviderSessionState.SECOND_FACTOR_PENDING

        second = SensitiveProviderValue.from_text(
            json.dumps({"password": "synthetic-password"})
        )
        final = await adapter.submit_second_factor(
            context, outcome.challenge_state, second
        )
        assert final.state is ProviderSessionState.AUTHENTICATED
        assert final.sealed_session is not None
        assert final.sealed_session.reveal_bytes() == b"bale:vault:v1"
        assert _SYNTHETIC_PASSPHRASE not in repr(final)
        assert "synthetic-password" not in repr(final)

        validation = await adapter.validate_session(context, final.sealed_session)
        assert validation.state is ProviderSessionState.AUTHENTICATED

    asyncio.run(_run())


def test_validate_session_maps_locked_vault_to_expired_honestly() -> None:
    async def _run():
        adapter = _adapter(FakeBaleBackend(vault_locked=True))
        outcome = await adapter.validate_session(
            _op_context(),
            SensitiveProviderValue.from_text("bale:vault:v1"),
        )
        assert outcome.state is ProviderSessionState.EXPIRED
        assert outcome.safe_reason_code == "bale_vault_locked"
        assert "bale:vault:v1" not in repr(outcome)

    asyncio.run(_run())


def test_dialogs_and_history_map_to_bounded_pages() -> None:
    async def _run():
        adapter = _adapter()
        dialog_page = await adapter.list_dialogs(_op_context(), cursor=None, limit=10)
        assert isinstance(dialog_page, ProviderDialogPage)
        assert dialog_page.dialogs[0].peer.opaque_reference == "bale:user:42"
        assert dialog_page.dialogs[0].peer.kind == "private"
        assert dialog_page.dialogs[1].peer.kind == "group"

        history = await adapter.load_history(
            _op_context(),
            peer=ProviderPeerReference("bale:peer:42", "private"),
            cursor=None,
            limit=10,
        )
        assert isinstance(history, ProviderMessagePage)
        assert history.messages[0].message_reference == "bale:message:11"
        assert history.messages[0].sent_at_unix_ms == 1758900000 * 1000
        assert history.messages[1].sender_reference is None

    asyncio.run(_run())


def test_release_scope_ships_the_personal_client_again() -> None:
    from package_clean import collect_release_files

    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    selected = {
        path.relative_to(root).as_posix()
        for path in collect_release_files(root)
    }
    assert "src/eitaa_bridge/application/bale_client/api.py" in selected
    assert "src/eitaa_bridge/application/bale_provider_adapter.py" in selected
    assert "src/eitaa_bridge/providers/bale/slot.py" in selected
    assert "src/eitaa_bridge/application/bale_provider_worker.py" in selected
    assert "src/eitaa_bridge/application/bale_runtime.py" in selected
    assert "scripts/bale_product_pilot.py" in selected
