"""Offline tests for the Bale branch modular API (Phase 1).

Everything here is contract/unit level: no network, no real Bale servers, no
credentials. WebSocket RPC calls are faked at the engine boundary with
hand-built protobuf responses, so the typed decoders and the facade are
exercised exactly as they will run live.
"""

from __future__ import annotations

import asyncio
import base64
import json
import threading
import time
import urllib.request
from pathlib import Path
from uuid import uuid4

import pytest

from eitaa_bridge.application.bale_client.api import BaleApi, BaleApiError
from eitaa_bridge.application.bale_client.codecs import (
    build_send_message,
    decode_history,
    encode_document_content,
    encode_text_content,
)
from eitaa_bridge.application.bale_client.codecs_ext import (
    build_import_contacts,
    classify_media,
    decode_contact_summaries,
    decode_dialog_summaries,
    decode_users,
    peer_from_identifier,
)
from eitaa_bridge.application.bale_client.models import FileDetails, Peer, PeerType, SendType
from eitaa_bridge.application.bale_client.wire import ProtoWriter, get_first, parse_fields


# ---------------------------------------------------------------------------
# Wire builders / typed decoders
# ---------------------------------------------------------------------------


def _user_record(user_id: int, name: str, *, access_hash: int = 777, username: bytes | None = None) -> bytes:
    writer = (
        ProtoWriter()
        .int64(1, user_id)
        .int64(2, access_hash)
        .string(3, name)
    )
    if username:
        writer.string(9, username.decode())
    return writer.build()


class TestCodecsExt:
    def test_build_import_contacts_shape(self) -> None:
        raw = build_import_contacts([(989120000111, "علی"), (989120000222, "Sara")])
        fields = parse_fields(raw)
        entries = [f.value for f in fields if f.number == 1]
        assert len(entries) == 2
        first = parse_fields(entries[0])
        assert get_first(first, 1) == 989120000111
        name_wrapper = parse_fields(get_first(first, 2))
        assert get_first(name_wrapper, 1) == "علی".encode("utf-8")

    def test_decode_users_top_level_container(self) -> None:
        payload = (
            ProtoWriter()
            .message(1, _user_record(10, "Ali", username=b"ali"))
            .message(1, _user_record(20, "Sara"))
            .build()
        )
        records = decode_users(payload)
        assert [r.id for r in records] == [10, 20]
        assert records[0].name == "Ali"
        assert records[0].username == "ali"
        assert records[0].access_hash == 777

    def test_decode_users_ignores_non_user_blobs(self) -> None:
        noise = ProtoWriter().string(1, "not-a-user").build()
        payload = ProtoWriter().message(4, noise).build()
        assert decode_users(payload) == []

    def test_decode_users_wrapped_container_one_level_deep(self) -> None:
        inner = ProtoWriter().message(1, _user_record(31, "Wrapped")).build()
        payload = ProtoWriter().message(2, inner).build()
        records = decode_users(payload)
        assert [r.id for r in records] == [31]
        assert records[0].name == "Wrapped"

    def test_decode_contact_summaries_via_user_record(self) -> None:
        payload = ProtoWriter().message(1, _user_record(50, "Contact Name")).build()
        summaries = decode_contact_summaries(payload)
        assert len(summaries) == 1
        assert summaries[0].peer.id == 50
        assert summaries[0].name == "Contact Name"

    def test_decode_dialog_summaries(self) -> None:
        peer = ProtoWriter().int32(1, 1).int64(2, 4242).build()
        entry = (
            ProtoWriter()
            .message(1, peer)
            .int32(2, 3)
            .int64(3, 1700000000000)
            .int64(4, 4242)
            .int64(5, 900)
            .int64(6, 1700000000000)
            .message(7, encode_text_content("آخرین پیام"))
            .build()
        )
        payload = ProtoWriter().message(3, entry).build()
        dialogs = decode_dialog_summaries(payload)
        assert len(dialogs) == 1
        assert dialogs[0].peer.id == 4242
        assert dialogs[0].unread_count == 3
        assert dialogs[0].last_text == "آخرین پیام"
        assert dialogs[0].last_message_id == 900

    def test_classify_media(self) -> None:
        assert classify_media(FileDetails(1, 0, "a.jpg", 1, "image/jpeg")) == "photo"
        assert classify_media(FileDetails(1, 0, "a.mp4", 1, "video/mp4")) == "video"
        assert classify_media(FileDetails(1, 0, "a.mp3", 1, "audio/mpeg")) == "audio"
        assert classify_media(FileDetails(1, 0, "a.pdf", 1, "application/pdf")) == "document"

    def test_peer_from_identifier(self) -> None:
        peer = peer_from_identifier("4242")
        assert peer.id == 4242
        assert peer.type == PeerType.PRIVATE


