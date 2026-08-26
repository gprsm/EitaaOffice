from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import httpx

from .config import BaleConfig, SERVICES
from .errors import AuthenticationError, GrpcWebError, PasswordRequired, SignupRequired
from .grpc_web import GrpcWebClient
from .models import AuthStart, BaleSession, session_from_tokens
from .wire import ProtoWriter, get_first, parse_fields

# Python 3.10+ support for slots, fallback for older versions to prevent setup errors
if sys.version_info >= (3, 10):
    @dataclass(slots=True)
    class ValidateCodeOutcome:
        session: BaleSession | None
        password_required: bool = False
        signup_required: bool = False
        raw: bytes = b""
else:
    @dataclass
    class ValidateCodeOutcome:
        session: BaleSession | None
        password_required: bool = False
        signup_required: bool = False
        raw: bytes = b""


class AuthClient:
    """Bale phone authentication over gRPC-Web."""

    def __init__(
        self,
        config: BaleConfig,
        grpc: GrpcWebClient,
        http: httpx.AsyncClient,
    ) -> None:
        self.config = config
        self.grpc = grpc
        self.http = http

    async def start_phone_auth(
        self,
        phone_number: str | int,
        *,
        device_hash: bytes | None = None,
        client_label: str | None = None,
        language: str | None = None,
    ) -> AuthStart:
        phone = int(str(phone_number).replace("+", "").replace(" ", ""))
        payload = (
            ProtoWriter()
            .int64(1, phone)
            .int32(2, self.config.auth_app_id)
            .string(3, self.config.auth_api_key)
            .bytes(4, device_hash or os.urandom(16))
            .string(5, client_label or self.config.client_label)
            .string(7, language or self.config.language)
            .int32(9, self.config.send_code_type)
            .build()
        )
        response = await self.grpc.call(SERVICES["auth"], "StartPhoneAuth", payload)
        fields = parse_fields(response.payload)
        tx = get_first(fields, 1, b"")
        if isinstance(tx, bytes):
            transaction_hash = tx.decode("utf-8", errors="replace")
        else:
            transaction_hash = str(tx or "")
        registered_raw = get_first(fields, 2, 1)
        is_registered = bool(registered_raw)
        if not transaction_hash:
            raise AuthenticationError("StartPhoneAuth response did not contain a transaction hash")
        return AuthStart(transaction_hash=transaction_hash, is_registered=is_registered)

    async def validate_code(
        self,
        transaction_hash: str,
        code: str | int,
        *,
        is_registered_hint: bool = True,
    ) -> ValidateCodeOutcome:
        payload = (
            ProtoWriter()
            .string(1, transaction_hash)
            .string(2, str(code))
            .message(3, ProtoWriter().bool(1, True))
            .build()
        )
        try:
            response = await self.grpc.call(SERVICES["auth"], "ValidateCode", payload)
        except GrpcWebError as exc:
            upper = exc.message.upper()
            if "PASSWORD" in upper or "TWO_STEP" in upper:
                return ValidateCodeOutcome(session=None, password_required=True)
            if "UNOCCUPIED" in upper or "SIGN_UP" in upper:
                return ValidateCodeOutcome(session=None, signup_required=True)
            raise

        jwt = self._extract_wrapped_string(response.payload, outer_fields=(4, 1))
        password_required = self._find_truthy_hint(response.payload, {5, 6, 7})
        if password_required and not jwt:
            return ValidateCodeOutcome(
                session=None,
                password_required=True,
                raw=response.payload,
            )
        if not jwt:
            return ValidateCodeOutcome(
                session=None,
                signup_required=not is_registered_hint,
                raw=response.payload,
            )
        access_token = await self.exchange_jwt(jwt)
        return ValidateCodeOutcome(
            session=session_from_tokens(access_token, jwt),
            raw=response.payload,
        )

    async def validate_password(self, transaction_hash: str, password: str) -> BaleSession:
        payload = (
            ProtoWriter()
            .string(1, transaction_hash)
            .string(2, password)
            .build()
        )
        response = await self.grpc.call(SERVICES["auth"], "ValidatePassword", payload)
        
        # Checking multiple potential fields gracefully
        jwt = self._extract_wrapped_string(response.payload, outer_fields=(4, 1))
        if not jwt:
            raise PasswordRequired("ValidatePassword succeeded but no JWT was found")
        return session_from_tokens(await self.exchange_jwt(jwt), jwt)

    async def signup(
        self,
        transaction_hash: str,
        first_name: str,
        last_name: str = "",
    ) -> BaleSession:
        payload = (
            ProtoWriter()
            .string(1, transaction_hash)
            .string(2, first_name)
            .string(3, last_name)
            .build()
        )
        response = await self.grpc.call(SERVICES["auth"], "SignUp", payload)
        jwt = self._extract_wrapped_string(response.payload, outer_fields=(4, 1))
        if not jwt:
            raise SignupRequired("SignUp succeeded but no JWT was found")
        return session_from_tokens(await self.exchange_jwt(jwt), jwt)

    async def exchange_jwt(self, jwt: str) -> str:
        url = f"{self.config.grpc_base_url.rstrip('/')}/set-cookie/"
        response = await self.http.get(
            url,
            headers={
                "Authorization": f"Bearer {jwt}",
                "Origin": self.config.origin,
                "User-Agent": self.config.user_agent,
            },
        )
        response.raise_for_status()
        token = response.cookies.get("access_token") or self.http.cookies.get("access_token")
        
        if not token:
            # Fallback for different versions of httpx
            if hasattr(response.headers, "get_list"):
                cookie_headers = response.headers.get_list("set-cookie")
            else:
                cookie_headers = response.headers.get_all("set-cookie")
                
            for cookie in cookie_headers:
                first = cookie.split(";", 1)[0]
                if first.startswith("access_token="):
                    token = first.split("=", 1)[1]
                    break
                    
        if not token:
            raise AuthenticationError("/set-cookie/ did not issue an access_token cookie")
        return token

    @staticmethod
    def _extract_wrapped_string(data: bytes, *, outer_fields: tuple[int, ...] = (4, 1)) -> str | None:
        """Dynamically scans predefined fields to extract the JWT."""
        try:
            fields = parse_fields(data)
            for outer_field in outer_fields:
                outer = get_first(fields, outer_field)
                if isinstance(outer, bytes):
                    inner = get_first(parse_fields(outer), 1)
                    if isinstance(inner, bytes):
                        value = inner.decode("utf-8", errors="strict")
                        if value:
                            return value
        except Exception:
            pass
        return None

    @staticmethod
    def _find_truthy_hint(data: bytes, fields_to_check: set[int]) -> bool:
        try:
            for field in parse_fields(data):
                if field.number in fields_to_check and isinstance(field.value, int) and field.value:
                    return True
        except Exception:
            pass
        return False