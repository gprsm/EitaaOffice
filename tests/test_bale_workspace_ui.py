"""Behavioral source contracts for the Bale workspace UI.

These tests pin the observable behavior the Bale workspace must keep: honest
send receipts, account/peer isolation guards, provider-friendly polling
cadences, capability gating, and the absence of Eitaa-only operations in the
Bale surface. They complement the browser fixture acceptance (bale_ui_preview)
and the Eitaa contract runners, which guard the shared components from
regression.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "ui" / "src"
BALE = UI / "bale"


def read(name: str) -> str:
    return (UI / name).read_text(encoding="utf-8")


def read_bale(name: str) -> str:
    return (BALE / name).read_text(encoding="utf-8")


def bale_surface() -> str:
    return "\n".join([
        read("BaleWorkspace.tsx"),
        read_bale("BaleConversationList.tsx"),
        read_bale("BaleChatHeader.tsx"),
        read_bale("BaleMessageCard.tsx"),
        read_bale("BaleComposer.tsx"),
        read_bale("BaleContactDirectory.tsx"),
    ])


def test_bale_workspace_is_mounted_per_account_with_isolated_state() -> None:
    app = read("App.tsx")
    workspace = read("BaleWorkspace.tsx")
    # Switching accounts remounts the whole Bale surface; no shared dialog state survives.
    assert "selected?.provider === 'bale' ? <BaleWorkspace key={selected.messenger_account_id} />" in app
    # Late responses must never leak into a different account or dialog.
    assert "if (!alive.current || selectedPeer.current !== reference) return" in workspace
    assert "payload.peer.peer_reference !== peer?.peer_reference" not in workspace
    assert "if (alive.current && selectedPeer.current === payload.peer.peer_reference)" in workspace
    composer = read_bale("BaleComposer.tsx")
    assert "if (payload.peer.peer_reference !== peer?.peer_reference) return" in composer
    assert "if (!alive.current) return" in composer


def test_bale_drafts_are_scoped_to_account_and_dialog() -> None:
    composer = read_bale("BaleComposer.tsx")
    assert "scopedStorageKey" in composer
    assert "eitaa-bridge.bale-composer.${peer.peer_reference}" in composer
    # Only the draft text is persisted; files, secrets and identities are not.
    assert "localStorage.setItem(draftKey, JSON.stringify({ text }))" in composer


def test_bale_polling_keeps_provider_friendly_cadences_and_hidden_tab_pause() -> None:
    workspace = read("BaleWorkspace.tsx")
    # Open chat history about every 5 seconds; dialogs about every 15 seconds
    # with an independent failure backoff (V-262 contract).
    assert "timer = setTimeout(() => void poll(), 5000)" in workspace
    assert "dialogPoll.current.nextAt = Date.now() + 15000" in workspace
    assert "Math.min(60000, 15000 * 2 ** dialogPoll.current.failures)" in workspace
    # A hidden tab never issues requests while the live-updates capability holds.
    assert "document.visibilityState === 'hidden' && accounts.hasCapability('updates.live')" in workspace
    # A dialogs failure never blocks history: the two reads fail independently.
    assert workspace.index("const result = await api<{ dialogs: BaleDialogItem[] }>(") < workspace.index("if ((peer?.peer_kind === 'private' || peer?.peer_kind === 'group' || peer?.peer_kind === 'channel') && accounts.hasCapability('history.read'))")
    # Poll errors clear on success and re-check the auth status while failing.
    assert "setPollError(dialogPoll.current.error || historyError)" in workspace


def test_bale_send_is_confirmed_idempotent_and_honest() -> None:
    workspace = read("BaleWorkspace.tsx")
    composer = read_bale("BaleComposer.tsx")
    directory = read_bale("BaleContactDirectory.tsx")
    assert "idempotency_key: payload.idempotency_key" in workspace
    assert "confirm: true" in workspace
    # The composer always asks for explicit confirmation with the target shown.
    assert "تأیید ارسال" in composer
    assert "confirming?.peer.title" in composer
    # Honest receipts: delivery to the Bale service is claimed; recipient
    # visibility is not, and uncertain results never auto-retry.
    assert "پیام به سرویس بله ارسال شد؛ مشاهدهٔ گیرنده تأیید نشده است." in composer
    assert "نتیجهٔ ارسال نامعلوم است؛ ارسال خودکار تکرار نمی‌شود." in composer
    assert 'return status === \'succeeded\' ? \'succeeded\' : \'uncertain\'' in workspace
    # Two synchronous clicks inside one React batch must not double-send or
    # double-run: the re-entry guards are synchronous refs, not state.
    assert "sendingRef.current" in composer
    assert "busyRef.current" in workspace
    assert "busyRef.current" in directory


def test_bale_media_stays_bounded_without_raw_file_paths() -> None:
    workspace = read("BaleWorkspace.tsx")
    composer = read_bale("BaleComposer.tsx")
    assert "max_bytes: 512 * 1024" in workspace
    assert "512 * 1024" in composer
    assert "upload_path" not in workspace + composer
    assert "eitaaDesktop" not in workspace + composer


def test_bale_surface_gates_every_operation_on_account_capabilities() -> None:
    workspace = read("BaleWorkspace.tsx")
    composer = read_bale("BaleComposer.tsx")
    directory = read_bale("BaleContactDirectory.tsx")
    surface = bale_surface()
    for capability in ("auth.phone", "dialogs.read", "history.read", "messages.send", "media.read", "media.send", "contacts.read", "contacts.write", "updates.live"):
        assert f"hasCapability('{capability}')" in surface or f"can('{capability}')" in surface, capability
    assert "can={capability => accounts.hasCapability(capability)}" in workspace
    assert "canSendText={accounts.hasCapability('messages.send')}" in workspace
    assert "canSendMedia={accounts.hasCapability('media.send')}" in workspace
    assert "can('contacts.write')" in directory


def test_bale_group_and_channel_support_reading_and_sending() -> None:
    workspace = read("BaleWorkspace.tsx")
    composer = read_bale("BaleComposer.tsx")
    # Group and channel history poll like private chats.
    assert "peer?.peer_kind === 'private' || peer?.peer_kind === 'group' || peer?.peer_kind === 'channel'" in workspace
    # Groups and channels compose like private chats; any other kind keeps
    # the generic unsupported alert.
    assert "kind === 'private' || kind === 'group' || kind === 'channel'" in workspace
    assert "این نوع گفتگو پشتیبانی نمی‌شود." in workspace
    assert "ارسال در کانال پشتیبانی نمی‌شود" not in workspace
    assert "کانال — فقط‌خواندنی" not in workspace
    assert "خواندن و ارسال در گروه/کانال فعلاً پشتیبانی نمی‌شود" not in workspace
    # Outgoing bubbles require a private peer (the contract exposes no self
    # reference for groups); group senders show their typed id label.
    assert "peer?.peer_kind === 'private'" in workspace
    assert "authorFor" in workspace
    assert "author?: string" in read_bale("BaleMessageCard.tsx")


def test_bale_contact_directory_is_paged_searchable_and_recoverable() -> None:
    directory = read_bale("BaleContactDirectory.tsx")
    assert "contacts/${selectedQuery ? 'search' : 'query'}" in directory
    assert "next_cursor" in directory
    assert "نتایج بیشتر" in directory
    assert "موارد بیشتر" in directory
    # Deduplicated pagination, an empty state and a dismissible recoverable error.
    assert "filter(item => !existing.has(item.contact_reference))" in directory
    assert "مخاطبی در دفترچهٔ این حساب نیست." in directory
    assert "onClose={() => setError('')}" in directory
    # Removing and adding contacts stay confirm-gated and capability-gated.
    assert "حذف" in directory and "تأیید عملیات" in directory


def test_bale_navigation_shares_workspace_chrome_without_eitaa_operations() -> None:
    workspace = read("BaleWorkspace.tsx")
    navigation = read("WorkspaceNavigation.tsx")
    assert "<WorkspaceNavigation" in workspace
    assert 'messengerLogoutLabel="خروج از حساب بله"' in workspace
    assert "wordpressVisible={false}" in workspace
    # Eitaa-only actions are never passed to the shared navigation for Bale.
    for absent in ("onAddDialog=", "onBulk=", "onCommunity=", "onWordpress="):
        assert absent not in workspace.split("<WorkspaceNavigation", 1)[1].split("/>", 1)[0]
    # Optional action props keep the Eitaa call sites unchanged.
    assert "onAddDialog?: () => void" in navigation
    assert "messengerLogoutLabel = 'خروج از حساب ایتا'" in navigation


def test_bale_surface_never_calls_eitaa_only_routes() -> None:
    surface = bale_surface()
    assert "/api/v1/" not in surface
    assert surface.count("/api/v2/messenger-accounts/") >= 1 or "${base}" in surface
    # Typed peer references only; raw numeric ids or phone numbers are never sent.
    assert "peer_reference: payload.peer.peer_reference" in read("BaleWorkspace.tsx")
    assert "peer_reference: contact.contact_reference" in read("BaleWorkspace.tsx")


def test_bale_history_marks_end_and_cap_honestly() -> None:
    workspace = read("BaleWorkspace.tsx")
    assert "ابتدای گفتگو نمایش داده شد" in workspace
    assert "حد نمایش این گفتگو ۵۰۰ پیام است." in workspace


def test_bale_messages_dedupe_and_stay_sorted_by_reference() -> None:
    workspace = read("BaleWorkspace.tsx")
    assert "new Map([...previous, ...incoming].map(item => [item.message_reference, item])).values()" in workspace
    assert ".sort((a, b) => a.sent_at_unix_ms - b.sent_at_unix_ms || a.message_reference.localeCompare(b.message_reference)).slice(-500)" in workspace


def test_bale_settings_show_worker_state_and_capability_reasons() -> None:
    workspace = read("BaleWorkspace.tsx")
    assert "Worker:" in workspace
    assert "capabilitySnapshot.capabilities.map" in workspace
    assert "item.reason_code" in workspace
    assert "قابلیت‌های مجاز این حساب" in workspace


def test_bale_auth_surface_covers_code_password_cancel_restore_and_errors() -> None:
    workspace = read("BaleWorkspace.tsx")
    for needle in (
        "authenticate('start', { confirm: true })",
        "? 'password' : 'code'",
        "authenticate('cancel')",
        "authenticate('restore', { confirm: true })",
        "authenticate('logout', { confirm: true })",
        "`${base}/auth/${action}`",
        "رمز دومرحله‌ای",
        "کد ورود",
        "بازیابی نشست ذخیره‌شده",
        "لغو ورود",
        "خروج از نشست بله همین حساب؟",
        "تلاش دوباره",
    ):
        assert needle in workspace, needle
    # The login surface names the selected Bale account explicitly.
    assert "وضعیت نشست:" in workspace
    assert "account.phone_hint" in workspace


def test_bale_uses_shared_shell_and_mobile_list_pattern_without_class_names() -> None:
    workspace = read("BaleWorkspace.tsx")
    listing = read_bale("BaleConversationList.tsx")
    assert "calc(66px + env(safe-area-inset-bottom))" in workspace
    assert "72px minmax(280px, 32vw) minmax(0, 1fr)" in workspace
    assert "(max-width: 899px)" in workspace + listing
    assert "translateX(-110%)" in listing
    for name in ("BaleWorkspace.tsx", "BaleConversationList.tsx", "BaleChatHeader.tsx", "BaleMessageCard.tsx", "BaleComposer.tsx", "BaleContactDirectory.tsx"):
        source = read(name) if name == "BaleWorkspace.tsx" else read_bale(name)
        assert "className=" not in source, name
    assert 'aria-label="بازگشت به فهرست گفتگوها"' in read_bale("BaleChatHeader.tsx")


def test_bale_mobile_header_and_search_clear_the_fixed_menu_button() -> None:
    # F-106: the workspace menu button floats over the inline-start edge on
    # mobile; header and list content must reserve space so no control is
    # covered or unreachable.
    header = read_bale("BaleChatHeader.tsx")
    listing = read_bale("BaleConversationList.tsx")
    assert "paddingInlineStart: { xs: '60px', md: 0 }" in header
    assert "paddingInlineStart: { xs: '60px', md: 8 }" in listing
    # Polling failures stay visible while the mobile drawer covers the chat pane.
    assert "warning?: string" in listing
    assert "warning={pollError || undefined}" in read("BaleWorkspace.tsx")


def test_bale_privacy_secrets_never_enter_component_persistence() -> None:
    surface = bale_surface()
    # The only localStorage writes are the per-dialog draft texts.
    assert surface.count("localStorage.setItem") == 1
    assert "localStorage.setItem(draftKey, JSON.stringify({ text }))" in surface
    # OTP, tokens and phone numbers are never persisted by the workspace.
    assert "localStorage.setItem" not in read("BaleWorkspace.tsx")