# ---------------------------------------------------------------------------
# Engine-level fake: a connected client whose RPC calls return canned bytes
# ---------------------------------------------------------------------------


class FakeWebSocket:
    def __init__(self) -> None:
        self.connected = True
        self.calls: list[tuple[str, str, bytes]] = []
        self.responses: dict[tuple[str, str], bytes] = {}

    async def rpc(self, service: str, method: str, payload: bytes = b"", timeout: float | None = None) -> bytes:
        self.calls.append((service, method, payload))
        return self.responses.get((service, method), b"")


class FakeBaleClient:
    """Duck-typed stand-in for BaleClient; the facade only touches these."""

    def __init__(self, vault_path: Path) -> None:
        self.config = type("C", (), {"vault_path": vault_path, "log_path": Path(vault_path.parent / "bale.log")})()
        self.session = None
        self.ws = FakeWebSocket()
        self._last_auth_start_registered = True

        class Vault:
            def __init__(self, path: Path) -> None:
                self.path = path

            def exists(self) -> bool:
                return self.path.exists()

        self.vault = Vault(vault_path)

    async def connect(self, *, subscribe: bool = True, presence: bool = True) -> None:
        pass

    async def close(self) -> None:
        pass

    async def load_history(self, peer, *, limit=20, offset_date=None, load_mode=2):
        user_record = _user_record(peer.id, "x")
        content = encode_text_content("hello from history")
        message = ProtoWriter().int64(1, 1).int64(2, 55).int64(3, 1700000000).message(4, content).build()
        container = ProtoWriter().message(1, message).build()
        return decode_history(container, peer)

    async def upload_file(self, path, *, peer=None, send_type=SendType.DOCUMENT, mime_type=None, progress=None):
        details = FileDetails(1234, 5678, Path(path).name, Path(path).stat().st_size, "image/jpeg")
        return details, b""

    async def download_file(self, details, destination, *, progress=None):
        out = Path(destination)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"fake-image-bytes")
        return out

    async def raw_rpc(self, service: str, method: str, payload: bytes = b"") -> bytes:
        return await self.ws.rpc(service, method, payload)

    async def auth_start(self, phone):
        self._last_auth_start_registered = True
        return "tx-hash-1"

    async def auth_code(self, transaction_hash, code, *, is_registered_hint=None, passphrase=None):
        from eitaa_bridge.application.bale_client.models import BaleSession

        return type(
            "Outcome",
            (),
            {"session": BaleSession(access_token="t", jwt="j", user_id=4242), "password_required": False, "signup_required": False},
        )()

    async def load_session(self, passphrase=None):
        raise FileNotFoundError


def _make_api(tmp_path: Path, registered_response: bytes | None = None) -> BaleApi:
    client = FakeBaleClient(tmp_path / "session.vault")
    if registered_response is not None:
        client.ws.responses[(client.config and "bale.users.v1.Users", "GetContacts")] = registered_response
    api = BaleApi.__new__(BaleApi)
    object.__setattr__(api, "_client", client)
    object.__setattr__(api, "_auth_start_hint", None)
    return api


