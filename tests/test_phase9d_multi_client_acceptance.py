from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json

from eitaa_bridge.infrastructure.coordinator import (
    CoordinatorAppAuth,
    CoordinatorDatabase,
    ProtectedPhone,
    StaticSubjectFingerprinter,
)


def _protected_phone(marker: bytes, fingerprint: str, hint: str) -> ProtectedPhone:
    return ProtectedPhone(
        ciphertext=marker,
        key_version=1,
        fingerprint=fingerprint,
        display_hint=hint,
    )


def test_two_users_three_clients_keep_accounts_and_sessions_isolated(tmp_path):
    database_path = tmp_path / "coordinator.sqlite3"
    database = CoordinatorDatabase(database_path)
    primary = database.bootstrap_legacy_account(
        protected_phone=_protected_phone(
            b"phase9d-primary-protected-phone",
            "1" * 64,
            "+** ** ** 41",
        ),
        display_name="Initial acceptance administrator",
        backup_name="primary-verified.zip",
        source_manifest_sha256="2" * 64,
        source_file_count=1,
        source_total_bytes=1,
    )
    auth = CoordinatorAppAuth(
        database_path,
        fingerprinter=StaticSubjectFingerprinter(b"phase9d-acceptance-secret"),
    )
    admin_desktop = auth.bootstrap_admin(
        username="acceptance.admin",
        password="correct horse battery staple",
        display_name="Acceptance administrator",
        client_kind="electron",
    )
    admin_actor = auth.authorize(admin_desktop.token).principal
    operator = auth.create_user(
        admin_actor,
        username="acceptance.operator",
        password="a distinct operator password",
        display_name="Acceptance operator",
        global_role="user",
    )

    secondary = database.bootstrap_legacy_account(
        protected_phone=_protected_phone(
            b"phase9d-secondary-protected-phone",
            "3" * 64,
            "+** ** ** 73",
        ),
        display_name="Secondary account owner",
        backup_name="secondary-verified.zip",
        source_manifest_sha256="4" * 64,
        source_file_count=1,
        source_total_bytes=1,
    )
    auth.update_phone_account_membership(
        admin_actor,
        phone_account_id=primary.phone_account_id,
        app_user_id=str(operator["app_user_id"]),
        role="operator",
        status="active",
    )

    admin_mobile = auth.authenticate(
        username="acceptance.admin",
        password="correct horse battery staple",
        client_kind="browser",
        client_address="192.0.2.41",
    )
    operator_mobile = auth.authenticate(
        username="acceptance.operator",
        password="a distinct operator password",
        client_kind="browser",
        client_address="192.0.2.73",
    )
    clients = (
        ("desktop-admin", admin_desktop.token, 2, 2),
        ("mobile-admin", admin_mobile.token, 2, 2),
        ("mobile-operator", operator_mobile.token, 1, 1),
    )

    def exercise(client):
        label, token, expected_accounts, expected_sessions = client
        observations = []
        for _ in range(30):
            authorized = auth.authorize(token)
            accounts = auth.list_messenger_accounts(authorized.principal)
            sessions = auth.list_own_sessions(authorized)
            assert len(accounts) == expected_accounts
            assert len(sessions) == expected_sessions
            observations.append(
                (
                    label,
                    tuple(sorted(str(item["messenger_account_id"]) for item in accounts)),
                    tuple(sorted(str(item["session_id"]) for item in sessions)),
                )
            )
        return observations

    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(exercise, clients))

    admin_accounts = set(results[0][0][1])
    assert admin_accounts == {
        primary.messenger_account_id,
        secondary.messenger_account_id,
    }
    assert set(results[1][0][1]) == admin_accounts
    assert set(results[2][0][1]) == {primary.messenger_account_id}
    assert set(results[0][0][2]) == set(results[1][0][2])
    assert set(results[0][0][2]).isdisjoint(set(results[2][0][2]))

    encoded = json.dumps(results)
    for secret in (
        admin_desktop.token,
        admin_mobile.token,
        operator_mobile.token,
        "phase9d-primary-protected-phone",
        "phase9d-secondary-protected-phone",
        "192.0.2.41",
        "192.0.2.73",
    ):
        assert secret not in encoded
