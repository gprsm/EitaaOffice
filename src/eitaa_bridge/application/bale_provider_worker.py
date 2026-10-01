"""Bounded account-owned Bale worker operations for in-process and Child hosts."""



from __future__ import annotations



import asyncio

import base64

import json

import os

from pathlib import Path

import time

from typing import Any, Mapping

from uuid import UUID, uuid4



from ..errors import WorkerIpcError

from ..infrastructure.worker_ipc import IPC_PROTOCOL_VERSION, IpcEnvelope

from ..providers.contracts import ProviderWorkerDispatchResult

from .bale_account_owner import BaleAccountOwner


_CONTACT_SNAPSHOT_MAX_ITEMS = 5000
_CONTACT_SNAPSHOT_MAX_BYTES = 16 * 1024 * 1024
_CONTACT_TEXT_MAX_CHARS = 8192
_CONTACT_PAGE_MAX_BYTES = 300_000
_CONTACT_PAGE_ENVELOPE_RESERVE = 8_192


def _contact_offset(payload: Mapping[str, Any], *, default_limit: int = 100) -> tuple[int, int]:
    offset = 0
    cursor = payload.get("cursor")
    if cursor is not None:
        cursor_str = str(cursor).strip()
        if not cursor_str.startswith("offset:") or not cursor_str[7:].isdigit():
            raise WorkerIpcError("Invalid contact cursor.", code="provider_cursor_invalid")
        offset = int(cursor_str[7:])
    elif "offset" in payload:
        value = payload["offset"]
        if isinstance(value, bool):
            raise WorkerIpcError("Invalid contact offset.", code="provider_cursor_invalid")
        try:
            offset = int(value)
        except (ValueError, TypeError):
            raise WorkerIpcError("Invalid contact offset.", code="provider_cursor_invalid") from None
        if offset < 0:
            raise WorkerIpcError("Invalid contact offset.", code="provider_cursor_invalid")
    limit = payload.get("limit", default_limit)
    if isinstance(limit, bool):
        raise WorkerIpcError("Invalid contact limit.", code="provider_page_limit_invalid")
    try:
        limit = int(limit)
    except (ValueError, TypeError):
        raise WorkerIpcError("Invalid contact limit.", code="provider_page_limit_invalid") from None
    if not 1 <= limit <= 500:
        raise WorkerIpcError("Invalid contact limit.", code="provider_page_limit_invalid")
    return offset, limit


def _bounded_contact_page(items: list[dict[str, Any]], *, offset: int, limit: int) -> dict[str, Any]:
    if len(items) > _CONTACT_SNAPSHOT_MAX_ITEMS:
        raise WorkerIpcError(
            "The Bale contact snapshot exceeds the supported offline bound.",
            code="provider_contact_snapshot_too_large",
        )
    selected: list[dict[str, Any]] = []
    selected_bytes = 2  # JSON array brackets.
    for item in items[offset:offset + limit]:
        item_bytes = len(json.dumps(item, ensure_ascii=True, separators=(",", ":")).encode("utf-8"))
        candidate_bytes = selected_bytes + item_bytes + (1 if selected else 0)
        if candidate_bytes + _CONTACT_PAGE_ENVELOPE_RESERVE > _CONTACT_PAGE_MAX_BYTES:
            if not selected:
                raise WorkerIpcError(
                    "A Bale contact exceeds the supported IPC page size.",
                    code="provider_contact_record_too_large",
                )
            break
        selected.append(item)
        selected_bytes = candidate_bytes
    if not selected and offset < len(items):
        raise WorkerIpcError(
            "A Bale contact exceeds the supported IPC page size.",
            code="provider_contact_record_too_large",
        )
    next_offset = offset + len(selected)
    return {
        "contacts": selected,
        "total": len(items),
        "offset": offset,
        "limit": limit,
        "next_cursor": f"offset:{next_offset}" if next_offset < len(items) else None,
        "has_more": next_offset < len(items),
    }