class TestBaleApiFacade:
    def test_require_connected_raises_clean_code(self) -> None:
        api = _make_api(Path("."))
        api._client.ws.connected = False
        with pytest.raises(BaleApiError) as err:
            asyncio.run(api.list_contacts())
        assert err.value.code == "bale_not_connected"

    def test_list_contacts_returns_typed_summaries(self) -> None:
        users = ProtoWriter().message(1, _user_record(99, "Contact A")).message(1, _user_record(88, "Contact B")).build()
        api = _make_api(Path("."))
        api._client.ws.responses[("bale.users.v1.Users", "GetContacts")] = users
        contacts = asyncio.run(api.list_contacts())
        assert {c["peer"]["id"] for c in contacts} == {99, 88}
        names = {c["name"] for c in contacts}
        assert names == {"Contact A", "Contact B"}

    def test_add_contact_by_phone_builds_import_contacts(self) -> None:
        api = _make_api(Path("."))
        matched = ProtoWriter().message(1, _user_record(77, "Matched User")).build()
        api._client.ws.responses[("bale.users.v1.Users", "ImportContacts")] = matched
        result = asyncio.run(api.add_contact_by_phone("+98 912 000 0011", "Ali"))
        assert result["phone"] == 989120000011
        assert result["matched"] is True
        assert result["users"][0]["id"] == 77
        service, method, payload = api._client.ws.calls[0]
        assert method == "ImportContacts"
        entries = [f.value for f in parse_fields(payload) if f.number == 1]
        assert len(entries) == 1

    def test_add_and_remove_contact_by_user_id(self) -> None:
        api = _make_api(Path("."))
        result = asyncio.run(api.add_contact(1234))
        assert result == {"user_id": 1234, "added": True}
        result = asyncio.run(api.remove_contact(1234))
        assert result == {"user_id": 1234, "removed": True}
        methods = [c[1] for c in api._client.ws.calls]
        assert methods == ["AddContact", "RemoveContact"]

    def test_send_text_builds_expected_payload(self) -> None:
        api = _make_api(Path("."))
        result = asyncio.run(api.send_text(4242, "سلام"))
        assert result["sent"] is True
        service, method, payload = api._client.ws.calls[0]
        assert method == "SendMessage"
        fields = parse_fields(payload)
        peer_raw = get_first(fields, 1)
        peer_fields = parse_fields(peer_raw)
        assert get_first(peer_fields, 2) == 4242
        content = parse_fields(get_first(fields, 3))
        text = parse_fields(get_first(content, 15))
        assert get_first(text, 1) == "سلام".encode("utf-8")

    def test_send_text_rejects_empty(self) -> None:
        api = _make_api(Path("."))
        with pytest.raises(BaleApiError) as err:
            asyncio.run(api.send_text(1, "   "))
        assert err.value.code == "bale_empty_text"

    def test_send_photo_uses_photo_mime(self, tmp_path: Path) -> None:
        api = _make_api(tmp_path)
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"jpegdata")
        result = asyncio.run(api.send_photo(4242, str(img), caption="توضیح"))
        assert result["media_kind"] == "photo"
        assert result["sent"] is True
        service, method, payload = api._client.ws.calls[-1]
        assert method == "SendMessage"
        fields = parse_fields(payload)
        content = parse_fields(get_first(fields, 3))
        doc = parse_fields(get_first(content, 4))
        assert get_first(doc, 5) == b"image/jpeg"

    def test_read_history_returns_typed_dicts(self) -> None:
        api = _make_api(Path("."))
        history = asyncio.run(api.read_history(4242, limit=5))
        assert len(history) == 1
        assert history[0]["message_id"] == 55
        assert history[0]["text"] == "hello from history"
        assert history[0]["media"] is None

    def test_read_message_media_downloads_document(self, tmp_path: Path) -> None:
        api = _make_api(tmp_path)
        # Patch load_history to return a message with a document
        from eitaa_bridge.application.bale_client.models import Message

        doc = FileDetails(111, 222, "photo.png", 9, "image/png")
        message = Message(peer=Peer(id=4242), sender_id=1, message_id=55, date=1, document=doc)

        async def fake_history(peer, *, limit=20, offset_date=None, load_mode=2):
            return [message]

        api._client.load_history = fake_history  # type: ignore[method-assign]
        destination = tmp_path / "downloads"
        result = asyncio.run(api.read_message_media(4242, 55, destination))
        assert result["message_id"] == 55
        assert result["media_kind"] == "photo"
        assert (destination / "photo.png").read_bytes() == b"fake-image-bytes"

    def test_read_message_media_missing_document_raises(self, tmp_path: Path) -> None:
        api = _make_api(tmp_path)
        with pytest.raises(BaleApiError) as err:
            asyncio.run(api.read_message_media(4242, 55, tmp_path))
        assert err.value.code == "bale_media_not_found"

    def test_send_file_missing_path(self) -> None:
        api = _make_api(Path("."))
        with pytest.raises(BaleApiError) as err:
            asyncio.run(api.send_file(4242, "Z:/nope/missing.bin"))
        assert err.value.code == "bale_file_missing"

    def test_account_card_hides_tokens(self) -> None:
        from eitaa_bridge.application.bale_client.models import BaleSession

        api = _make_api(Path("."))
        api._client.session = BaleSession(access_token="SECRET-TOKEN", jwt="SECRET.JWT", user_id=1)
        card = asyncio.run(api.account_card())
        assert card == {"authenticated": True, "user_id": 1, "expires_at": None, "has_vault": False}
        assert "SECRET" not in json.dumps(card)

    def test_rpc_error_maps_to_stable_code(self) -> None:
        from eitaa_bridge.application.bale_client.errors import RpcError

        api = _make_api(Path("."))

        async def failing_rpc(service, method, payload=b"", timeout=None):
            raise RpcError(5, "boom")

        api._client.ws.rpc = failing_rpc  # type: ignore[method-assign]
        with pytest.raises(BaleApiError) as err:
            asyncio.run(api.list_contacts())
        assert err.value.code == "bale_rpc_error"


