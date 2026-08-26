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
    app = read("App.tsx") + read("utils/helpers.tsx")
    workbench = read("MessageFilterDialog.tsx")
    index = read("ContentIndexDialog.tsx")
    assert "<MessageFilterDialog" in app
    assert "<ContentIndexDialog" in app
    assert "content-filter-popover" not in app
    assert "<Dialog" in workbench
    assert "<Dialog" in index
    assert "فیلتر نمایش پیام‌ها" in workbench
    assert "ایندکس‌گذاری محتوا" in index


def test_sender_filter_uses_names_and_marks_eitaa_contacts() -> None:
    app = read("App.tsx") + read("utils/helpers.tsx")
    workbench = read("MessageFilterDialog.tsx")
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
    app = read("App.tsx") + read("utils/helpers.tsx")
    assert "limit: 5_000" in app
    assert "max_messages: 5_000" in app
    assert "limit: 50_000" not in app
    assert "max_messages: 20_000" not in app


def test_media_requests_are_deduplicated_with_stable_callbacks() -> None:
    app = read("App.tsx") + read("utils/helpers.tsx")
    assert "mediaRequestsRef.current.has(key)" in app
    assert "fullMediaRequestsRef.current.has(key)" in app
    assert "mediaCacheRef.current" in app
    assert "}, [dialog, mediaReadSupported, siteKey])" in app


def test_installer_requires_material_build_marker() -> None:
    install = (ROOT / "install_app.bat").read_text(encoding="utf-8", errors="ignore")
    finalize = (ROOT / "ui" / "scripts" / "finalize-ui-build.mjs").read_text(encoding="utf-8")
    assert 'ui\\dist\\.material-ui-v1' in install
    assert ".material-ui-v1" in finalize


def test_login_and_startup_surfaces_use_material_components() -> None:
    app = read("App.tsx") + read("utils/helpers.tsx")
    login = read("LoginExperience.tsx")
    assert "export function LoginSurface" in login
    assert "<TextField" in app
    assert "<CircularProgress" in app
    assert "<Alert severity=\"error\"" in app
    assert '<form className="login-card card"' not in login
    assert "مرکز یکپارچهٔ محتوای ایتا" not in login
    assert "آماده برای معماری چندحسابی ایزوله" not in login
    assert "gridTemplateColumns" not in login
    assert "justifySelf: 'center'" in login


def test_invalid_session_recovery_is_automatic_and_hides_archive_internals() -> None:
    app = read("App.tsx") + read("utils/helpers.tsx")
    api_client = read("lib/api.ts")
    assert "AUTH_SESSION_INVALID_EVENT" in api_client
    assert "error.code === 'auth_session_invalid'" in api_client
    assert "window.dispatchEvent(new Event(AUTH_SESSION_INVALID_EVENT))" in api_client
    assert "window.addEventListener(AUTH_SESSION_INVALID_EVENT" in app
    assert "status.session_error_code === 'auth_session_invalid'" in app
    assert "automatic_recovery: true" in app
    assert "'POST', '/api/v1/auth/request-code', {}" in app
    assert "نشست ایتا نیاز به بررسی دارد" not in app
    assert "بایگانی نشست و ورود تازه" not in app


def test_provider_session_invalidation_does_not_clear_app_user_csrf() -> None:
    api_client = read("lib/api.ts")
    assert "path === '/api/v2/app-auth/status' && result.payload?.session_invalid" in api_client
    assert "path === '/api/v2/app-auth/logout' || result.payload?.session_invalid" not in api_client


def test_login_gate_normalizes_localized_otp_input_before_submission() -> None:
    app = read("App.tsx") + read("utils/helpers.tsx")
    assert "function normalizeLoginCodeInput" in app
    assert "setCode(normalizeLoginCodeInput(e.target.value))" in app
    assert "code: normalizeLoginCodeInput(code)" in app
    assert "e.code === 'auth_provider_code_expired'" in app
    assert "دریافت کد تازه" in app


def test_message_content_is_a_modular_material_card_with_author_header() -> None:
    app = read("App.tsx") + read("utils/helpers.tsx")
    card = read("MessageContentCard.tsx")
    assert "from './MessageContentCard'" in app
    assert "<MessageContentCard" in app
    for component in (
        "Card",
        "CardHeader",
        "CardMedia",
        "CardContent",
        "CardActions",
        "Collapse",
        "Avatar",
        "IconButton",
        "Typography",
    ):
        assert component in card
    assert "authorLabel" in card
    assert "sender_display_name" in card
    assert "sender_is_eitaa_contact" in card
    assert "className=" not in card


