"""M2M Service Credentials for automated integrations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from typing import Any
from uuid import uuid4

from .store import CoordinatorDatabase

_TOKEN_PREFIX = "eb_svc_"
_TOKEN_RANDOM_CHARS = 48
_SALT_BYTES = 16
_ITERATIONS = 600_000
_DIGEST_BYTES = 32

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

@dataclass(frozen=True, slots=True)
class ServiceCredential:
    id: str
    service_name: str
    allowed_providers: list[str]
    allowed_messenger_account_ids: list[str] | None
    scopes: list[str]
    created_at: str
    updated_at: str
    revoked_at: str | None
    created_by_app_user_id: str
    description: str


class ServiceCredentialService:
    def __init__(self, database: CoordinatorDatabase) -> None:
        self._db = database

    def _hash_token(self, token_secret: str, salt: bytes | None = None) -> tuple[str, bytes]:
        if salt is None:
            salt = os.urandom(_SALT_BYTES)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            token_secret.encode("utf-8"),
            salt,
            _ITERATIONS,
            dklen=_DIGEST_BYTES,
        )
        return digest.hex(), salt

    def create_credential(
        self,
        service_name: str,
        allowed_providers: list[str],
        allowed_messenger_account_ids: list[str] | None,
        scopes: list[str],
        description: str,
        created_by_app_user_id: str,
    ) -> tuple[ServiceCredential, str]:
        if not (3 <= len(service_name) <= 64):
            raise ValueError("service_name must be between 3 and 64 characters")
            
        token_secret = secrets.token_hex(_TOKEN_RANDOM_CHARS // 2)
        token_plaintext = f"{_TOKEN_PREFIX}{token_secret}"
        token_hash, salt = self._hash_token(token_plaintext)
        
        credential_id = str(uuid4())
        now = _now()
        
        providers_json = json.dumps(allowed_providers)
        accounts_json = json.dumps(allowed_messenger_account_ids) if allowed_messenger_account_ids is not None else None
        scopes_json = json.dumps(scopes)
        
        with self._db._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO service_credentials (
                    id, service_name, token_hash, salt, allowed_providers,
                    allowed_messenger_account_ids, scopes, created_at, updated_at,
                    revoked_at, created_by_app_user_id, description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    credential_id,
                    service_name,
                    token_hash,
                    salt,
                    providers_json,
                    accounts_json,
                    scopes_json,
                    now,
                    now,
                    None,
                    created_by_app_user_id,
                    description,
                ),
            )
            conn.commit()
            
        return (
            ServiceCredential(
                id=credential_id,
                service_name=service_name,
                allowed_providers=allowed_providers,
                allowed_messenger_account_ids=allowed_messenger_account_ids,
                scopes=scopes,
                created_at=now,
                updated_at=now,
                revoked_at=None,
                created_by_app_user_id=created_by_app_user_id,
                description=description,
            ),
            token_plaintext,
        )

    def verify_token(self, token_plaintext: str) -> ServiceCredential | None:
        if not token_plaintext.startswith(_TOKEN_PREFIX):
            return None
            
        with self._db._connect() as conn:
            cursor = conn.execute(
                """
                SELECT id, service_name, allowed_providers, allowed_messenger_account_ids,
                       scopes, created_at, updated_at, revoked_at, created_by_app_user_id,
                       description, token_hash, salt
                FROM service_credentials
                WHERE revoked_at IS NULL
                """
            )
            rows = cursor.fetchall()

        token_bytes = token_plaintext.encode("utf-8")
        matched_row = None
        
        # Verify against all active to prevent timing attacks based on the number of active credentials?
        # Actually, iterating through all of them is linear time, but since M2M credentials are few, it's acceptable.
        for row in rows:
            expected_hash = row["token_hash"]
            salt = row["salt"]
            
            actual_digest = hashlib.pbkdf2_hmac(
                "sha256",
                token_bytes,
                salt,
                _ITERATIONS,
                dklen=_DIGEST_BYTES,
            )
            
            if hmac.compare_digest(actual_digest.hex(), expected_hash):
                matched_row = row
                break
                
        if matched_row is None:
            return None
            
        return self._row_to_credential(matched_row)

    def _row_to_credential(self, row: sqlite3.Row) -> ServiceCredential:
        return ServiceCredential(
            id=row["id"],
            service_name=row["service_name"],
            allowed_providers=json.loads(row["allowed_providers"]),
            allowed_messenger_account_ids=json.loads(row["allowed_messenger_account_ids"]) if row["allowed_messenger_account_ids"] else None,
            scopes=json.loads(row["scopes"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            revoked_at=row["revoked_at"],
            created_by_app_user_id=row["created_by_app_user_id"],
            description=row["description"],
        )

    def revoke_credential(self, credential_id: str) -> None:
        with self._db._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE service_credentials SET revoked_at = ?, updated_at = ? WHERE id = ? AND revoked_at IS NULL",
                (_now(), _now(), credential_id)
            )
            conn.commit()

    def list_credentials(self) -> list[ServiceCredential]:
        with self._db._connect() as conn:
            cursor = conn.execute(
                """
                SELECT id, service_name, allowed_providers, allowed_messenger_account_ids,
                       scopes, created_at, updated_at, revoked_at, created_by_app_user_id, description
                FROM service_credentials
                ORDER BY created_at DESC
                """
            )
            return [self._row_to_credential(row) for row in cursor.fetchall()]

    def rotate_credential(self, credential_id: str) -> str:
        token_secret = secrets.token_hex(_TOKEN_RANDOM_CHARS // 2)
        token_plaintext = f"{_TOKEN_PREFIX}{token_secret}"
        token_hash, salt = self._hash_token(token_plaintext)

        with self._db._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute(
                """
                UPDATE service_credentials
                SET token_hash = ?, salt = ?, updated_at = ?
                WHERE id = ? AND revoked_at IS NULL
                """,
                (token_hash, salt, _now(), credential_id)
            )
            rotated = cursor.rowcount == 1
            conn.commit()

        if not rotated:
            raise LookupError("Service credential not found or already revoked.")
        return token_plaintext
