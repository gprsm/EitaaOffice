from __future__ import annotations

import ast
import asyncio
from pathlib import Path
import time
from uuid import uuid4

import pytest

from eitaa_bridge.application.provider_adapter import provider_adapter_catalog
from eitaa_bridge.errors import ProviderExtensionError
from eitaa_bridge.infrastructure.diagnostics import EVENT_CATALOG
from eitaa_bridge.interfaces.provider_worker import run_worker
from eitaa_bridge.providers import (
    ProviderAccountContext,
    ProviderAdapter,
    ProviderAuthOutcome,
    ProviderAuthStage,
    ProviderAuthorizationBasis,
    ProviderCapability,
    ProviderDialogPage,
    ProviderImplementationState,
    ProviderManifest,
    ProviderMessagePage,
    ProviderOperationContext,
    ProviderRegistration,
    ProviderRegistry,
    ProviderSendReceipt,
    ProviderSendStatus,
    ProviderSessionState,
    ProviderSendTextRequest,
    SensitiveProviderValue,
    default_provider_registry,
)
from eitaa_bridge.providers.testing import (
    InMemoryProviderSessionStore,
    verify_provider_adapter_contract,
)


def _account(provider: str = "demo") -> ProviderAccountContext:
    return ProviderAccountContext(
        messenger_account_id=str(uuid4()),
        phone_account_id=str(uuid4()),
        provider=provider,
        storage_revision=1,
        session_generation=1,
    )


def _authorized_manifest(provider: str = "demo") -> ProviderManifest:
    return ProviderManifest(
        provider=provider,
        display_name="Demo",
        account_kind="personal",
        implementation_state=ProviderImplementationState.CONTRACT_VERIFIED,
        authorization_basis=ProviderAuthorizationBasis.OFFICIAL_API,
        authorization_reference="https://example.invalid/provider-contract",
        configured=True,
        runtime_enabled=True,
        onboarding_enabled=True,
        account_identity_kind="phone_e164",
        auth_steps=(ProviderAuthStage.IDENTITY, ProviderAuthStage.CHALLENGE),
        capabilities=frozenset(
            {
                ProviderCapability.AUTH_PHONE,
                ProviderCapability.DIALOGS_READ,
                ProviderCapability.HISTORY_READ,
                ProviderCapability.MESSAGES_SEND,
            }
        ),
    )


class _ContractAdapter:
    def __init__(self, manifest: ProviderManifest) -> None:
        self._manifest = manifest

    @property
    def manifest(self) -> ProviderManifest:
        return self._manifest

    async def request_challenge(self, context, identity):
        context.require_live_deadline()
        return ProviderAuthOutcome(
            ProviderSessionState.CHALLENGE_PENDING,
            challenge_state=SensitiveProviderValue.from_text("opaque-challenge"),
            challenge_kind="code",
        )

    async def submit_challenge(self, context, challenge_state, response):
        return ProviderAuthOutcome(
            ProviderSessionState.AUTHENTICATED,
            sealed_session=SensitiveProviderValue.from_text("sealed-session"),
        )

    async def submit_second_factor(self, context, challenge_state, response):
        return await self.submit_challenge(context, challenge_state, response)

    async def validate_session(self, context, sealed_session):
        return ProviderAuthOutcome(ProviderSessionState.AUTHENTICATED, sealed_session=sealed_session)

    async def list_dialogs(self, context, *, cursor, limit):
        return ProviderDialogPage(())

    async def load_history(self, context, *, peer, cursor, limit):
        return ProviderMessagePage(())

    async def send_text(self, context, request: ProviderSendTextRequest):
        return ProviderSendReceipt(ProviderSendStatus.SUCCEEDED, message_reference="message:1")

    async def close(self):
        return None


def test_default_registry_exposes_offline_verified_bale_product():
    catalog = provider_adapter_catalog()
    assert set(catalog) == {"eitaa", "bale"}
    assert catalog["eitaa"].implementation_state == "live_accepted"
    assert "dialogs.read" in catalog["eitaa"].capabilities
    assert catalog["bale"].implementation_state == "contract_verified"
    assert catalog["bale"].configured is True
    assert catalog["bale"].runtime_enabled is True
    assert catalog["bale"].onboarding_enabled is True
    assert catalog["bale"].reason_code is None
    adapter = default_provider_registry().create_adapter("bale", _account("bale"), InMemoryProviderSessionStore())
    with pytest.raises(ProviderExtensionError) as unowned:
        adapter._get_backend()
    assert unowned.value.code == "provider_account_runtime_unavailable"
    with pytest.raises(ProviderExtensionError) as rejected:
        default_provider_registry().create_worker("bale", str(uuid4()), None)
    assert rejected.value.code == "bale_worker_config_required"


def test_manifest_requires_authorization_and_contract_verification():
    with pytest.raises(ProviderExtensionError) as unauthorized:
        ProviderManifest(
            provider="demo",
            display_name="Demo",
            account_kind="personal",
            implementation_state=ProviderImplementationState.IMPLEMENTED,
            configured=True,
        )
    assert unauthorized.value.code == "provider_activation_not_authorized"

    with pytest.raises(ProviderExtensionError) as unverified:
        ProviderManifest(
            provider="demo",
            display_name="Demo",
            account_kind="personal",
            implementation_state=ProviderImplementationState.IMPLEMENTED,
            authorization_basis=ProviderAuthorizationBasis.OFFICIAL_API,
            authorization_reference="https://example.invalid/provider-contract",
            configured=True,
            runtime_enabled=True,
        )
    assert unverified.value.code == "provider_activation_not_verified"

    with pytest.raises(ProviderExtensionError) as no_reference:
        ProviderManifest(
            provider="demo",
            display_name="Demo",
            account_kind="personal",
            implementation_state=ProviderImplementationState.IMPLEMENTED,
            authorization_basis=ProviderAuthorizationBasis.WRITTEN_PERMISSION,
        )
    assert no_reference.value.code == "provider_authorization_reference_required"


