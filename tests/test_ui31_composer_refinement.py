from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "ui" / "src" / "App.tsx"
CSS = ROOT / "ui" / "src" / "styles.css"
WORKFLOW = ROOT / "src" / "eitaa_bridge" / "application" / "workflows" / "compose_wordpress_post.py"


def test_successful_wordpress_write_resets_form_and_selected_eitaa_messages():
    app = APP.read_text(encoding="utf-8")
    assert "reset(true)" in app
    assert "if (clearSelection) props.setSelectedKeys([])" in app
    assert "نوشته وردپرس ایجاد شد و فرم پاک شد." in app
    assert "نوشته وردپرس به‌روزرسانی شد و فرم پاک شد." in app


def test_edit_mode_can_append_selected_messages_without_removing_old_sources():
    app = APP.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "const appendSelectedToEdit" in app
    assert "افزودن {props.selectedKeys.filter" in app
    assert "حذف منابع قبلی مجاز نیست" in app
    assert "composition_update_source_removal_blocked" in workflow
    assert "composition_sources_appended" in workflow


def test_bulk_message_composer_is_large_and_responsive():
    app = APP.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    assert 'className="fieldset rounded-box border p-4 bulk-message-fieldset"' in app
    assert 'className="textarea w-full message-compose" rows={10}' in app
    assert ".bulk-message-fieldset" in css
    assert "min-height: clamp(300px, 48vh, 560px)" in css
    assert "min-height: clamp(240px, 34vh, 430px)" in css


def test_invite_mode_explains_direct_invite_permissions_and_server_limits():
    app = APP.read_text(encoding="utf-8")
    assert "دعوت مستقیم به {titleFor(dialog)}" in app
    assert "دسترسی افزودن عضو" in app
    assert "این عملیات صرفاً لینک دعوت ارسال نمی‌کند" in app