def test_legacy_operational_dialogs_are_contained_by_material_dialogs() -> None:
    app = read("App.tsx") + read("utils/helpers.tsx")
    assert app.count("<MaterialLegacyDialog") >= 4
    assert "fullScreen={fullScreen}" in app
    assert "return <Dialog open" in app
    assert "className=" not in app


def test_contact_and_community_large_lists_use_incremental_virtual_rendering() -> None:
    app = read("App.tsx") + read("utils/helpers.tsx")
    contacts = read("ContactDirectoryModal.tsx")
    assert "limit: 300" not in app
    assert "requestMemberPage(offset, 200)" in app
    assert "requestMemberPage(offset, 1_000)" in app
    assert "memberVirtualizer.getVirtualItems()" in app
    assert "سقف ۳۰۰ عضو حذف شده است" not in app
    assert "snapshot_total_count" in app
    assert "autoSyncAttemptedRef" in app
    assert "useState(250)" in contacts
    assert "setInterval(() =>" in contacts and "}, 1000)" in contacts
    assert "Math.ceil(expectedTotal / 25) + 20" in app


def test_member_management_button_keeps_readable_contrast() -> None:
    app = read("App.tsx") + read("utils/helpers.tsx")
    theme = read("theme.ts")
    assert '<Button variant="outlined" disabled={!props.dialog || props.dialog.display_kind === \'personal\'} onClick={props.openMembers}>مدیریت اعضا</Button>' in app
    assert "containedPrimary: { color: '#07131f' }" in theme
    assert "MuiButton" in theme


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
    app = read("App.tsx") + read("utils/helpers.tsx")
    conversations = read("ConversationListPage.tsx")
    assert "filteredDialogs.slice(0, 500)" in app
    assert "items.map" in conversations
    assert "برای حفظ سرعت، ۵۰۰ گفت‌وگوی نخست" in conversations
    assert 'label="جست‌وجوی گفتگو"' in conversations


def test_material_index_dialog_is_not_closed_by_workspace_click_bubbling() -> None:
    app = read("App.tsx") + read("utils/helpers.tsx")
    overlay_line = next(line for line in app.splitlines() if '<Box role="presentation" onClick=' in line)
    assert "setContentFiltersOpen(false)" not in overlay_line
    assert "close={() => setContentFiltersOpen(false)}" in app


def test_index_selection_effect_has_no_nested_state_update_side_effects() -> None:
    app = read("App.tsx") + read("utils/helpers.tsx")
    assert "setIndexKeywordCategoryId(current =>" not in app
    assert "const selectedDefinition = indexDefinitions.find" in app


def test_contact_initial_load_does_not_duplicate_the_contact_query() -> None:
    contacts = read("ContactDirectoryModal.tsx")
    assert "useEffect(() => { void loadCategories() }, [loadCategories])" in contacts
    assert "useEffect(() => { void Promise.all([loadCategories(), loadContacts()])" not in contacts


def test_settings_exposes_one_material_network_port_control() -> None:
    settings = read("SettingsPage.tsx")
    assert "شبکه و وب" in settings
    assert "پورت داخلی برنامه" in settings
    assert "تنها محل تنظیم پورت داخلی" in settings
    assert "'/api/v2/settings/deployment'" in settings
    assert "'/api/v2/settings/deployment/port'" in settings
    assert "پس از ذخیره برنامه باید دوباره اجرا شود" in settings
    assert "proxy_update_required" in settings
    assert "className=" not in settings


def test_mobile_bottom_navigation_opens_filtered_conversation_list_and_header_goes_back() -> None:
    app = read("App.tsx") + read("utils/helpers.tsx")
    header = read("ChatHeader.tsx")
    navigation = read("WorkspaceNavigation.tsx")
    assert "const showDialogSection = useCallback" in app
    assert "setTab(value)" in app
    assert "if (!chatsDocked)" in app
    assert "setChatsOpen(true)" in app
    assert "setComposerOpen(false)" in app
    assert "onSection={showDialogSection}" in app
    assert "window.matchMedia('(max-width: 899px)').matches" in app
    assert 'aria-label="بازگشت به فهرست گفتگوها"' in header
    assert "<ArrowForwardRounded />" in header
    assert "onChange={(_event, index) => onSection" in navigation


def test_mobile_header_hides_live_success_noise_and_aligns_wordpress_opposite_menu() -> None:
    header = read("ChatHeader.tsx")
    assert "همگام‌سازی زنده" not in header
    assert "liveState !== 'idle' && liveState !== 'live'" in header
    assert "insetInlineEnd: 'max(8px, env(safe-area-inset-right))'" in header
    assert "top: 'max(8px, env(safe-area-inset-top))'" in header
    assert "theme.zIndex.appBar + 1" in header
    assert "width: 48, height: 48" in header
