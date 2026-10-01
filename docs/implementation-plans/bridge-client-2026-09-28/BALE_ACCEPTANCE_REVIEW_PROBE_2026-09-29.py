"""Offline acceptance probe: real product path with existing synthetic fixtures.

Exit 0 means all checked repair criteria pass; exit 1 means semantic failures.
No production configuration, session, provider, or AI endpoint is opened.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import gc
import json
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from pytest import MonkeyPatch
from tests.conftest import config_file
from tests.test_bale_main_product import OfflineOwner, create_account, login, product
import eitaa_bridge.infrastructure.coordinator.rate_policy as rate_policy


def main() -> int:
    results = []
    with TemporaryDirectory(prefix="bale-acceptance-review-") as directory:
        patch = MonkeyPatch()
        fixture = product.__wrapped__(config_file.__wrapped__(Path(directory)), patch)
        app, request = next(fixture)
        try:
            account = create_account(request)
            base = login(request, account)
            now = [datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)]
            patch.setattr(rate_policy, "_utc", lambda value: value or now[0])
            policy = rate_policy.AccountExecutionPolicyService(
                app._coordinator, default_capacity=1, default_refill_per_second=1,
            )
            app._provider_orchestrator._execution_policy = policy

            def code(response):
                return response.payload.get("error", {}).get("error_code") or response.payload.get("code")

            body = {
                "peer_reference": "bale:user:42", "peer_kind": "private",
                "text": "Synthetic review text", "confirm": True,
                "idempotency_key": "review-accepted-key-0001",
            }
            accepted = request("POST", base + "/messages/send-text", body)
            denied_body = dict(body, idempotency_key="review-denied-key-0002")
            denied = request("POST", base + "/messages/send-text", denied_body)
            calls_at_denial = OfflineOwner.states[account]["calls"].count("send")
            now[0] += timedelta(seconds=10)
            retried = request("POST", base + "/messages/send-text", denied_body)
            now[0] += timedelta(seconds=10)
            fresh = request("POST", base + "/messages/send-text", dict(body, idempotency_key="review-fresh-key-0003"))
            connection = sqlite3.connect(app._coordinator.path)
            try:
                row = connection.execute(
                    "SELECT outcome FROM provider_operation_receipts WHERE idempotency_key=?",
                    ("review-denied-key-0002",),
                ).fetchone()
            finally:
                connection.close()
            results.append({
                "probe": "rate_denial_retry", "accepted_status": accepted.status,
                "denied_status": denied.status, "denied_code": code(denied),
                "denied_retry_after_present": "Retry-After" in denied.headers,
                "retry_after_refill_status": retried.status, "retry_code": code(retried),
                "fresh_key_status": fresh.status, "calls_at_denial": calls_at_denial,
                "calls_final": OfflineOwner.states[account]["calls"].count("send"),
                "memory_in_progress": len(app._provider_orchestrator._send_in_progress),
                "durable_outcome": row[0] if row else None,
                "passed": accepted.status == 201 and denied.status == 429
                and "Retry-After" in denied.headers and retried.status == 201
                and fresh.status == 201 and calls_at_denial == 1
                and OfflineOwner.states[account]["calls"].count("send") == 3
                and not app._provider_orchestrator._send_in_progress,
            })

            first = policy.acquire(messenger_account_id=account, operation_scope="contacts.upsert")
            second = policy.acquire(messenger_account_id=account, operation_scope="contacts.upsert")
            imported = request("POST", base + "/contacts/upsert", {
                "identity": "bale:user:444", "display_name": "Synthetic review contact",
                "idempotency_key": "review-contact-key-0001", "confirm": True,
            })
            mutated = 444 in OfflineOwner.states[account]["contacts"]
            results.append({
                "probe": "contact_budget", "bucket_exhausted": not second.allowed,
                "upsert_status": imported.status, "backend_mutated": mutated,
                "passed": first.allowed and not second.allowed and imported.status == 429 and not mutated,
            })

            OfflineOwner.states[account]["contacts"] = {i: "Synthetic contact" for i in range(1, 502)}
            visible, page_sizes, cursor = set(), [], None
            for _ in range(10):
                query = {"limit": 100}
                if cursor is not None:
                    query["cursor"] = cursor
                page = request("POST", base + "/contacts/query", query)
                if page.status != 200:
                    break
                page_sizes.append(len(page.payload["contacts"]))
                visible.update(item["contact_reference"] for item in page.payload["contacts"])
                cursor = page.payload.get("next_cursor")
                if cursor is None:
                    break
            results.append({
                "probe": "contact_pagination", "backend_total": 501,
                "visible_unique": len(visible), "page_sizes": page_sizes,
                "next_cursor": cursor, "passed": len(visible) == 501 and cursor is None,
            })

            # R1 already required immutable payload binding after admission
            # denial. Keep the original three checks and independently test
            # this condition instead of treating a deleted receipt as a fix.
            bound_body = dict(body, idempotency_key="review-binding-key-0004")
            binding_denied = request("POST", base + "/messages/send-text", bound_body)
            calls_before_change = OfflineOwner.states[account]["calls"].count("send")
            now[0] += timedelta(seconds=10)
            changed = request("POST", base + "/messages/send-text", dict(
                bound_body, text="Synthetic changed review text",
            ))
            calls_after_change = OfflineOwner.states[account]["calls"].count("send")
            results.append({
                "probe": "changed_payload_after_denial",
                "denial_status": binding_denied.status,
                "changed_payload_status": changed.status,
                "changed_payload_code": code(changed),
                "adapter_calls_before": calls_before_change,
                "adapter_calls_after": calls_after_change,
                "passed": binding_denied.status == 429 and changed.status == 409
                and calls_before_change == calls_after_change,
            })
        finally:
            # Resume the pytest fixture to execute its post-yield teardown;
            # generator.close() would skip that code and leave Windows locks.
            try:
                next(fixture)
            except StopIteration:
                pass
            patch.undo()
            gc.collect()
    for result in results:
        print(json.dumps(result, sort_keys=True))
    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