# ---------------------------------------------------------------------------
# HTTP server (loopback, real socket, fake service layer)
# ---------------------------------------------------------------------------


class TestApiServer:
    @pytest.fixture
    def server(self, tmp_path: Path):
        from eitaa_bridge.application.bale_client import api_server

        service = api_server.BaleApiService(
            vault_path=tmp_path / "session.vault", log_path=tmp_path / "bale.log"
        )
        fake_api = _make_api(tmp_path)
        users = ProtoWriter().message(1, _user_record(99, "Server Contact")).build()
        fake_api._client.ws.responses[("bale.users.v1.Users", "GetContacts")] = users
        fake_api._client.ws.responses[("bale.users.v1.Users", "ImportContacts")] = users
        service.api = fake_api
        token = "test-token-123"
        httpd = api_server.build_server(
            host="127.0.0.1", port=0, token=token,
            vault_path=tmp_path / "session.vault", log_path=tmp_path / "bale.log",
        )
        # Reuse the prepared service on the bound handler class.
        httpd.RequestHandlerClass.service = service  # type: ignore[attr-defined]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        port = httpd.server_address[1]
        yield f"http://127.0.0.1:{port}", api_server.ROUTE_PREFIX, token
        httpd.shutdown()
        httpd.server_close()

    def _request(self, url: str, path: str, token: str, body: dict | None = None, method: str | None = None):
        target = f"{url}{path}"
        # No-body calls default to POST with an empty JSON object; routes like
        # contacts/list take an optional body.
        data = json.dumps(body or {}).encode("utf-8")
        req = urllib.request.Request(target, data=data, method=method or "POST")
        req.add_header("Authorization", f"Bearer {token}")
        if data:
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_health_and_root(self, server) -> None:
        url, prefix, token = server
        health = self._request(url, f"{prefix}/health", token, method="GET")
        assert health["ok"] is True
        assert "connected" in health
        root = json.loads(urllib.request.urlopen(url, timeout=5).read().decode("utf-8"))
        assert root["service"] == "bale-branch-api"

    def test_auth_rejects_missing_token(self, server) -> None:
        url, prefix, _ = server
        req = urllib.request.Request(f"{url}{prefix}/account", method="GET")
        try:
            urllib.request.urlopen(req, timeout=5)
            raise AssertionError("expected 401")
        except urllib.error.HTTPError as err:
            assert err.code == 401

    def test_contacts_flow_over_http(self, server) -> None:
        url, prefix, token = server
        contacts = self._request(url, f"{prefix}/contacts/list", token)
        assert contacts[0]["peer"]["id"] == 99
        added = self._request(
            url, f"{prefix}/contacts/add-phone", token,
            {"phone": "989120000011", "name": "Ali"},
        )
        assert added["matched"] is True

    def test_send_text_over_http(self, server) -> None:
        url, prefix, token = server
        result = self._request(
            url, f"{prefix}/messages/send-text", token,
            {"user_id": 4242, "text": "سلام"},
        )
        assert result["sent"] is True
        assert result["user_id"] == 4242

    def test_missing_field_returns_400(self, server) -> None:
        url, prefix, token = server
        try:
            self._request(url, f"{prefix}/messages/send-text", token, {"user_id": 1})
            raise AssertionError("expected 400")
        except urllib.error.HTTPError as err:
            assert err.code == 400
            payload = json.loads(err.read().decode("utf-8"))
            assert payload["error"] == "bale_missing_field"

    def test_unknown_route_404(self, server) -> None:
        url, prefix, token = server
        try:
            self._request(url, f"{prefix}/channels/list", token)
            raise AssertionError("expected 404")
        except urllib.error.HTTPError as err:
            assert err.code == 404
