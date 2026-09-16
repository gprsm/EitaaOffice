"""Unit and contract tests for the Bale provider application adapter."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from eitaa_bridge.errors import ProviderExtensionError
from eitaa_bridge.application.bale_client.api import BaleApiError
from eitaa_bridge.application.bale_provider_adapter import BaleProviderApplicationAdapter
from eitaa_bridge.providers.contracts import (
    ProviderAccountContext,
    ProviderAuthOutcome,
    ProviderAuthStage,
    ProviderAuthorizationBasis,
    ProviderCapability,
    ProviderContactAdapter,
    ProviderContactMutationReceipt,
    ProviderContactPage,
    ProviderContactSummary,
    ProviderContactUpsertRequest,
    ProviderDialogPage,
    ProviderDialogSummary,
    ProviderImplementationState,
    ProviderManifest,
    ProviderMediaAdapter,
    ProviderMediaReadReceipt,
    ProviderMediaReadRequest,
    ProviderMessagePage,
    ProviderMessageSummary,
    ProviderOperationContext,
    ProviderPeerReference,
    ProviderSendReceipt,
    ProviderSendStatus,
    ProviderSendTextRequest,
    ProviderSessionState,
    SensitiveProviderValue,
)


def _make_bale_manifest() -> ProviderManifest:
    return ProviderManifest(
        provider="bale",
        display_name="بله",
        account_kind="personal",
        implementation_state=ProviderImplementationState.CONTRACT_VERIFIED,
        authorization_basis=ProviderAuthorizationBasis.WRITTEN_PERMISSION,
        authorization_reference="document:F-046",
        configured=True,
        runtime_enabled=True,
        onboarding_enabled=True,
        account_identity_kind="phone_e164",
        auth_steps=(
            ProviderAuthStage.IDENTITY,
            ProviderAuthStage.CHALLENGE,
            ProviderAuthStage.SECOND_FACTOR_OPTIONAL,
        ),
        capabilities=frozenset(
            {
                ProviderCapability.AUTH_PHONE,
                ProviderCapability.DIALOGS_READ,
                ProviderCapability.HISTORY_READ,
                ProviderCapability.MESSAGES_SEND,
                ProviderCapability.MEDIA_READ,
                ProviderCapability.CONTACTS_READ,
                ProviderCapability.CONTACTS_WRITE,
            }
        ),
    )


def _make_account_context(account_id: str | None = None) -> ProviderAccountContext:
    return ProviderAccountContext(
        messenger_account_id=account_id or str(uuid4()),
        phone_account_id=str(uuid4()),
        provider="bale",
        storage_revision=1,
        session_generation=1,
    )


def _make_operation_context(
    account: ProviderAccountContext | None = None,
) -> ProviderOperationContext:
    account_ctx = account or _make_account_context()
    now_ms = int(time.time() * 1000)
    return ProviderOperationContext(
        account=account_ctx,
        correlation_id=uuid4().hex,
        deadline_unix_ms=now_ms + 60_000,
    )


class TestBaleProviderApplicationAdapterContracts:
    def test_implements_required_protocols(self) -> None:
        from eitaa_bridge.providers.testing import verify_provider_adapter_contract

        manifest = _make_bale_manifest()
        account = _make_account_context()
        mock_api = MagicMock()
        adapter = BaleProviderApplicationAdapter(account, manifest, api=mock_api)

        assert isinstance(adapter, ProviderContactAdapter)
        assert isinstance(adapter, ProviderMediaAdapter)
        assert adapter.manifest == manifest

        report = verify_provider_adapter_contract(adapter, expected_manifest=manifest)
        assert report.adapter_shape_valid is True
        assert report.forbidden_public_members == ()

    def test_scope_enforcement_rejects_mismatched_account(self) -> None:
        manifest = _make_bale_manifest()
        account1 = _make_account_context()
        account2 = _make_account_context()
        mock_api = MagicMock()
        adapter = BaleProviderApplicationAdapter(account1, manifest, api=mock_api)

        wrong_context = _make_operation_context(account2)
        with pytest.raises(ProviderExtensionError) as exc_info:
            asyncio.run(adapter.list_dialogs(wrong_context, cursor=None, limit=10))
        assert exc_info.value.code == "provider_extension_scope_invalid"

    def test_request_challenge_success(self) -> None:
        manifest = _make_bale_manifest()
        account = _make_account_context()
        mock_api = MagicMock()
        mock_api.auth_start = AsyncMock(return_value={"transaction_hash": "tx-12345", "next": "code"})
        adapter = BaleProviderApplicationAdapter(account, manifest, api=mock_api)

        context = _make_operation_context(account)
        phone = SensitiveProviderValue.from_text("+989123456789")
        outcome = asyncio.run(adapter.request_challenge(context, phone))

        assert outcome.state == ProviderSessionState.CHALLENGE_PENDING
        assert outcome.challenge_kind == "phone_code"
        assert outcome.challenge_state is not None
        assert outcome.challenge_state.reveal_bytes().decode("utf-8") == "tx-12345"
        mock_api.auth_start.assert_awaited_once_with("+989123456789")

    def test_request_challenge_maps_error(self) -> None:
        manifest = _make_bale_manifest()
        account = _make_account_context()
        mock_api = MagicMock()
        mock_api.auth_start = AsyncMock(side_effect=BaleApiError("Invalid phone", code="bale_invalid_phone"))
        adapter = BaleProviderApplicationAdapter(account, manifest, api=mock_api)

        context = _make_operation_context(account)
        phone = SensitiveProviderValue.from_text("invalid")
        outcome = asyncio.run(adapter.request_challenge(context, phone))

        assert outcome.state == ProviderSessionState.INVALID
        assert outcome.safe_reason_code == "bale_invalid_phone"

    def test_submit_challenge_authenticated(self) -> None:
        manifest = _make_bale_manifest()
        account = _make_account_context()
        mock_api = MagicMock()
        mock_api.auth_code = AsyncMock(return_value={"authenticated": True, "next": None, "user_id": 9988})
        adapter = BaleProviderApplicationAdapter(account, manifest, api=mock_api)

        context = _make_operation_context(account)
        tx = SensitiveProviderValue.from_text("tx-12345")
        code = SensitiveProviderValue.from_text("123456")
        outcome = asyncio.run(adapter.submit_challenge(context, tx, code))

        assert outcome.state == ProviderSessionState.AUTHENTICATED
        assert outcome.sealed_session is not None
        assert outcome.sealed_session.reveal_bytes().decode("utf-8") == "9988"

    def test_submit_challenge_requires_password(self) -> None:
        manifest = _make_bale_manifest()
        account = _make_account_context()
        mock_api = MagicMock()
        mock_api.auth_code = AsyncMock(return_value={"authenticated": False, "next": "password", "transaction_hash": "tx-12345"})
        adapter = BaleProviderApplicationAdapter(account, manifest, api=mock_api)

        context = _make_operation_context(account)
        tx = SensitiveProviderValue.from_text("tx-12345")
        code = SensitiveProviderValue.from_text("123456")
        outcome = asyncio.run(adapter.submit_challenge(context, tx, code))

        assert outcome.state == ProviderSessionState.SECOND_FACTOR_PENDING
        assert outcome.challenge_kind == "password"
        assert outcome.challenge_state is not None
        assert outcome.challenge_state.reveal_bytes().decode("utf-8") == "tx-12345"

    def test_submit_second_factor_success(self) -> None:
        manifest = _make_bale_manifest()
        account = _make_account_context()
        mock_api = MagicMock()
        mock_api.auth_password = AsyncMock(return_value={"authenticated": True, "user_id": 9988})
        adapter = BaleProviderApplicationAdapter(account, manifest, api=mock_api)

        context = _make_operation_context(account)
        tx = SensitiveProviderValue.from_text("tx-12345")
        password = SensitiveProviderValue.from_text("secret2fa")
        outcome = asyncio.run(adapter.submit_second_factor(context, tx, password))

        assert outcome.state == ProviderSessionState.AUTHENTICATED
        assert outcome.sealed_session is not None
        assert outcome.sealed_session.reveal_bytes().decode("utf-8") == "9988"

    def test_validate_session(self) -> None:
        manifest = _make_bale_manifest()
        account = _make_account_context()
        mock_api = MagicMock()
        mock_api.account_card = AsyncMock(return_value={"authenticated": True, "user_id": 9988})
        adapter = BaleProviderApplicationAdapter(account, manifest, api=mock_api)

        context = _make_operation_context(account)
        sealed = SensitiveProviderValue.from_text("9988")
        outcome = asyncio.run(adapter.validate_session(context, sealed))

        assert outcome.state == ProviderSessionState.AUTHENTICATED

    def test_list_dialogs_maps_to_provider_dialog_page(self) -> None:
        manifest = _make_bale_manifest()
        account = _make_account_context()
        mock_api = MagicMock()
        mock_api.list_dialogs = AsyncMock(
            return_value=[
                {"peer": {"id": 1001, "type": 1}, "title": "کاربر الف", "unread_count": 2},
                {"peer": {"id": 1002, "type": 2}, "title": "گروه تست", "unread_count": 0},
            ]
        )
        adapter = BaleProviderApplicationAdapter(account, manifest, api=mock_api)

        context = _make_operation_context(account)
        page = asyncio.run(adapter.list_dialogs(context, cursor=None, limit=20))

        assert isinstance(page, ProviderDialogPage)
        assert len(page.dialogs) == 2
        d1, d2 = page.dialogs
        assert d1.peer == ProviderPeerReference("1001", "private")
        assert d1.title == "کاربر الف"
        assert d1.unread_count == 2
        assert d2.peer == ProviderPeerReference("1002", "group")
        assert d2.title == "گروه تست"

    def test_load_history_maps_to_provider_message_page(self) -> None:
        manifest = _make_bale_manifest()
        account = _make_account_context()
        mock_api = MagicMock()
        mock_api.read_history = AsyncMock(
            return_value=[
                {
                    "message_id": 9001,
                    "sender_id": 1001,
                    "date": 1726000000,
                    "text": "سلام",
                    "media": None,
                },
                {
                    "message_id": 9002,
                    "sender_id": 9988,
                    "date": 1726000010,
                    "text": "علیک سلام",
                    "media": None,
                },
            ]
        )
        adapter = BaleProviderApplicationAdapter(account, manifest, api=mock_api)

        context = _make_operation_context(account)
        peer = ProviderPeerReference("1001", "private")
        page = asyncio.run(adapter.load_history(context, peer=peer, cursor=None, limit=10))

        assert isinstance(page, ProviderMessagePage)
        assert len(page.messages) == 2
        m1, m2 = page.messages
        assert m1.message_reference == "9001"
        assert m1.peer == peer
        assert m1.sender_reference == "1001"
        assert m1.sent_at_unix_ms == 1726000000000
        assert m1.text == "سلام"

    def test_send_text_returns_success_receipt(self) -> None:
        manifest = _make_bale_manifest()
        account = _make_account_context()
        mock_api = MagicMock()
        mock_api.send_text = AsyncMock(return_value={"message_id": 4091180017836933156, "date": 1726000000})
        adapter = BaleProviderApplicationAdapter(account, manifest, api=mock_api)

        context = _make_operation_context(account)
        request = ProviderSendTextRequest(
            peer=ProviderPeerReference("1001", "private"),
            text="پیام تستی",
            idempotency_key="a" * 32,
        )
        receipt = asyncio.run(adapter.send_text(context, request))

        assert isinstance(receipt, ProviderSendReceipt)
        assert receipt.status == ProviderSendStatus.SUCCEEDED
        assert receipt.message_reference == "4091180017836933156"
        mock_api.send_text.assert_awaited_once_with(1001, "پیام تستی")

    def test_send_text_maps_access_denied_to_safe_receipt(self) -> None:
        manifest = _make_bale_manifest()
        account = _make_account_context()
        mock_api = MagicMock()
        mock_api.send_text = AsyncMock(side_effect=BaleApiError("Access denied", code="bale_access_denied"))
        adapter = BaleProviderApplicationAdapter(account, manifest, api=mock_api)

        context = _make_operation_context(account)
        request = ProviderSendTextRequest(
            peer=ProviderPeerReference("1001", "private"),
            text="پیام تستی",
            idempotency_key="a" * 32,
        )
        receipt = asyncio.run(adapter.send_text(context, request))

        assert receipt.status == ProviderSendStatus.UNCERTAIN
        assert receipt.safe_reason_code == "bale_access_denied"

    def test_list_contacts_prioritizes_local_name(self) -> None:
        manifest = _make_bale_manifest()
        account = _make_account_context()
        mock_api = MagicMock()
        mock_api.list_contacts = AsyncMock(
            return_value=[
                {
                    "peer": {"id": 2001, "type": 1},
                    "name": "محسن (نام مستعار)",
                    "username": "m_akhoondian",
                    "is_bot": False,
                    "access_hash": 12345,
                },
                {
                    "peer": {"id": 2002, "type": 1},
                    "name": "محمد",
                    "username": None,
                    "is_bot": False,
                    "access_hash": 67890,
                },
            ]
        )
        adapter = BaleProviderApplicationAdapter(account, manifest, api=mock_api)

        context = _make_operation_context(account)
        page = asyncio.run(adapter.list_contacts(context, cursor=None, limit=50))

        assert isinstance(page, ProviderContactPage)
        assert len(page.contacts) == 2
        c1, c2 = page.contacts
        assert c1.contact_reference == "2001"
        assert c1.display_name == "محسن (نام مستعار)"
        assert c1.identity_hint == "m_akhoondian"
        assert c2.contact_reference == "2002"
        assert c2.display_name == "محمد"
        assert c2.identity_hint is None

    def test_upsert_contact_by_phone_calls_add_contact_by_phone(self) -> None:
        manifest = _make_bale_manifest()
        account = _make_account_context()
        mock_api = MagicMock()
        mock_api.add_contact_by_phone = AsyncMock(
            return_value={
                "phone": 989123456789,
                "matched": True,
                "users": [{"id": 3001, "name": "مخاطب جدید"}],
            }
        )
        adapter = BaleProviderApplicationAdapter(account, manifest, api=mock_api)

        context = _make_operation_context(account)
        request = ProviderContactUpsertRequest(
            identity=SensitiveProviderValue.from_text("+989123456789"),
            display_name="مخاطب جدید",
            idempotency_key="b" * 32,
        )
        receipt = asyncio.run(adapter.upsert_contact(context, request))

        assert isinstance(receipt, ProviderContactMutationReceipt)
        assert receipt.contact_reference == "3001"
        assert receipt.created is True
        mock_api.add_contact_by_phone.assert_awaited_once_with("+989123456789", "مخاطب جدید")

    def test_read_media_success(self, tmp_path: Path) -> None:
        manifest = _make_bale_manifest()
        account = _make_account_context()
        fake_file = tmp_path / "received_photo.jpg"
        fake_file.write_bytes(b"dummy jpeg content")

        mock_api = MagicMock()
        mock_api.read_message_media = AsyncMock(return_value=fake_file)
        adapter = BaleProviderApplicationAdapter(account, manifest, api=mock_api, media_dir=tmp_path)

        context = _make_operation_context(account)
        request = ProviderMediaReadRequest(
            peer=ProviderPeerReference("1001", "private"),
            message_reference="9001",
            media_reference="photo-9001",
            variant="thumbnail",
        )
        receipt = asyncio.run(adapter.read_media(context, request))

        assert isinstance(receipt, ProviderMediaReadReceipt)
        assert receipt.media_reference == "photo-9001"
        assert receipt.mime_type == "image/jpeg"
        assert receipt.byte_count == len(b"dummy jpeg content")
