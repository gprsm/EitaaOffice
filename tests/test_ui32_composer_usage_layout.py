from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "ui" / "src" / "App.tsx"
CSS = ROOT / "ui" / "src" / "styles.css"
WORKFLOW = ROOT / "src" / "eitaa_bridge" / "application" / "workflows" / "compose_wordpress_post.py"
FACADE = ROOT / "src" / "eitaa_bridge" / "facade.py"


def test_successful_composition_marks_all_committed_sources_used_immediately():
    app = APP.read_text(encoding="utf-8")
    assert "const markWordPressSourcesUsed" in app
    assert "const committedSourceKeys = [...sourceKeys]" in app
    assert "props.markSourcesUsed(committedSourceKeys" in app
    assert "usage_state: 'used' as const" in app
    assert "external_post_id: String(publication.post_id)" in app


def test_composition_store_is_authoritative_fallback_for_used_messages():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    facade = FACADE.read_text(encoding="utf-8")
    assert "composition_records = self.store.find_by_source" in workflow
    assert "existing_post_id = (" in workflow
    assert "composition_post_id = str(records[0].post_id) if records else None" in workflow
    assert "used = bool((publication and publication.external_post_id) or composition)" in facade


def test_bulk_entry_points_are_unified():
    app = APP.read_text(encoding="utf-8")
    assert "ورود شماره‌ها / فایل" not in app
    assert app.count("ارسال و دعوت گروهی") >= 3
    assert "اعضای گفتگو، شماره‌های جدید و دعوت شماره‌ها همگی در یک ابزار" in app


def test_bulk_recipient_and_message_fieldsets_are_two_equal_columns_then_stack():
    app = APP.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    assert "bulk-recipient-fieldset" in app
    assert "bulk-message-kind-row" in app
    assert 'className="textarea w-full message-compose" rows={10}' in app
    assert ".bulk-grid { grid-template-columns: repeat(2, minmax(0, 1fr));" in css
    assert ".bulk-message-kind { width: min(180px, 100%);" in css
    assert "min-height: clamp(300px, 48vh, 560px)" in css
    assert "@media (max-width: 900px)" in css


def test_message_list_usage_falls_back_to_composition_record_when_publication_row_is_missing():
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from eitaa_core import Peer, PeerType
    from eitaa_bridge.facade import EitaaBridge

    record = SimpleNamespace(
        composition_key="roundup-1",
        post_id=596,
        post_url="https://example.test/?p=596",
        status="draft",
        title="عنوان",
        updated_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
    )
    fake = SimpleNamespace(
        site_key="medical-site",
        core=SimpleNamespace(publications=SimpleNamespace(get=lambda *args, **kwargs: None)),
        compose_messages_workflow=SimpleNamespace(
            store=SimpleNamespace(find_by_source=lambda *args, **kwargs: (record,))
        ),
    )

    result = EitaaBridge.wordpress_message_usage_details(
        fake,
        Peer(id=14394054, type=PeerType.CHANNEL, access_hash=987654321),
        11900,
    )

    assert result["used"] is True
    assert result["usage_state"] == "used"
    assert result["external_post_id"] == 596
    assert result["external_url"] == "https://example.test/?p=596"