def test_allowlisted_factory_and_offline_contract_harness_accept_typed_adapter():
    manifest = _authorized_manifest()
    registry = ProviderRegistry()
    registry.register(
        ProviderRegistration(
            manifest=manifest,
            adapter_factory=lambda context, store: _ContractAdapter(manifest),
        )
    )
    store = InMemoryProviderSessionStore()
    account = _account()
    adapter = registry.create_adapter("demo", account, store)
    assert isinstance(adapter, ProviderAdapter)
    report = verify_provider_adapter_contract(adapter, expected_manifest=manifest)
    assert report.safe_payload()["adapter_shape_valid"] is True

    context = ProviderOperationContext(
        account=account,
        correlation_id="a" * 32,
        deadline_unix_ms=int(time.time() * 1000) + 30_000,
    )
    outcome = asyncio.run(adapter.request_challenge(context, SensitiveProviderValue.from_text("synthetic")))
    assert outcome.safe_summary() == {
        "state": "challenge_pending",
        "challenge_kind": "code",
        "expires_at_unix_ms": None,
        "retry_after_seconds": None,
        "safe_reason_code": None,
        "challenge_present": True,
        "session_present": False,
    }


def test_sensitive_values_session_store_and_repr_do_not_expose_material():
    secret = SensitiveProviderValue.from_text("do-not-expose-this")
    assert "do-not-expose-this" not in repr(secret)
    assert "do-not-expose-this" not in str(secret)
    account = _account()
    store = InMemoryProviderSessionStore()
    store.save(account, secret)
    assert store.load(account) is secret
    other = _account()
    assert store.load(other) is None
    store.archive(account, reason_code="test_complete")
    assert store.load(account) is None


def test_registry_rejects_duplicates_unknown_providers_and_bad_factory_shape():
    manifest = _authorized_manifest()
    registry = ProviderRegistry()
    registration = ProviderRegistration(manifest=manifest, adapter_factory=lambda context, store: object())
    registry.register(registration)
    with pytest.raises(ProviderExtensionError) as duplicate:
        registry.register(registration)
    assert duplicate.value.code == "provider_registration_duplicate"
    with pytest.raises(ProviderExtensionError) as unknown:
        registry.registration("not_registered")
    assert unknown.value.code == "provider_not_allowlisted"
    with pytest.raises(ProviderExtensionError) as invalid:
        registry.create_adapter("demo", _account(), InMemoryProviderSessionStore())
    assert invalid.value.code == "provider_adapter_contract_invalid"

    failed_registry = ProviderRegistry()

    def failed_factory(context, store):
        del context, store
        raise ValueError("private provider detail")

    failed_registry.register(
        ProviderRegistration(manifest=manifest, adapter_factory=failed_factory)
    )
    with pytest.raises(ProviderExtensionError) as failed:
        failed_registry.create_adapter("demo", _account(), InMemoryProviderSessionStore())
    assert failed.value.code == "provider_adapter_factory_failed"
    assert "private provider detail" not in str(failed.value)


def test_bale_slot_has_no_transport_dynamic_loader_or_endpoint_literal(capsys):
    root = Path(__file__).resolve().parents[1] / "src" / "eitaa_bridge" / "providers"
    forbidden_imports = {"aiohttp", "httpx", "requests", "socket", "websockets", "importlib", "pkgutil"}
    forbidden_calls = {"eval", "exec", "__import__"}
    # providers/bale_bot is the official Bale Bot API scaffold (ADR-56): the
    # only allowed transport import, and only inside that dedicated package.
    bale_bot_allowed_imports = {"httpx"}
    bale_bot_root = root / "bale_bot"
    for path in root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        in_bale_bot = bale_bot_root in path.parents
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                hit = {item.name.split(".")[0] for item in node.names} & forbidden_imports
                if in_bale_bot:
                    assert not (hit - bale_bot_allowed_imports)
                else:
                    assert not hit
            if isinstance(node, ast.ImportFrom) and node.module:
                top_module = node.module.split(".")[0]
                if top_module in forbidden_imports:
                    assert in_bale_bot and top_module in bale_bot_allowed_imports
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in forbidden_calls
        if "providers/bale/" in path.as_posix():
            assert "http://" not in source and "https://" not in source
            assert "raw_rpc" not in source
        if in_bale_bot:
            # Official Bot API endpoint only; no personal-client RPC markers
            # and no dynamic loading. The endpoint base stays a single constant.
            assert "raw_rpc" not in source
            assert "importlib" not in source and "pkgutil" not in source
            assert source.count("https://") <= 1
            if path.name == "adapter.py":
                assert 'https://tapi.bale.ai' in source

    assert run_worker(
        provider="bale",
        messenger_account_id=str(uuid4()),
        secret_file="missing-secret-file",
    ) == 2
    captured = capsys.readouterr()
    assert "bale_worker_config_required" in captured.err
    assert "missing-secret-file" not in captured.err


def test_provider_extension_observability_events_are_cataloged():
    for name in (
        "provider_adapter_activation_started",
        "provider_adapter_activation_succeeded",
        "provider_adapter_activation_rejected",
        "provider_adapter_activation_failed",
    ):
        assert name in EVENT_CATALOG
    assert EVENT_CATALOG["provider_adapter_activation_rejected"].audit_required is True
