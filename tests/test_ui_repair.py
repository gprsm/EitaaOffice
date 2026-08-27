from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_font_sync_module():
    path = ROOT / "scripts" / "sync_ui_fonts.py"
    spec = importlib.util.spec_from_file_location("sync_ui_fonts_under_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_visible_tabs_use_one_active_contract_and_no_fixed_header_offset():
    app = ((ROOT / "ui" / "src" / "App.tsx").read_text(encoding="utf-8") + (ROOT / "ui" / "src" / "utils" / "helpers.tsx").read_text(encoding="utf-8"))

    assert "tab-active" not in app
    assert 'name="composer_sections"' not in app
    assert 'name="manual_dialog_mode"' not in app
    assert '<ToggleButton value="wordpress"' in app
    assert '<ToggleButton value="community" disabled={!props.communityEnabled}>عملیات گفتگو</ToggleButton>' in app
    assert '<ToggleButton value="username">با نام کاربری</ToggleButton>' in app
    assert '<ToggleButton value="peer">شناسه فنی</ToggleButton>' in app
    assert "<ToggleButtonGroup exclusive fullWidth" in app
    assert "className=" not in app


def test_ui_labels_do_not_claim_xlsx_support_and_primitives_are_complete():
    app = ((ROOT / "ui" / "src" / "App.tsx").read_text(encoding="utf-8") + (ROOT / "ui" / "src" / "utils" / "helpers.tsx").read_text(encoding="utf-8"))

    assert "ورود Excel" not in app
    assert "انتخاب TXT/CSV" in app
    assert "ورود شماره‌ها / فایل" not in app
    assert "<TextField" in app
    assert "<Checkbox" in app
    assert "<Button" in app
    assert "className=" not in app


def test_optional_iransans_syncs_into_prebuilt_dist_and_records_status(tmp_path):
    module = _load_font_sync_module()
    (tmp_path / "ui" / "dist").mkdir(parents=True)
    (tmp_path / "ui" / "dist" / "index.html").write_text("ok", encoding="utf-8")
    (tmp_path / "ui" / "fonts").mkdir(parents=True)

    fallback = module.sync_ui_fonts(tmp_path)
    assert fallback["status"] == "fallback_active"
    assert fallback["ready"] is False

    regular = tmp_path / "ui" / "fonts" / "IRANSansWeb-Regular.woff2"
    bold = tmp_path / "ui" / "fonts" / "IRANSansWeb-Bold.woff2"
    regular.write_bytes(b"licensed-regular")
    bold.write_bytes(b"licensed-bold")

    ready = module.sync_ui_fonts(tmp_path)
    assert ready["status"] == "iransans_ready"
    assert ready["ready"] is True
    assert (tmp_path / "ui" / "dist" / "fonts" / regular.name).read_bytes() == b"licensed-regular"
    assert (tmp_path / "ui" / "dist" / "fonts" / bold.name).read_bytes() == b"licensed-bold"

    status = json.loads((tmp_path / "runtime" / "font-status.json").read_text(encoding="utf-8"))
    assert status["ready"] is True
    assert status["missing"] == []


def test_material_css_baseline_loads_both_iransans_weights_from_bundled_fonts():
    theme = (ROOT / "ui" / "src" / "theme.ts").read_text(encoding="utf-8")
    assert "'@font-face': [" in theme
    assert 'url("./fonts/IRANSansWeb-Regular.woff2") format("woff2")' in theme
    assert 'url("./fonts/IRANSansWeb-Bold.woff2") format("woff2")' in theme
    assert "fontFamily: 'IRANSans'" in theme
    assert "fontWeight: 400" in theme
    assert "fontWeight: 700" in theme
    assert "fontDisplay: 'swap'" in theme
    assert 'fontFamily: \'IRANSans, "Segoe UI", Tahoma, Arial, sans-serif\'' in theme


def test_installer_runs_font_sync_without_requiring_node_for_prebuilt_ui():
    installer = (ROOT / "install_app.bat").read_text(encoding="utf-8")
    assert "scripts\\sync_ui_fonts.py --quiet" in installer
    assert "Node.js, npm packages, and Electron are development-only" in installer


def test_wordpress_ui_keeps_category_tree_and_stays_quiet_without_credentials():
    app = ((ROOT / "ui" / "src" / "App.tsx").read_text(encoding="utf-8") + (ROOT / "ui" / "src" / "utils" / "helpers.tsx").read_text(encoding="utf-8"))
    types = (ROOT / "ui" / "src" / "lib" / "types.ts").read_text(encoding="utf-8")

    assert "parent_id?: number | null" in types
    assert "function categoryTree(" in app
    assert 'role="tree"' in app
    assert "aria-level={depth + 1}" in app
    assert "!activeSite?.credentials_configured" in app
    assert "wordpressReady" in app
    assert 'aria-label="وردپرس آماده نیست"' in app


def test_wordpress_panel_is_opt_in_and_community_operations_are_role_gated():
    app = (ROOT / "ui" / "src" / "App.tsx").read_text(encoding="utf-8")
    helpers = (ROOT / "ui" / "src" / "utils" / "helpers.tsx").read_text(encoding="utf-8")
    settings = (ROOT / "ui" / "src" / "SettingsPage.tsx").read_text(encoding="utf-8")
    types = (ROOT / "ui" / "src" / "lib" / "types.ts").read_text(encoding="utf-8")

    assert "showWordPressPanel" in helpers
    assert "readStored<boolean>(STORAGE.showWordPressPanel, false)" in app
    assert "wordpressPanelReady" in app
    assert "!showWordPressPanel || !activeSite?.credentials_configured" in app
    assert "canManageCommunity(dialog)" in app
    assert "نمایش پنل وردپرس" in settings
    assert "account_role?: 'owner' | 'admin' | 'member' | 'unknown'" in types
    assert "can_manage_community?: boolean" in types


def test_dialog_sync_and_avatar_ui_do_not_report_benign_or_fetch_remote_work():
    app = ((ROOT / "ui" / "src" / "App.tsx").read_text(encoding="utf-8") + (ROOT / "ui" / "src" / "utils" / "helpers.tsx").read_text(encoding="utf-8"))
    loader = (ROOT / "ui" / "src" / "lib" / "avatarLoader.ts").read_text(encoding="utf-8")

    assert "unusable_peer_missing_access_hash" in app
    assert "گفتگوی حذف‌شده یا غیرقابل استفاده کنار گذاشته شد" in app
    assert "IntersectionObserver" in app
    assert "loadDialogAvatar" in app
    assert "peekDialogAvatar" in app
    assert "cached_only: true" in loader
    assert "cached_only: false" in loader
    assert "avatarRequests" in loader
    assert "avatarCacheQueue" in loader
    assert "avatarRemoteQueue" in loader
    assert "requestStorageScope !== getClientStoragePrefix()" in loader
    assert "FAILURE_TTL_MS" in loader


def test_consecutive_sender_messages_render_as_one_mixed_content_group():
    app = (ROOT / "ui" / "src" / "App.tsx").read_text(encoding="utf-8")
    card = (ROOT / "ui" / "src" / "MessageContentCard.tsx").read_text(encoding="utf-8")
    grouping = (ROOT / "ui" / "src" / "lib" / "groupedMedia.ts").read_text(encoding="utf-8")

    assert "MESSAGE_GROUP_MAX_GAP_SECONDS = 5 * 60" in grouping
    assert "buildMessageGroupLookup" in app
    assert "fallbackIncomingSenderKey" in app
    assert "groupLookup={messageGroupLookup}" in app
    assert "timelineGroup" not in app
    assert "buildContentBlocks" in card
    assert "group?.messages || [message]" in card
    assert "authorPeerKey" in card
