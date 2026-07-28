from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "ui" / "src"


def read(name: str) -> str:
    return (UI / name).read_text(encoding="utf-8")


def test_material_ui_dependencies_and_rtl_cache() -> None:
    package = json.loads((ROOT / "ui" / "package.json").read_text(encoding="utf-8"))
    dependencies = package["dependencies"]
    for name in ("@mui/material", "@mui/icons-material", "@emotion/react", "@emotion/styled", "@emotion/cache", "stylis-plugin-rtl"):
        assert name in dependencies
    main = read("main.tsx")
    assert "CacheProvider value={rtlCache}" in main
    assert "ThemeProvider theme={appTheme}" in main


def test_index_workbench_is_material_dialog_and_not_header_popover() -> None:
    app = read("App.tsx")
    workbench = read("MaterialIndexWorkbench.tsx")
    assert "<MaterialIndexWorkbench" in app
    assert "content-filter-popover" not in app
    assert "<Dialog" in workbench
    assert "<Grid container" in workbench
    assert "fullScreen={fullScreen}" in workbench
    assert "ایندکس‌گذاری" in workbench and "نمایش و فیلتر" in workbench


def test_sender_filter_uses_names_and_marks_eitaa_contacts() -> None:
    app = read("App.tsx")
    workbench = read("MaterialIndexWorkbench.tsx")
    types = read("lib/types.ts")
    assert "sender_display_name" in types
    assert "sender_is_eitaa_contact" in types
    assert "کاربر ناشناس · شناسه" in app
    assert "/api/v1/messages/sync" in app
    assert "stop_when_unchanged: false" in app
    assert "senderResolutionState" in app
    assert "sender.isEitaaContact" in workbench
    assert 'label="مخاطب ایتا"' in workbench
    assert "sender.label" in workbench


def test_multi_index_editor_is_searchable_and_bounded() -> None:
    editor = read("MessageIndexEditor.tsx")
    assert "جست‌وجوی ایندکس" in editor
    assert "slice(0, 500)" in editor
    assert "چند ایندکس" in editor


def test_contact_directory_is_material_and_bounded() -> None:
    contacts = read("ContactDirectoryModal.tsx")
    assert "<Dialog open" in contacts
    assert "<Grid container" in contacts
    assert "limit: contactLimit" in contacts
    assert "useState(250)" in contacts
    assert "limit: 10_000" not in contacts
    assert "مخاطبان ایتا" in contacts
    assert "/api/v1/eitaa-contacts/list" in contacts


def test_heavy_index_and_message_reads_are_capped() -> None:
    app = read("App.tsx")
    assert "limit: 5_000" in app
    assert "max_messages: 5_000" in app
    assert "limit: 50_000" not in app
    assert "max_messages: 20_000" not in app


def test_media_requests_are_deduplicated_with_stable_callbacks() -> None:
    app = read("App.tsx")
    assert "mediaRequestsRef.current.has(key)" in app
    assert "fullMediaRequestsRef.current.has(key)" in app
    assert "mediaCacheRef.current" in app
    assert "}, [dialog, siteKey])" in app


def test_installer_requires_material_build_marker() -> None:
    install = (ROOT / "install_app.bat").read_text(encoding="utf-8", errors="ignore")
    finalize = (ROOT / "ui" / "scripts" / "finalize-ui-build.mjs").read_text(encoding="utf-8")
    assert 'ui\\dist\\.material-ui-v1' in install
    assert ".material-ui-v1" in finalize


def test_login_and_startup_surfaces_use_material_components() -> None:
    app = read("App.tsx")
    login = read("LoginExperience.tsx")
    assert "export function LoginSurface" in login
    assert "<TextField" in app
    assert "<CircularProgress" in app
    assert "<Alert severity=\"error\"" in app
    assert '<form className="login-card card"' not in login


def test_invalid_session_errors_return_to_the_recovery_surface() -> None:
    app = read("App.tsx")
    api_client = read("lib/api.ts")
    assert "AUTH_SESSION_INVALID_EVENT" in api_client
    assert "error.code === 'auth_session_invalid'" in api_client
    assert "window.dispatchEvent(new Event(AUTH_SESSION_INVALID_EVENT))" in api_client
    assert "window.addEventListener(AUTH_SESSION_INVALID_EVENT" in app
    assert "status.session_error_code === 'auth_session_invalid'" in app
    assert "/api/v1/auth/reset-local-session" in app


def test_legacy_operational_dialogs_are_contained_by_material_dialogs() -> None:
    app = read("App.tsx")
    assert app.count("<MaterialLegacyDialog") >= 5
    assert "fullScreen={fullScreen}" in app
    assert 'className="material-legacy-dialog-content"' in app


def test_contact_and_community_render_limits_are_safe() -> None:
    app = read("App.tsx")
    contacts = read("ContactDirectoryModal.tsx")
    assert "limit: 300" in app
    assert "useState(250)" in contacts
    assert "setInterval(() =>" in contacts and "}, 1000)" in contacts
    assert "max_pages: Math.min(250" in app


def test_index_editor_uses_a_real_checkbox_control() -> None:
    editor = read("MessageIndexEditor.tsx")
    assert "control={<Checkbox" in editor
    assert "control={<span />}" not in editor
    assert "secondaryAction=" not in editor


def test_ui_build_scripts_do_not_contain_machine_specific_node_paths() -> None:
    scripts = [
        (ROOT / "ui" / "scripts" / "run-scroll-tests.mjs").read_text(encoding="utf-8"),
        (ROOT / "ui" / "scripts" / "run-grouped-media-tests.mjs").read_text(encoding="utf-8"),
    ]
    for script in scripts:
        assert "/opt/nvm/" not in script
        assert "npm', ['root', '-g']" in script


def test_old_material_compile_stub_is_not_shipped() -> None:
    assert not (UI / "__mui_compile_stub.d.ts").exists()


def test_dialog_rendering_is_bounded_and_search_remains_available() -> None:
    app = read("App.tsx")
    assert "filteredDialogs.slice(0, 500)" in app
    assert "visibleDialogs.map" in app
    assert "برای حفظ سرعت، ۵۰۰ گفت‌وگوی نخست" in app


def test_material_index_dialog_is_not_closed_by_workspace_click_bubbling() -> None:
    app = read("App.tsx")
    workspace_line = next(line for line in app.splitlines() if 'className="workspace telegram-workspace"' in line)
    assert "setContentFiltersOpen(false)" not in workspace_line


def test_index_selection_effect_has_no_nested_state_update_side_effects() -> None:
    app = read("App.tsx")
    assert "setIndexKeywordCategoryId(current =>" not in app
    assert "const selectedDefinition = indexDefinitions.find" in app


def test_contact_initial_load_does_not_duplicate_the_contact_query() -> None:
    contacts = read("ContactDirectoryModal.tsx")
    assert "useEffect(() => { void loadCategories() }, [loadCategories])" in contacts
    assert "useEffect(() => { void Promise.all([loadCategories(), loadContacts()])" not in contacts
