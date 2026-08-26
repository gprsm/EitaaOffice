from __future__ import annotations

import urllib.parse
from dataclasses import dataclass

import httpx

from .config import BaleConfig
from .errors import GrpcWebError, ProtocolError


@dataclass(slots=True)
class GrpcWebResponse:
    payloads: list[bytes]
    trailers: dict[str, str]
    status_code: int

    @property
    def payload(self) -> bytes:
        return self.payloads[-1] if self.payloads else b""


def frame_grpc_web(payload: bytes) -> bytes:
    return b"\x00" + len(payload).to_bytes(4, "big") + payload


def parse_trailers(raw: bytes) -> dict[str, str]:
    text = raw.decode("utf-8", errors="replace")
    out: dict[str, str] = {}
    for line in text.replace("\r\n", "\n").split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            out[key.strip().lower()] = value.strip()
    return out


def unframe_grpc_web(data: bytes) -> tuple[list[bytes], dict[str, str]]:
    payloads: list[bytes] = []
    trailers: dict[str, str] = {}
    offset = 0
    while offset < len(data):
        if len(data) - offset < 5:
            raise ProtocolError("Truncated gRPC-Web frame header")
        flags = data[offset]
        length = int.from_bytes(data[offset + 1 : offset + 5], "big")
        offset += 5
        end = offset + length
        if end > len(data):
            raise ProtocolError("Truncated gRPC-Web frame body")
        body = data[offset:end]
        offset = end
        if flags & 0x80:
            trailers.update(parse_trailers(body))
        elif flags & 0x01:
            raise ProtocolError("Compressed gRPC-Web frame is not supported")
        else:
            payloads.append(body)
    return payloads, trailers


class GrpcWebClient:
    def __init__(self, config: BaleConfig, http: httpx.AsyncClient | None = None):
        self.config = config
        self.http = http or httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30.0),
            headers={"User-Agent": config.user_agent},
        )
        self._owns_http = http is None

    async def close(self) -> None:
        if self._owns_http:
            await self.http.aclose()

    async def call(
        self,
        service: str,
        method: str,
        payload: bytes = b"",
        *,
        access_token: str | None = None,
    ) -> GrpcWebResponse:
        url = f"{self.config.grpc_base_url.rstrip('/')}/{service}/{method}"
        headers = {
            "Content-Type": "application/grpc-web+proto",
            "X-Grpc-Web": "1",
            "Origin": self.config.origin,
            "Accept": "*/*",
        }
        if access_token:
            headers["Cookie"] = f"access_token={access_token}"
        response = await self.http.post(url, headers=headers, content=frame_grpc_web(payload))
        response.raise_for_status()
        payloads, trailers = unframe_grpc_web(response.content)
        status = int(trailers.get("grpc-status", response.headers.get("grpc-status", "0")) or 0)
        message = trailers.get("grpc-message", response.headers.get("grpc-message", ""))
        message = urllib.parse.unquote(message)
        if status != 0:
            raise GrpcWebError(status, message, trailers=trailers)
        return GrpcWebResponse(payloads=payloads, trailers=trailers, status_code=response.status_code)
