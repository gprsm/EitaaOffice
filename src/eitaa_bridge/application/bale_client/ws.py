from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from websockets.exceptions import ConnectionClosed
from websockets.legacy.client import connect as ws_connect

from .codecs import build_set_online, decode_update_union
from .config import BaleConfig, SERVICES
from .errors import ProtocolError, RpcError, SessionExpired, VersionMismatch
from .models import BaleSession, Update
from .wire import ProtoWriter, get_first, parse_fields

UpdateHandler = Callable[[Update], Awaitable[None] | None]


class BaleWebSocket:
    def __init__(
        self,
        config: BaleConfig,
        session: BaleSession,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self.config = config
        self.session = session
        self.log = logger or logging.getLogger("bale_personal_client.ws")
        self.socket: Any = None
        self._request_id = 0
        self._pending: dict[int, asyncio.Future[bytes]] = {}
        self._reader_task: asyncio.Task[None] | None = None
        self._ping_task: asyncio.Task[None] | None = None
        self._presence_task: asyncio.Task[None] | None = None
        self._handshake_event = asyncio.Event()
        self._closed_event = asyncio.Event()
        self._update_queue: asyncio.Queue[Update] = asyncio.Queue(maxsize=1000)
        self._handlers: list[UpdateHandler] = []
        self._subscription_ids: set[int] = set()
        self._resubscribe_task: asyncio.Task[None] | None = None
        self.last_error: BaseException | None = None
        self.server_proto_version: int | None = None
        self.server_api_version: int | None = None

    @property
    def connected(self) -> bool:
        return self.socket is not None and not getattr(self.socket, "closed", True)

    def add_update_handler(self, handler: UpdateHandler) -> None:
        self._handlers.append(handler)

    async def next_update(self, timeout: float | None = None) -> Update:
        if timeout is None:
            return await self._update_queue.get()
        return await asyncio.wait_for(self._update_queue.get(), timeout)

    async def connect(self, *, subscribe: bool = True, presence: bool = True) -> None:
        if self.connected:
            return
        self.last_error = None
        self._closed_event.clear()
        self._handshake_event.clear()
        headers = {
            "Cookie": f"access_token={self.session.access_token}",
            "User-Agent": self.config.user_agent,
        }
        self.log.info("Connecting WebSocket: %s", self.config.ws_url)
        self.socket = await ws_connect(
            self.config.ws_url,
            extra_headers=headers,
            origin=self.config.origin,
            open_timeout=self.config.handshake_timeout,
            close_timeout=5,
            ping_interval=None,
            compression=None,
            max_size=None,
        )
        self._reader_task = asyncio.create_task(self._reader_loop(), name="bale-ws-reader")
        await self.socket.send(self._handshake_frame())
        try:
            await asyncio.wait_for(self._handshake_event.wait(), self.config.handshake_timeout)
        except Exception:
            await self.disconnect()
            raise
        self._ping_task = asyncio.create_task(self._ping_loop(), name="bale-ws-ping")
        if presence:
            self._presence_task = asyncio.create_task(self._presence_loop(), name="bale-presence")
        if subscribe:
            await self.subscribe_to_updates()
        self.log.info(
            "WebSocket ready; server proto=%s api=%s",
            self.server_proto_version,
            self.server_api_version,
        )

    async def disconnect(self) -> None:
        tasks = [self._ping_task, self._presence_task, self._resubscribe_task]
        for task in tasks:
            if task:
                task.cancel()
        if self.socket is not None:
            with contextlib.suppress(Exception):
                await self.socket.close()
        if self._reader_task and self._reader_task is not asyncio.current_task():
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._reader_task
        self.socket = None
        for task in tasks:
            if task:
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
        self._reader_task = self._ping_task = self._presence_task = self._resubscribe_task = None
        for future in self._pending.values():
            if not future.done():
                future.set_exception(ProtocolError("WebSocket disconnected"))
        self._pending.clear()
        self._closed_event.set()

    async def wait_closed(self) -> None:
        await self._closed_event.wait()
        if self.last_error:
            raise self.last_error

    async def rpc(
        self,
        service: str,
        method: str,
        payload: bytes = b"",
        *,
        timeout: float | None = None,
    ) -> bytes:
        if not self.connected:
            raise ProtocolError("WebSocket is not connected")
        request_id = self._next_request_id()
        future: asyncio.Future[bytes] = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        await self.socket.send(self._rpc_frame(service, method, payload, request_id))
        self.log.debug("RPC -> #%s %s/%s (%s bytes)", request_id, service, method, len(payload))
        try:
            return await asyncio.wait_for(future, timeout or self.config.rpc_timeout)
        finally:
            self._pending.pop(request_id, None)

    async def send_stream_rpc(self, service: str, method: str, payload: bytes = b"") -> int:
        if not self.connected:
            raise ProtocolError("WebSocket is not connected")
        request_id = self._next_request_id()
        self._subscription_ids.add(request_id)
        await self.socket.send(self._rpc_frame(service, method, payload, request_id))
        self.log.debug("STREAM -> #%s %s/%s", request_id, service, method)
        return request_id

    async def subscribe_to_updates(self) -> int:
        return await self.send_stream_rpc(SERVICES["stream"], "SubscribeToUpdates", b"")

    async def set_online(self, online: bool = True) -> bytes:
        return await self.rpc(
            SERVICES["presence"],
            "SetOnline",
            build_set_online(online=online),
        )

    def _next_request_id(self) -> int:
        self._request_id += 1
        if self._request_id >= (1 << 31):
            self._request_id = 1
        return self._request_id

    def _handshake_frame(self) -> bytes:
        inner = (
            ProtoWriter()
            .int32(1, self.config.proto_version)
            .int32(2, self.config.api_version)
        )
        return ProtoWriter().message(3, inner).build()

    @staticmethod
    def _rpc_frame(service: str, method: str, payload: bytes, request_id: int) -> bytes:
        inner = (
            ProtoWriter()
            .string(1, service)
            .string(2, method)
            .bytes(3, payload)
            .int64(5, request_id)
        )
        return ProtoWriter().message(1, inner).build()

    @staticmethod
    def _ping_frame(request_id: int) -> bytes:
        return ProtoWriter().message(2, ProtoWriter().int64(1, request_id)).build()

    async def _reader_loop(self) -> None:
        try:
            async for message in self.socket:
                if isinstance(message, str):
                    self.log.warning("bale_ws_text_frame_ignored")
                    continue
                await self._handle_frame(bytes(message))
        except asyncio.CancelledError:
            raise
        except ConnectionClosed as exc:
            if exc.code == 4401:
                self.last_error = SessionExpired("Bale rejected or expired the access_token (close 4401)")
            else:
                self.last_error = ProtocolError("WebSocket closed")
            self.log.error("bale_ws_connection_closed")
        except BaseException as exc:
            self.last_error = exc
            self.log.error("bale_ws_reader_failed")
        finally:
            self._closed_event.set()
            for future in list(self._pending.values()):
                if not future.done():
                    future.set_exception(self.last_error or ProtocolError("WebSocket reader stopped"))

    async def _handle_frame(self, data: bytes) -> None:
        try:
            top = parse_fields(data)
        except Exception as exc:
            raise ProtocolError(f"Cannot parse incoming WebSocket frame: {exc}") from exc

        for field in top:
            if field.number == 5 and isinstance(field.value, bytes):
                self._handle_handshake(field.value)
            elif field.number == 4:
                self.log.debug("PONG <-")
            elif field.number == 3:
                self.log.warning("Server terminate frame: %s", field.value)
            elif field.number == 1 and isinstance(field.value, bytes):
                await self._handle_rpc_or_push(field.value)
            elif field.number == 2 and isinstance(field.value, bytes):
                await self._emit_update_container(field.value)
            else:
                self.log.debug("Unknown top-level WS field %s", field.number)

    def _handle_handshake(self, data: bytes) -> None:
        fields = parse_fields(data)
        proto = int(get_first(fields, 1, 0))
        api = int(get_first(fields, 2, 0))
        self.server_proto_version = proto
        self.server_api_version = api
        if proto != self.config.proto_version or api != self.config.api_version:
            error = VersionMismatch(proto, api, self.config.proto_version, self.config.api_version)
            self.last_error = error
            raise error
        self._handshake_event.set()

    async def _handle_rpc_or_push(self, data: bytes) -> None:
        fields = parse_fields(data)
        request_id = get_first(fields, 3)
        payload = get_first(fields, 2, b"")
        error_raw = get_first(fields, 1)

        if isinstance(request_id, int):
            error = self._decode_rpc_error(error_raw) if isinstance(error_raw, bytes) else None
            if request_id in self._subscription_ids:
                self._subscription_ids.discard(request_id)
                if error is None or self._is_expected_subscription_end(error):
                    self.log.debug("Update subscription #%s rotated", request_id)
                    self._schedule_resubscribe()
                else:
                    self.log.warning("bale_update_subscription_failed")
                    self._schedule_resubscribe(delay=2.0)
                return
            future = self._pending.get(request_id)
            if future is not None and not future.done():
                if error:
                    future.set_exception(error)
                else:
                    future.set_result(payload if isinstance(payload, bytes) else b"")
                return

        # Unmatched field-1 packets are treated as push containers. Server builds
        # have used more than one nesting shape, so decode both the payload and the
        # entire inner frame.
        if isinstance(payload, bytes) and payload:
            await self._emit_update_container(payload)
        else:
            await self._emit_update_container(data)

    @staticmethod
    def _decode_rpc_error(data: bytes) -> RpcError | None:
        try:
            fields = parse_fields(data)
        except Exception:
            return RpcError(-1, "Malformed RPC error")
        code = int(get_first(fields, 1, 0))
        raw_message = get_first(fields, 2, b"")
        message = raw_message.decode("utf-8", errors="replace") if isinstance(raw_message, bytes) else str(raw_message)
        if code == 0 and not message:
            return None
        return RpcError(code, message)

    @staticmethod
    def _is_expected_subscription_end(error: RpcError) -> bool:
        message = error.message.lower()
        return (
            error.code == 4
            or (error.code == 2 and "eof" in message)
            or (error.code == 13 and "cardinality" in message)
        )

    async def _emit_update_container(self, raw: bytes) -> None:
        try:
            updates = decode_update_union(raw)
        except Exception:
            updates = [Update(kind="raw", payload=raw, raw=raw)]
        for update in updates:
            if self._update_queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    self._update_queue.get_nowait()
            self._update_queue.put_nowait(update)
            for handler in list(self._handlers):
                try:
                    result = handler(update)
                    if asyncio.iscoroutine(result):
                        asyncio.create_task(result)
                except Exception:
                    self.log.error("bale_update_handler_failed")

    def _schedule_resubscribe(self, delay: float = 0.05) -> None:
        if not self.connected:
            return
        if self._resubscribe_task and not self._resubscribe_task.done():
            return

        async def runner() -> None:
            await asyncio.sleep(delay)
            if self.connected:
                await self.subscribe_to_updates()

        self._resubscribe_task = asyncio.create_task(runner(), name="bale-resubscribe")

    async def _ping_loop(self) -> None:
        try:
            while self.connected:
                await asyncio.sleep(self.config.ping_interval)
                if self.connected:
                    await self.socket.send(self._ping_frame(self._next_request_id()))
        except asyncio.CancelledError:
            raise
        except Exception:
            self.log.error("bale_ping_failed")

    async def _presence_loop(self) -> None:
        try:
            while self.connected:
                try:
                    await self.set_online(True)
                except Exception:
                    self.log.debug("bale_presence_failed")
                await asyncio.sleep(self.config.presence_interval)
        except asyncio.CancelledError:
            raise
