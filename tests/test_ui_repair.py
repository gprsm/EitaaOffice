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
    app = (ROOT / "ui" / "src" / "App.tsx").read_text(encoding="utf-8")
    css = (ROOT / "ui" / "src" / "styles.css").read_text(encoding="utf-8")

    assert "tab-active" not in app
    assert 'name="composer_sections"' not in app
    assert 'name="manual_dialog_mode"' not in app
    assert ">وردپرس</button>" in app
    assert ">عملیات گفتگو</button>" in app
    assert ">با نام کاربری</button>" in app
    assert ">شناسه و Access Hash</button>" in app
    assert 'role="tab"' in app
    assert "aria-selected=" in app
    assert "composer-chrome" in app
    assert "top: 66px" not in css
    assert ".composer-chrome" in css
    assert '.tab[aria-selected="true"]' in css


def test_ui_labels_do_not_claim_xlsx_support_and_primitives_are_complete():
    app = (ROOT / "ui" / "src" / "App.tsx").read_text(encoding="utf-8")
    css = (ROOT / "ui" / "src" / "styles.css").read_text(encoding="utf-8")

    assert "ورود Excel" not in app
    assert "انتخاب TXT/CSV" in app
    assert "ورود شماره‌ها / فایل" not in app
    assert "background-image:" in css
    assert ".select" in css
    assert ".checkbox:checked" in css
    assert "button:focus-visible" in css


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


def test_installer_runs_font_sync_without_requiring_node_for_prebuilt_ui():
    installer = (ROOT / "install_app.bat").read_text(encoding="utf-8")
    assert "scripts\\sync_ui_fonts.py --quiet" in installer
    assert "Node.js, npm packages, and Electron are development-only" in installer


def test_wordpress_ui_keeps_category_tree_and_stays_quiet_without_credentials():
    app = (ROOT / "ui" / "src" / "App.tsx").read_text(encoding="utf-8")
    types = (ROOT / "ui" / "src" / "lib" / "types.ts").read_text(encoding="utf-8")
    css = (ROOT / "ui" / "src" / "styles.css").read_text(encoding="utf-8")

    assert "parent_id?: number | null" in types
    assert "function categoryTree(" in app
    assert 'role="tree"' in app
    assert "aria-level={depth + 1}" in app
    assert ".category-tree-row" in css
    assert "!activeSite?.credentials_configured" in app
    assert "wordpressReady" in app
    assert "wordpress-unavailable" in app


def test_dialog_sync_and_avatar_ui_do_not_report_benign_or_fetch_remote_work():
    app = (ROOT / "ui" / "src" / "App.tsx").read_text(encoding="utf-8")
    loader = (ROOT / "ui" / "src" / "lib" / "avatarLoader.ts").read_text(encoding="utf-8")

    assert "unusable_peer_missing_access_hash" in app
    assert "گفتگوی حذف‌شده یا غیرقابل استفاده کنار گذاشته شد" in app
    assert "IntersectionObserver" in app
    assert "loadDialogAvatar" in app
    assert "peekDialogAvatar" in app
    assert "cached_only: false" in loader
    assert "avatarRequests" in loader
