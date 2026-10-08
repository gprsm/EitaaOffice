"""Default-off, owner-confirmed pilot through the main product API only.

Never run --allow-live without the owner's same-moment approval. Inputs stay
in memory; output contains only fixed step names and bounded safe error codes.
This script neither logs in automatically nor generates or validates OTPs.
"""
from __future__ import annotations

import argparse
import base64
from getpass import getpass
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from uuid import UUID, uuid4

PLAN = """Bale main-product pilot: OFF (no network, no credentials requested).
Required: target revision, owner-approved account and private test recipient,
existing app session/CSRF and Bale vault, operation limits and same-step approval.
Steps: status; warm restore; contacts/list/search; private history/receive;
named contact import; add-by-ID; one text send/read-back; bounded media;
remove only a contact created for this pilot. Unknown effects are never retried.
Run each approved action separately with --allow-live --origin http://127.0.0.1:PORT
--action ACTION. Private inputs are prompted locally and never saved or printed.
"""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def origin(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port or parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("A loopback main-product origin with an explicit port is required.")
    return value.rstrip("/")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--origin", default="")
    parser.add_argument("--action", choices=["status", "restore", "contacts", "search", "history", "receive", "import", "add-id", "send", "media", "remove"], default="status")
    args = parser.parse_args(argv)
    if not args.allow_live:
        print(PLAN)
        return 0
    try:
        endpoint = origin(args.origin)
    except ValueError:
        print("pilot_origin_invalid")
        return 2
    account = getpass("Approved account UUID (private): ")
    try:
        parsed = UUID(account)
        if parsed.version != 4 or str(parsed) != account:
            raise ValueError
    except ValueError:
        print("pilot_account_invalid")
        return 2
    cookie = getpass("Existing main-app session cookie (name=value; private): ")
    csrf = getpass("Existing main-app CSRF token (private): ")
    if not cookie or not csrf or any(char in cookie + csrf for char in "\r\n"):
        print("pilot_session_input_invalid")
        return 2
    api = endpoint + f"/api/v2/messenger-accounts/{account}/"
    opener = build_opener(NoRedirect())

    def call(path, payload=None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(api + path, data=data, headers={"Content-Type": "application/json", "Cookie": cookie, "X-CSRF-Token": csrf})
        try:
            with opener.open(request, timeout=95) as response:
                content = response.read(2 * 1024 * 1024 + 1)
                if len(content) > 2 * 1024 * 1024:
                    raise ValueError
                return json.loads(content)
        except HTTPError as error:
            # Never print the HTTP exception, URL, payload, or provider message.
            code = "pilot_http_error"
            try:
                body = json.loads(error.read(65536))
                candidate = body.get("error", {}).get("error_code", "")
                if re.fullmatch(r"[a-z][a-z0-9_]{0,80}", candidate):
                    code = candidate
            except (ValueError, AttributeError, TypeError):
                pass
            raise RuntimeError(code) from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise RuntimeError("pilot_result_unknown_no_retry") from None

    def confirm(step):
        if getpass(f"Owner approval for {step}; type {step.upper()} (private): ") != step.upper():
            raise RuntimeError("pilot_step_not_approved")

    def private_peer():
        value = getpass("Approved private peer bale:user:ID (private): ")
        if not re.fullmatch(r"bale:user:[1-9][0-9]{0,18}", value):
            raise RuntimeError("pilot_peer_invalid")
        return value

    def history(peer):
        return call("history/query", {"peer_reference": peer, "peer_kind": "private", "limit": 100})

    try:
        status = call("auth/status")
        if status.get("provider") != "bale" or status.get("messenger_account_id") != account:
            raise RuntimeError("pilot_account_fence_failed")
        action = args.action
        if action == "status":
            print("pilot_status_checked")
        elif action == "restore":
            confirm("restore")
            result = call("auth/restore", {"confirm": True})
            print("pilot_restore_authenticated" if result.get("auth_state") == "authenticated" else "pilot_restore_requires_user")
        else:
            if status.get("auth_state") != "authenticated":
                raise RuntimeError("pilot_account_not_authenticated")
            if action == "contacts":
                call("contacts/query", {"limit": 100}); print("pilot_contacts_checked")
            elif action == "search":
                query = getpass("Approved contact search (private): ")
                call("contacts/search", {"query": query}); print("pilot_search_checked")
            elif action in {"history", "receive"}:
                peer = private_peer()
                before = history(peer)
                if action == "receive":
                    confirm("receive_after_owner_sent_test_reply")
                    after = history(peer)
                    old = {item["message_reference"] for item in before.get("messages", [])}
                    fresh = any(item["message_reference"] not in old for item in after.get("messages", []))
                    print("pilot_new_message_observed" if fresh else "pilot_new_message_not_observed")
                else:
                    print("pilot_history_checked")
            elif action in {"import", "add-id"}:
                identity = getpass("Approved pilot phone E.164 (private): ") if action == "import" else private_peer()
                name = getpass("Approved pilot contact name (private): ")
                confirm(action)
                result = call("contacts/upsert", {"identity": identity, "display_name": name, "idempotency_key": uuid4().hex, "confirm": True})
                reference = result.get("contact_reference")
                current = call("contacts/query", {"limit": 500})
                observed = reference and any(item.get("contact_reference") == reference for item in current.get("contacts", []))
                print("pilot_contact_matched_observed" if observed else "pilot_contact_match_not_observed")
            elif action == "remove":
                peer = private_peer()
                current = call("contacts/query", {"limit": 500})
                if not any(item.get("contact_reference") == peer for item in current.get("contacts", [])):
                    raise RuntimeError("pilot_remove_contact_not_observed")
                confirm("remove_only_contact_created_for_this_pilot")
                result = call("contacts/remove", {"contact_reference": peer, "idempotency_key": uuid4().hex, "confirm": True})
                after = call("contacts/query", {"limit": 500})
                absent = all(item.get("contact_reference") != peer for item in after.get("contacts", []))
                print("pilot_contact_remove_observed" if result.get("removed") is True and absent else "pilot_contact_remove_unverified")
            elif action == "send":
                peer = private_peer()
                text = getpass("Owner-approved test text (private): ")
                old = {item["message_reference"] for item in history(peer).get("messages", [])}
                confirm("send")
                result = call("messages/send-text", {"peer_reference": peer, "peer_kind": "private", "text": text, "idempotency_key": uuid4().hex, "confirm": True})
                if result.get("status") != "succeeded":
                    raise RuntimeError("pilot_send_uncertain_no_retry")
                observed = any(item.get("text") == text and item["message_reference"] not in old for item in history(peer).get("messages", []))
                print("pilot_send_readback_observed" if observed else "pilot_send_accepted_readback_not_observed")
            elif action == "media":
                peer = private_peer()
                message = getpass("Approved message reference (private): ")
                reference = getpass("Approved media reference (private): ")
                result = call("media/read", {"peer_reference": peer, "peer_kind": "private", "message_reference": message, "media_reference": reference, "variant": "full", "max_bytes": 512 * 1024})
                content = call("media/content", {"content_reference": result["content_reference"]})
                if len(base64.b64decode(content["data_base64"], validate=True)) > 512 * 1024:
                    raise RuntimeError("pilot_media_limit_exceeded")
                print("pilot_media_checked")
        return 0
    except (RuntimeError, KeyError, ValueError, TypeError) as error:
        code = str(error) if isinstance(error, RuntimeError) and re.fullmatch(r"[a-z][a-z0-9_]{0,80}", str(error)) else "pilot_invalid_result"
        print(code)
        return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        print("pilot_cancelled_no_retry")
        raise SystemExit(130)
