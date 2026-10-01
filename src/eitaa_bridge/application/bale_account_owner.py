"""Account-owned Bale connection on one persistent asyncio loop.

The provider WebSocket never crosses request-local asyncio.run loops. Creating
this owner does not connect, request an OTP, import contacts, or send anything.
Only explicit method calls can produce provider traffic.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
from concurrent.futures import Future
import os
from pathlib import Path
import stat
import threading
import time
from typing import Any, Callable
from uuid import UUID, uuid4

from ..errors import ProviderExtensionError

_DIALOG_NAME_REFRESH_SECONDS = 300


def _account_directory(base_directory: Path, account_id: str) -> Path:
    try:
        parsed = UUID(account_id)
    except (ValueError, AttributeError) as exc:
        raise ProviderExtensionError("Invalid Bale account scope.", code="provider_extension_scope_invalid") from exc
    if parsed.version != 4 or str(parsed) != account_id:
        raise ProviderExtensionError("Invalid Bale account scope.", code="provider_extension_scope_invalid")
    base = base_directory.resolve()
    directory = base / "data" / "providers" / "bale" / account_id
    for path in (directory, *directory.parents):
        if path == base:
            break
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise ProviderExtensionError("Invalid account storage boundary.", code="bale_vault_path_invalid")
    return directory


class BaleAccountSecret:
    """Server-owned account key. POSIX 0600 or Windows machine DPAPI."""

    def __init__(self, account_directory: Path) -> None:
        self.directory = account_directory
        self.path = account_directory / ("vault.key.dpapi" if os.name == "nt" else "vault.key")

    def passphrase(self) -> str:
        if self.path.exists() or self.path.is_symlink():
            key = self._read()
        else:
            self.directory.mkdir(parents=True, exist_ok=True)
            from ..infrastructure.worker_ipc.secret_file import _restrict_to_current_user
            _restrict_to_current_user(self.directory)
            if os.name != "nt":
                os.chmod(self.directory, 0o700)
            key = os.urandom(32)
            if os.name == "nt":
                from ..infrastructure.coordinator.identity import _protect_data
                stored = _protect_data(key, entropy=None, description="Bale account vault key", machine_scope=True)
            else:
                stored = key
            try:
                descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
            except FileExistsError:
                key = self._read()
            else:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(stored)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.chmod(self.path, 0o600)
                _restrict_to_current_user(self.path)
        return base64.urlsafe_b64encode(key).decode("ascii")

    def _read(self) -> bytes:
        metadata = self.path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or (
            os.name != "nt" and stat.S_IMODE(metadata.st_mode) & 0o077
        ):
            raise ProviderExtensionError("Invalid Bale account secret file.", code="bale_vault_key_invalid")
        stored = self.path.read_bytes()
        if os.name == "nt":
            from ..infrastructure.coordinator.identity import _unprotect_data
            key = _unprotect_data(stored, entropy=None)
        else:
            key = stored
        if len(key) != 32:
            raise ProviderExtensionError("Invalid Bale account secret file.", code="bale_vault_key_invalid")
        return key


class BaleAccountOwner:
    """Serialized access to a single facade, bound to a dedicated event loop."""

    def __init__(
        self,
        base_directory: str | Path,
        messenger_account_id: str,
        *,
        backend_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.directory = _account_directory(Path(base_directory), messenger_account_id)
        self._backend_factory = backend_factory
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._closed = False
        self._client: Any = None
        self._dialog_contact_names: dict[int, str] = {}
        self._dialog_names_checked_at = 0.0
        self._thread = threading.Thread(
            target=self._run, name=f"bale-account-{messenger_account_id[:8]}", daemon=True
        )
        self._thread.start()
        self._ready.wait(timeout=5)
        if not self._ready.is_set():
            raise ProviderExtensionError("Bale account loop did not start.", code="bale_runtime_start_failed")

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._ready.set()
        self._loop.run_forever()
        self._loop.close()

    async def _invoke(self, name: str, *args: Any, **kwargs: Any) -> Any:
        if self._closed:
            raise ProviderExtensionError("Bale account owner is closed.", code="bale_runtime_closed")

        async def call() -> Any:
            if self._client is None:
                phrase = BaleAccountSecret(self.directory).passphrase()
                factory = self._backend_factory
                if factory is None:
                    from .bale_client.api import BaleApi
                    factory = BaleApi.create
                self._client = factory(
                    passphrase=phrase,
                    vault_path=self.directory / "session.vault",
                    log_path=self.directory / "client.log",
                )
            method = getattr(self._client, name)
            if name in {"auth_code", "auth_password", "connect"}:
                kwargs["passphrase"] = BaleAccountSecret(self.directory).passphrase()
            return await method(*args, **kwargs)

        pending: Future[Any] = asyncio.run_coroutine_threadsafe(call(), self._loop)
        try:
            return await asyncio.wrap_future(pending)
        except asyncio.CancelledError:
            pending.cancel()
            raise

    async def auth_start(self, phone: str) -> dict[str, Any]:
        return await self._invoke("auth_start", phone)

    async def auth_code(self, transaction_hash: str, code: str) -> dict[str, Any]:
        result = await self._invoke("auth_code", transaction_hash, code)
        if result.get("authenticated") is True:
            self._dialog_contact_names.clear()
            self._dialog_names_checked_at = 0.0
        return result

    async def auth_password(self, transaction_hash: str, password: str) -> dict[str, Any]:
        result = await self._invoke("auth_password", transaction_hash, password)
        if result.get("authenticated") is True:
            self._dialog_contact_names.clear()
            self._dialog_names_checked_at = 0.0
        return result

    async def connect(self, *, subscribe: bool = False) -> dict[str, Any]:
        try:
            return await self._invoke("connect", subscribe=subscribe)
        except Exception as exc:
            logger = getattr(self._client, "log", None)
            if logger is not None:
                logger.warning("bale_connect_failed type=%s", type(exc).__name__)
            raise

    async def list_contacts(self) -> list[dict[str, Any]]:
        return await self._invoke("list_contacts")

    async def search_contacts(self, query: str) -> list[dict[str, Any]]:
        return await self._invoke("search_contacts", query)

    async def add_contact_by_phone(self, phone: str, name: str) -> dict[str, Any]:
        existing = await self.lookup_phone(phone)
        if existing is not None:
            return {"matched": True, "users": [{"id": existing}], "created": False}
        result = await self._invoke("add_contact_by_phone", phone, name)
        self._dialog_names_checked_at = 0.0
        users = result.get("users") if result.get("matched") is True else None
        if isinstance(users, list) and len(users) == 1:
            item = users[0]
            peer_id = int(item.get("id") or (item.get("peer") or {}).get("id") or 0)
            if peer_id > 0:
                await self._phone_mapping(phone, peer_id)
        return result

    async def _phone_mapping(self, phone: str, peer_id: int | None = None) -> int | None:
        async def mapping():
            key = BaleAccountSecret(self.directory).passphrase().encode()
            fingerprint = hmac.new(key, phone.encode(), hashlib.sha256).hexdigest()
            path = self.directory / "contact-bindings.json"
            if path.is_symlink():
                raise ProviderExtensionError("Invalid contact storage.", code="bale_contact_storage_invalid")
            items = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
            if peer_id is not None:
                items[fingerprint] = peer_id
                temporary = self.directory / f"bindings.{uuid4().hex}.tmp"
                temporary.write_text(json.dumps(items), encoding="utf-8")
                os.replace(temporary, path)
            found = items.get(fingerprint)
            return found if isinstance(found, int) and found > 0 else None
        return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(mapping(), self._loop))

    async def lookup_phone(self, phone: str) -> int | None:
        found = await self._phone_mapping(phone)
        contacts = await self.list_contacts()
        if found is not None and any((item.get("peer") or {}).get("id") == found for item in contacts):
            return found
        matches = await self._invoke("lookup_contact_by_phone", phone)
        peers = {int(item["peer"]["id"]) for item in matches
                 if isinstance(item.get("peer"), dict) and item["peer"].get("type") == 1 and int(item["peer"].get("id") or 0) > 0}
        if len(peers) > 1:
            raise ProviderExtensionError("Contact match is ambiguous.", code="bale_contact_match_ambiguous")
        candidate = next(iter(peers), None)
        # Exact search is usable only when it names a contact in this account.
        return candidate if candidate is not None and any((item.get("peer") or {}).get("id") == candidate for item in contacts) else None

    async def add_contact(self, user_id: int) -> dict[str, Any]:
        result = await self._invoke("add_contact", user_id)
        self._dialog_names_checked_at = 0.0
        return result

    async def remove_contact(self, user_id: int) -> dict[str, Any]:
        result = await self._invoke("remove_contact", user_id)
        self._dialog_names_checked_at = 0.0
        return result

    async def list_dialogs(self, *, limit: int = 20, offset_date: int | None = None) -> list[dict[str, Any]]:
        kwargs = {"limit": limit}
        if offset_date is not None:
            kwargs["offset_date"] = offset_date
        items = await self._invoke("list_dialogs", **kwargs)
        needs_names = any(
            not item.get("title") and isinstance(item.get("peer"), dict)
            and item["peer"].get("type") == 1 for item in items
        )
        if not needs_names:
            return items
        now = time.monotonic()
        if self._dialog_names_checked_at == 0.0 or now - self._dialog_names_checked_at >= _DIALOG_NAME_REFRESH_SECONDS:
            self._dialog_names_checked_at = now
            try:
                contacts = await self.list_contacts()
            except Exception as exc:
                # Enriching a title is optional. A rate-limited GetContacts
                # must not turn an otherwise valid dialog page into an error.
                if getattr(exc, "code", None) != "bale_rpc_error":
                    raise
            else:
                self._dialog_contact_names = {
                    int(item["peer"]["id"]): str(item.get("local_name") or item.get("name"))
                    for item in contacts if isinstance(item.get("peer"), dict)
                    and item["peer"].get("type") == 1
                    and (item.get("local_name") or item.get("name"))
                }
        for item in items:
            peer = item.get("peer") or {}
            if not item.get("title") and peer.get("type") == 1 and self._dialog_contact_names.get(peer.get("id")):
                item["title"] = self._dialog_contact_names[peer["id"]]
        return items

    async def read_history(self, user_id: int, *, limit: int = 20, offset_date: int | None = None) -> list[dict[str, Any]]:
        kwargs = {"limit": limit}
        if offset_date is not None:
            kwargs["offset_date"] = offset_date
        return await self._invoke("read_history", user_id, **kwargs)

    async def send_text(self, user_id: int, text: str) -> dict[str, Any]:
        return await self._invoke("send_text", user_id, text)

    async def send_file_bytes(self, user_id: int, name: str, data: bytes, *, caption: str = "") -> dict[str, Any]:
        return await self._invoke("send_file_bytes", user_id, name, data,
                                  caption=caption, staging_dir=self.directory / "uploads")

    async def read_media_bytes(self, user_id: int, message_id: int, *, max_bytes: int) -> dict[str, Any]:
        result = await self._invoke("read_message_media", user_id, message_id,
                                    self.directory / "downloads", max_bytes=max_bytes)
        path = Path(result["path"])
        if path.parent.resolve() != (self.directory / "downloads").resolve() or path.is_symlink():
            raise ProviderExtensionError("Invalid media storage.", code="bale_media_path_invalid")
        try:
            if path.stat().st_size > max_bytes:
                raise ProviderExtensionError("Media is too large.", code="bale_media_too_large")
            return {"data_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
                    "mime_type": result.get("mime_type") or "application/octet-stream"}
        finally:
            path.unlink(missing_ok=True)

    async def logout(self) -> bool:
        """Explicit local revocation; archive this account's vault without deleting it."""
        if self._closed:
            raise ProviderExtensionError("Bale account owner is closed.", code="bale_runtime_closed")
        self._dialog_contact_names.clear()
        self._dialog_names_checked_at = 0.0

        async def revoke() -> bool:
            if self._client is not None:
                await self._client.close()
                self._client = None
            vault = self.directory / "session.vault"
            if not vault.is_file() or vault.is_symlink():
                return False
            os.replace(vault, self.directory / f"session.revoked.{uuid4().hex}")
            return True

        pending = asyncio.run_coroutine_threadsafe(revoke(), self._loop)
        return await asyncio.wrap_future(pending)

    async def has_vault(self) -> bool:
        async def inspect() -> bool:
            vault = self.directory / "session.vault"
            return vault.is_file() and not vault.is_symlink()

        pending = asyncio.run_coroutine_threadsafe(inspect(), self._loop)
        return await asyncio.wrap_future(pending)

    async def close(self) -> None:
        if self._closed:
            return
        if self._client is not None:
            pending = asyncio.run_coroutine_threadsafe(self._client.close(), self._loop)
            await asyncio.wrap_future(pending)
        self._closed = True
        self._loop.call_soon_threadsafe(self._loop.stop)
        await asyncio.to_thread(self._thread.join, 5)
