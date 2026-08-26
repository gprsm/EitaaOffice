from bale_personal_client.models import BaleSession
from bale_personal_client.vault import SessionVault


def test_encrypted_vault_roundtrip(tmp_path):
    path = tmp_path / "session.vault"
    vault = SessionVault(path)
    original = BaleSession(access_token="secret", jwt="jwt", user_id=123)
    vault.save(original, "correct horse battery staple")
    raw = path.read_bytes()
    assert b"secret" not in raw
    restored = vault.load("correct horse battery staple")
    assert restored.access_token == "secret"
    assert restored.user_id == 123