def _uuid(value: object) -> str:

    try:

        parsed = UUID(str(value))

    except (TypeError, ValueError, AttributeError) as exc:

        raise WorkerIpcError("Invalid Bale worker identity.", code="bale_worker_identity_invalid") from exc

    if parsed.version != 4 or str(parsed) != value:

        raise WorkerIpcError("Invalid Bale worker identity.", code="bale_worker_identity_invalid")

    return str(parsed)





class BaleProviderProcessWorker:

    provider = "bale"



    def __init__(

        self, messenger_account_id: str, config_file: str | Path,

        *, owner_factory: Any = BaleAccountOwner,

    ) -> None:

        self.messenger_account_id = _uuid(messenger_account_id)

        self.base_directory = Path(config_file).resolve().parent

        self._owner_factory = owner_factory

        self.owner: BaleAccountOwner | None = None

        self.worker_instance_id: str | None = None

        self.worker_generation: int | None = None

        self.session_generation: int | None = None

        self._challenge: tuple[str, str, float, str] | None = None

        self._lease: Any = None

        self._authenticated = False

        self._session_invalid = False

        self._media: dict[str, tuple[float, dict[str, Any]]] = {}
        self._contact_snapshot: list[dict[str, Any]] | None = None
        self._contact_search_snapshot: tuple[str, list[dict[str, Any]]] | None = None

    def _invalidate_contact_snapshots(self) -> None:
        self._contact_snapshot = None
        self._contact_search_snapshot = None

    def _bounded_contact_snapshot(self, items: Any) -> list[dict[str, Any]]:
        if not isinstance(items, list) or len(items) > _CONTACT_SNAPSHOT_MAX_ITEMS:
            raise WorkerIpcError(
                "The Bale contact snapshot exceeds the supported offline bound.",
                code="provider_contact_snapshot_too_large",
            )
        normalized: list[dict[str, Any]] = []
        snapshot_bytes = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            peer = item.get("peer")
            safe_peer = None
            if isinstance(peer, dict):
                safe_peer = {
                    "id": peer.get("id") if isinstance(peer.get("id"), int) and not isinstance(peer.get("id"), bool) else None,
                    "type": peer.get("type") if isinstance(peer.get("type"), int) and not isinstance(peer.get("type"), bool) else None,
                }
            names: dict[str, str | None] = {}
            for field in ("name", "local_name"):
                value = item.get(field)
                if value is not None and not isinstance(value, str):
                    value = str(value)
                if isinstance(value, str) and len(value) > _CONTACT_TEXT_MAX_CHARS:
                    raise WorkerIpcError(
                        "A Bale contact exceeds the supported snapshot text bound.",
                        code="provider_contact_snapshot_too_large",
                    )
                names[field] = value
            selected = {"peer": safe_peer, **names}
            snapshot_bytes += len(json.dumps(selected, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
            if snapshot_bytes > _CONTACT_SNAPSHOT_MAX_BYTES:
                raise WorkerIpcError(
                    "The Bale contact snapshot exceeds the supported byte bound.",
                    code="provider_contact_snapshot_too_large",
                )
            normalized.append(selected)
        return normalized

    def _contact_list_snapshot(self, deadline_unix_ms: int, *, refresh: bool = False) -> list[dict[str, Any]]:
        if refresh:
            self._contact_snapshot = None
        if self._contact_snapshot is None:
            items = self._run(self._owner().list_contacts(), deadline_unix_ms)
            self._contact_snapshot = self._bounded_contact_snapshot(items)
        return self._contact_snapshot

    def _search_contacts_snapshot(self, query: str, deadline_unix_ms: int, *, refresh: bool = False) -> list[dict[str, Any]]:
        cached = self._contact_search_snapshot
        if refresh or cached is None or cached[0] != query:
            if refresh:
                self._contact_search_snapshot = None
            items = self._run(self._owner().search_contacts(query), deadline_unix_ms)
            self._contact_search_snapshot = (query, self._bounded_contact_snapshot(items))
        return self._contact_search_snapshot[1]



    def _require_fields(self, payload: Mapping[str, Any], fields: set[str], *, started: bool = True) -> None:

        expected = fields | ({"worker_instance_id", "worker_generation", "session_generation"} if started else set())

        if set(payload) != expected:

            raise WorkerIpcError("Invalid Bale worker payload.", code="ipc_payload_invalid")

        if started and (

            self.owner is None

            or payload["worker_instance_id"] != self.worker_instance_id

            or payload["worker_generation"] != self.worker_generation

            or payload["session_generation"] != self.session_generation

        ):

            raise WorkerIpcError("Bale worker generation changed.", code="bale_worker_fence_mismatch")



    def _owner(self) -> BaleAccountOwner:

        if self.owner is None:

            raise WorkerIpcError("Bale worker has not started.", code="bale_worker_not_started")

        return self.owner



    def _run(self, operation: Any, deadline_unix_ms: int) -> Any:

        remaining = (deadline_unix_ms - int(time.time() * 1000)) / 1000

        if remaining <= 0 or remaining > 120:

            operation.close()

            raise WorkerIpcError("Bale operation deadline invalid.", code="provider_operation_deadline_expired")

        try:

            return asyncio.run(asyncio.wait_for(operation, timeout=remaining))

        except TimeoutError:

            raise WorkerIpcError("Bale operation timed out.", code="bale_operation_timeout") from None

        except WorkerIpcError as exc:

            if exc.code == "bale_not_connected":
                self._authenticated = False
            raise

        except Exception as exc:

            selected = getattr(exc, "code", "bale_api_error")

            safe_code = selected if isinstance(selected, str) and selected.startswith("bale_") and selected.replace("_", "").isalnum() else "bale_api_error"

            if safe_code == "bale_not_connected":
                self._authenticated = False

            raise WorkerIpcError("Bale provider request failed.", code=safe_code) from None



    def _challenge_state(self, challenge_id: object, stage: str) -> str:

        challenge = self._challenge

        if challenge is not None and challenge[2] <= time.monotonic():

            self._challenge = None

            challenge = None

        if challenge is None or challenge[0] != challenge_id or challenge[1] != stage:

            raise WorkerIpcError("Bale challenge expired or changed.", code="bale_challenge_invalid")

        return challenge[3]



    @staticmethod

    def _text(value: object, *, maximum: int, code: str = "ipc_payload_invalid") -> str:

        if not isinstance(value, str) or not 1 <= len(value) <= maximum:

            raise WorkerIpcError("Invalid Bale worker text.", code=code)

        return value



    def dispatch(self, request: IpcEnvelope) -> ProviderWorkerDispatchResult:

        if request.provider != "bale" or request.messenger_account_id != self.messenger_account_id:

            raise WorkerIpcError("Bale worker account scope changed.", code="ipc_worker_scope_mismatch")

        method, payload = request.method, request.payload

        if method == "worker.hello":

            self._require_fields(payload, set(), started=False)

            return ProviderWorkerDispatchResult({

                "status": "bootstrap_ready" if self.owner is None else "ready",

                "worker_pid": os.getpid(), "protocol_version": IPC_PROTOCOL_VERSION,

                "provider": "bale", "messenger_account_id": self.messenger_account_id,

                "runtime_boundary": "child_process",

            })

        if method == "bale.runtime.start":

            self._require_fields(payload, {"runtime_record", "worker_instance_id", "worker_generation"}, started=False)

            if self.owner is not None:

                raise WorkerIpcError("Bale worker already started.", code="bale_worker_already_started")

            record = payload["runtime_record"]

            if not isinstance(record, Mapping) or (

                record.get("provider") != "bale"

                or record.get("messenger_account_id") != self.messenger_account_id

                or record.get("lifecycle_state") != "active"

                or record.get("desired_worker_state") != "running"

                or record.get("storage_revision") != 1

                or not isinstance(record.get("session_generation"), int)

                or record["session_generation"] < 0

            ):

                raise WorkerIpcError("Invalid Bale runtime record.", code="bale_worker_record_invalid")

            self.worker_instance_id = _uuid(payload["worker_instance_id"])

            generation = payload["worker_generation"]

            if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:

                raise WorkerIpcError("Invalid Bale worker generation.", code="bale_worker_identity_invalid")

            self.worker_generation = generation

            self.session_generation = record["session_generation"]

            from .account_runtime import AccountWorkerLease

            directory = self.base_directory / "runtime" / "providers" / "bale" / self.messenger_account_id

            directory.mkdir(parents=True, exist_ok=True)

            self._lease = AccountWorkerLease.acquire(

                directory / "worker.lock", self.messenger_account_id,

                session_generation=self.session_generation, storage_revision=1,

            )

            try:

                self.owner = self._owner_factory(self.base_directory, self.messenger_account_id)

            except Exception:

                self._lease.release()

                self._lease = None

                raise

            return ProviderWorkerDispatchResult({

                "status": "ready", "worker_pid": os.getpid(),

                "worker_instance_id": self.worker_instance_id,

                "worker_generation": generation,

                "core_owner_pid": os.getpid(), "core_opened": False,

                "core_open_deferred": True,

            })

        if method == "worker.stop":

            self._require_fields(payload, set())

            self.close()

            return ProviderWorkerDispatchResult({"status": "stopped"}, stop_requested=True)

        if method == "bale.runtime.generation":

            self._require_fields(payload, {"new_session_generation"})

            generation = payload["new_session_generation"]

            if isinstance(generation, bool) or not isinstance(generation, int) or generation < self.session_generation:

                raise WorkerIpcError("Invalid Bale session generation.", code="bale_worker_fence_mismatch")

            self.session_generation = generation

            self._challenge = None

            self._invalidate_contact_snapshots()

            self._lease.update_session_generation(generation)

            return ProviderWorkerDispatchResult({"session_generation": generation})

        if method in {"worker.health", "worker.heartbeat"}:

            self._require_fields(payload, set())

            return ProviderWorkerDispatchResult({

                "status": "ready", "worker_pid": os.getpid(),

                "worker_instance_id": self.worker_instance_id,

                "worker_generation": self.worker_generation,

            })

        if method == "bale.auth.start":

            self._require_fields(payload, {"phone"})

            phone = self._text(payload["phone"], maximum=16)

            if not phone.startswith("+") or not phone[1:].isdigit():

                raise WorkerIpcError("Invalid Bale phone identity.", code="bale_phone_invalid")

            result = self._run(self._owner().auth_start(phone), request.deadline_unix_ms)

            transaction_hash = self._text(result.get("transaction_hash"), maximum=4096)

            challenge_id = str(uuid4())

            self._challenge = (challenge_id, "code", time.monotonic() + 300, transaction_hash)

            self._session_invalid = False

            return ProviderWorkerDispatchResult({"step": "code", "challenge_id": challenge_id, "expires_in_seconds": 300})

        if method == "bale.auth.code":

            self._require_fields(payload, {"challenge_id", "code"})

            transaction_hash = self._challenge_state(payload["challenge_id"], "code")

            code = self._text(payload["code"], maximum=32)

            result = self._run(self._owner().auth_code(transaction_hash, code), request.deadline_unix_ms)

            if result.get("authenticated") is True:

                # OTP saves a vault session but does not open the provider WebSocket.
                # The first provider request must restore/connect on the owner loop.
                self._authenticated = False

                self._challenge = None

                return ProviderWorkerDispatchResult({"step": "completed"})

            if result.get("next") == "password":

                assert self._challenge is not None

                self._challenge = (self._challenge[0], "password", time.monotonic() + 300, transaction_hash)

                return ProviderWorkerDispatchResult({"step": "password", "challenge_id": payload["challenge_id"], "expires_in_seconds": 300})

            self._challenge = None

            raise WorkerIpcError("Bale login requires another flow.", code="bale_signup_required")

        if method == "bale.auth.password":

            self._require_fields(payload, {"challenge_id", "credential"})

            transaction_hash = self._challenge_state(payload["challenge_id"], "password")

            password = self._text(payload["credential"], maximum=1024)

            result = self._run(self._owner().auth_password(transaction_hash, password), request.deadline_unix_ms)

            if result.get("authenticated") is not True:

                raise WorkerIpcError("Bale second factor failed.", code="bale_auth_password_failed")

            self._challenge = None

            # A successful second factor saves the session without connecting.
            self._authenticated = False

            return ProviderWorkerDispatchResult({"step": "completed"})

        if method == "bale.auth.cancel":

            self._require_fields(payload, set())

            self._challenge = None

            return ProviderWorkerDispatchResult({"step": "cancelled"})

        if method == "bale.auth.restore":

            self._require_fields(payload, set())

            result = self._run(self._owner().connect(subscribe=False), request.deadline_unix_ms)

            self._authenticated = result.get("connected") is True

            return ProviderWorkerDispatchResult({"authenticated": result.get("connected") is True})

        if method == "bale.auth.status":

            self._require_fields(payload, set())

            has_vault = self._run(self._owner().has_vault(), request.deadline_unix_ms)

            if self._challenge is not None and self._challenge[2] <= time.monotonic():

                self._challenge = None

            return ProviderWorkerDispatchResult({"has_vault": has_vault, "session_invalid": self._session_invalid, "challenge_pending": self._challenge is not None,

                "challenge_id": self._challenge[0] if self._challenge else None,

                "step": self._challenge[1] if self._challenge else None})

        if method == "bale.auth.logout":

            self._require_fields(payload, set())

            self._challenge = None

            self._authenticated = False

            self._media.clear()

            archived = self._run(self._owner().logout(), request.deadline_unix_ms)

            return ProviderWorkerDispatchResult({"step": "logged_out", "session_archived": archived})

        if method.startswith("bale.provider.") and not self._authenticated:

            if self._session_invalid:

                raise WorkerIpcError("Fresh login required.", code="bale_session_invalid")

            if not self._run(self._owner().has_vault(), request.deadline_unix_ms):

                raise WorkerIpcError("Login is required.", code="bale_session_absent")

            try:

                restored = self._run(self._owner().connect(subscribe=False), request.deadline_unix_ms)

            except WorkerIpcError as exc:

                if str(getattr(exc, "code", "")) == "bale_vault_locked":

                    self._session_invalid = True

                    raise WorkerIpcError("Session restore failed.", code="bale_session_invalid") from None

                # Transport and timeout failures are not proof of session
                # invalidity; surface the real code and let the caller retry.

                raise

            except Exception:

                self._session_invalid = True

                raise WorkerIpcError("Session restore failed.", code="bale_session_invalid") from None

            self._authenticated = restored.get("connected") is True

            if not self._authenticated:

                self._session_invalid = True

                raise WorkerIpcError("Session restore failed.", code="bale_session_invalid")

        if method == "bale.provider.recipients.resolve":

            self._require_fields(payload, {"recipients"})

            recipients = payload["recipients"]

            if not isinstance(recipients, list) or not 1 <= len(recipients) <= 100:

                raise WorkerIpcError("Invalid recipient query.", code="ipc_payload_invalid")

            contacts = self._run(self._owner().list_contacts(), request.deadline_unix_ms)

            known = {f"bale:user:{item['peer']['id']}" for item in contacts if isinstance(item.get('peer'), dict) and item['peer'].get('type') == 1}

            results = []

            for recipient in recipients:

                kind, value = recipient.get("kind"), recipient.get("value")

                reference = None

                if kind == "dialog" and value in known:

                    reference = value

                elif kind == "phone" and isinstance(value, str) and value.startswith("+") and value[1:].isdigit():

                    peer_id = self._run(self._owner().lookup_phone(value), request.deadline_unix_ms)

                    reference = f"bale:user:{peer_id}" if peer_id is not None else None

                results.append({"status": "resolved" if reference else "unresolved", "peer_reference": reference,

                                "reason": None if reference else "recipient_not_found"})

            return ProviderWorkerDispatchResult({"results": results})

        if method == "bale.provider.media.read":

            self._require_fields(payload, {"user_id", "message_id", "max_bytes"})

            if any(isinstance(payload[k], bool) or not isinstance(payload[k], int) or payload[k] <= 0 for k in ("user_id", "message_id", "max_bytes")) or payload["max_bytes"] > 512 * 1024:

                raise WorkerIpcError("Invalid media query.", code="ipc_payload_invalid")

            result = self._run(self._owner().read_media_bytes(payload["user_id"], payload["message_id"], max_bytes=payload["max_bytes"]), request.deadline_unix_ms)

            if len(base64.b64decode(result["data_base64"], validate=True)) > payload["max_bytes"]:

                raise WorkerIpcError("Media size exceeded.", code="bale_media_too_large")

            token = uuid4().hex

            self._media = {k: v for k, v in self._media.items() if v[0] > time.monotonic()}

            if len(self._media) >= 16:

                self._media.pop(next(iter(self._media)))

            self._media[token] = (time.monotonic() + 300, result)

            return ProviderWorkerDispatchResult({"content_reference": f"bale:download:{token}",

                "byte_count": len(base64.b64decode(result["data_base64"])), "mime_type": result["mime_type"]})

        if method == "bale.provider.media.content":

            self._require_fields(payload, {"content_handle"})

            handle = self._text(payload["content_handle"], maximum=32)
            item = self._media.get(handle)

            if item is None or item[0] <= time.monotonic():

                raise WorkerIpcError("Media expired.", code="bale_media_not_found")

            return ProviderWorkerDispatchResult(item[1])

        if method == "bale.provider.messages.send_media":

            self._require_fields(payload, {"user_id", "filename", "data_base64", "caption"})

            user_id = payload["user_id"]

            if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:

                raise WorkerIpcError("Invalid media peer.", code="ipc_payload_invalid")

            try:

                data = base64.b64decode(payload["data_base64"], validate=True)

            except (ValueError, TypeError):

                raise WorkerIpcError("Invalid media bytes.", code="ipc_payload_invalid") from None

            from ..providers.contracts import ProviderPeerReference, ProviderSendMediaRequest

            checked = ProviderSendMediaRequest(ProviderPeerReference(f"bale:user:{user_id}", "private"),

                payload["filename"], data, "worker-validation-0001", payload["caption"])

            result = self._run(self._owner().send_file_bytes(user_id, checked.filename, checked.data, caption=checked.caption), request.deadline_unix_ms)

            return ProviderWorkerDispatchResult({"sent": result.get("sent") is True, "submission_reference": f"bale:submission:{uuid4().hex}"})

        if method == "bale.provider.contacts.query":
            offset, limit = _contact_offset(payload, default_limit=500)
            items = self._contact_list_snapshot(request.deadline_unix_ms, refresh=offset == 0)
            return ProviderWorkerDispatchResult(_bounded_contact_page(items, offset=offset, limit=limit))

        if method == "bale.provider.contacts.contains":
            self._require_fields(payload, {"peer_id"})
            try:
                peer_id = int(payload["peer_id"])
            except (ValueError, TypeError):
                raise WorkerIpcError("Invalid peer id.", code="ipc_payload_invalid")
            items = self._contact_list_snapshot(request.deadline_unix_ms, refresh=True)
            exists = any(
                isinstance(item, dict)
                and isinstance(item.get("peer"), dict)
                and int(item["peer"].get("id") or 0) == peer_id
                for item in items
            )
            return ProviderWorkerDispatchResult({"exists": exists})

        if method == "bale.provider.contacts.search":
            optional_page_fields = set(payload) & {"cursor", "limit"}
            self._require_fields(payload, {"query", *optional_page_fields})
            query = self._text(payload["query"], maximum=128)
            offset, limit = _contact_offset(payload)
            items = self._search_contacts_snapshot(query, request.deadline_unix_ms, refresh=offset == 0)
            return ProviderWorkerDispatchResult(_bounded_contact_page(items, offset=offset, limit=limit))

        if method == "bale.provider.contacts.add_phone":

            self._require_fields(payload, {"phone", "display_name"})

            phone = self._text(payload["phone"], maximum=16)

            name = self._text(payload["display_name"], maximum=512)

            if not phone.startswith("+") or not phone[1:].isdigit():

                raise WorkerIpcError("Invalid Bale phone identity.", code="bale_phone_invalid")

            result = self._run(self._owner().add_contact_by_phone(phone, name), request.deadline_unix_ms)

            self._invalidate_contact_snapshots()

            users = result.get("users")

            return ProviderWorkerDispatchResult({

                "matched": result.get("matched") is True,

                "created": result.get("created", True),

                "users": [

                    {"id": item.get("id") or (item.get("peer") or {}).get("id")}

                    for item in users[:10] if isinstance(item, dict)

                ] if isinstance(users, list) else [],

            })

        if method in {"bale.provider.contacts.add_id", "bale.provider.contacts.remove"}:

            self._require_fields(payload, {"user_id"})

            user_id = payload["user_id"]

            if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:

                raise WorkerIpcError("Invalid Bale contact peer.", code="ipc_payload_invalid")

            if method.endswith("add_id"):

                result = self._run(self._owner().add_contact(user_id), request.deadline_unix_ms)

                self._invalidate_contact_snapshots()

                return ProviderWorkerDispatchResult({"added": result.get("added") is True})

            result = self._run(self._owner().remove_contact(user_id), request.deadline_unix_ms)

            self._invalidate_contact_snapshots()

            return ProviderWorkerDispatchResult({"removed": result.get("removed") is True})

        if method == "bale.provider.dialogs.query":

            self._require_fields(payload, {"limit", "offset_date"})

            limit = payload["limit"]

            if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:

                raise WorkerIpcError("Invalid Bale page limit.", code="ipc_payload_invalid")

            offset = payload["offset_date"]

            if offset is not None and (isinstance(offset, bool) or not isinstance(offset, int) or offset <= 0):

                raise WorkerIpcError("Invalid Bale cursor.", code="provider_cursor_invalid")

            kwargs = {"limit": limit, **({"offset_date": offset} if offset is not None else {})}

            items = self._run(self._owner().list_dialogs(**kwargs), request.deadline_unix_ms)

            return ProviderWorkerDispatchResult({"dialogs": [

                {key: item.get(key) for key in ("peer", "title", "name", "unread_count", "last_text", "sort_date")}

                for item in items[:limit] if isinstance(item, dict)

            ]})

        if method == "bale.provider.history.query":

            self._require_fields(payload, {"user_id", "limit", "offset_date"})

            user_id, limit = payload["user_id"], payload["limit"]

            if any(isinstance(item, bool) or not isinstance(item, int) for item in (user_id, limit)) or not 0 < user_id or not 1 <= limit <= 500:

                raise WorkerIpcError("Invalid Bale history query.", code="ipc_payload_invalid")

            offset = payload["offset_date"]

            if offset is not None and (isinstance(offset, bool) or not isinstance(offset, int) or offset <= 0):

                raise WorkerIpcError("Invalid Bale cursor.", code="provider_cursor_invalid")

            kwargs = {"limit": limit, **({"offset_date": offset} if offset is not None else {})}

            items = self._run(self._owner().read_history(user_id, **kwargs), request.deadline_unix_ms)

            return ProviderWorkerDispatchResult({"messages": [

                {key: item.get(key) for key in ("message_id", "sender_id", "date", "text", "media")}

                for item in items[:limit] if isinstance(item, dict)

            ]})

        if method == "bale.provider.messages.send_text":

            self._require_fields(payload, {"user_id", "text"})

            user_id = payload["user_id"]

            if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:

                raise WorkerIpcError("Invalid Bale peer.", code="ipc_payload_invalid")

            text = self._text(payload["text"], maximum=100_000)

            result = self._run(self._owner().send_text(user_id, text), request.deadline_unix_ms)

            return ProviderWorkerDispatchResult({"sent": result.get("sent") is True, "random_id": result.get("random_id")})

        raise WorkerIpcError("Unsupported Bale worker method.", code="ipc_method_not_supported")



    def close(self) -> None:

        self._challenge = None

        owner, self.owner = self.owner, None

        try:

            if owner is not None:

                asyncio.run(owner.close())

        finally:

            if self._lease is not None:

                self._lease.release()

                self._lease = None
