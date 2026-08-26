from __future__ import annotations


class BaleError(Exception):
    """Base exception for the client."""


class ProtocolError(BaleError):
    pass


class GrpcWebError(BaleError):
    def __init__(self, status: int, message: str, *, trailers: dict[str, str] | None = None):
        super().__init__(f"gRPC-Web error {status}: {message}")
        self.status = status
        self.message = message
        self.trailers = trailers or {}


class RpcError(BaleError):
    def __init__(self, code: int, message: str, *, service: str = "", method: str = ""):
        prefix = f"{service}/{method}: " if service or method else ""
        super().__init__(f"{prefix}RPC error {code}: {message}")
        self.code = code
        self.message = message
        self.service = service
        self.method = method


class AuthenticationError(BaleError):
    pass


class PasswordRequired(AuthenticationError):
    pass


class SignupRequired(AuthenticationError):
    pass


class SessionExpired(AuthenticationError):
    pass


class VersionMismatch(ProtocolError):
    def __init__(self, proto: int, api: int, expected_proto: int, expected_api: int):
        super().__init__(
            f"Bale WebSocket version mismatch: server=({proto}, {api}), "
            f"client=({expected_proto}, {expected_api})"
        )
        self.proto = proto
        self.api = api
