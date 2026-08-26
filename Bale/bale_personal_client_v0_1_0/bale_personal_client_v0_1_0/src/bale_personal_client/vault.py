from __future__ import annotations

import json
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .models import BaleSession


MAGIC = b"BPCV1\x00"


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=32, n=2**15, r=8, p=1)
    return kdf.derive(passphrase.encode("utf-8"))


class SessionVault:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def exists(self) -> bool:
        return self.path.exists()

    def save(self, session: BaleSession, passphrase: str) -> None:
        if not passphrase:
            raise ValueError("Vault passphrase cannot be empty")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        salt = os.urandom(16)
        nonce = os.urandom(12)
        key = _derive_key(passphrase, salt)
        plaintext = json.dumps(session.to_dict(), ensure_ascii=False).encode("utf-8")
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, MAGIC)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_bytes(MAGIC + salt + nonce + ciphertext)
        os.replace(temp, self.path)

    def load(self, passphrase: str) -> BaleSession:
        raw = self.path.read_bytes()
        if not raw.startswith(MAGIC) or len(raw) < len(MAGIC) + 16 + 12 + 16:
            raise ValueError("Invalid Bale session vault")
        offset = len(MAGIC)
        salt = raw[offset : offset + 16]
        nonce = raw[offset + 16 : offset + 28]
        ciphertext = raw[offset + 28 :]
        key = _derive_key(passphrase, salt)
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, MAGIC)
        return BaleSession.from_dict(json.loads(plaintext.decode("utf-8")))

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
