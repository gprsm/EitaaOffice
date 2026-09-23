from __future__ import annotations

import pytest

from eitaa_bridge.reporting import (
    AgentSuggestion,
    ReportingService,
    ReportingStore,
    ReportingSuggester,
)


def test_suggester_ashura_pilgrimage():
    suggester = ReportingSuggester()
    text = "مراسم پرفیض قرائت زیارت عاشورا صبح امروز پنجشنبه در نمازخانه دادگستری کل استان برگزار شد و با صرف صبحانه به پایان رسید."
    suggestion = suggester.analyze(
        candidate_id="cand-1",
        text=text,
        dialog_label="کانال ستاد دادگستری",
    )
    assert suggestion.candidate_id == "cand-1"
    assert suggestion.recommended_program == "ceremonies"
    assert suggestion.is_ashura_pilgrimage is True
    assert "C12" in suggestion.reasoning
    assert suggestion.star_field_hints.get("reception") == 1


def test_suggester_honor_with_chief_justice():
    suggester = ReportingSuggester()
    text = (
        "مراسم تجلیل و تکریم از بازنشستگان و قضات برجسته دادگستری با حضور حجت‌الاسلام والمسلمین اکبری "
        "رئیس‌کل محترم دادگستری استان مازندران برگزار گردید و از ۱۲ نفر تقدیر شد."
    )
    suggestion = suggester.analyze(
        candidate_id="cand-2",
        text=text,
        dialog_label="اخبار دادگستری مازندران",
    )
    assert suggestion.recommended_program == "honor"
    assert suggestion.official_present_suggested is True
    assert suggestion.extracted_attendees == 12
    assert "B9" in suggestion.reasoning


def test_suggester_courthouse_extraction():
    suggester = ReportingSuggester()
    text = "جشن تکلیف فرزندان نومکلف در دادگستری شهرستان آمل برگزار گردید و به ۲۵ نفر بسته فرهنگی اهداء شد."
    suggestion = suggester.analyze(
        candidate_id="cand-3",
        text=text,
        dialog_label="حوزه قضایی آمل",
    )
    assert suggestion.recommended_program == "prayer"
    assert suggestion.extracted_unit_scope == "courthouse"
    assert "آمل" in suggestion.extracted_unit_name
    assert suggestion.extracted_attendees == 25
    assert suggestion.star_field_hints.get("culture_pack") == 1


def test_suggester_service_integration(tmp_path):
    db_path = tmp_path / "reporting.sqlite3"
    store = ReportingStore(db_path=db_path)
    service = ReportingService(store=store)

    text = "اردوی زیارتی همکاران دادگستری به مشهد مقدس با حضور ۴۰ نفر برگزار شد."
    suggestion = service.suggest_candidate_review(
        candidate_id="cand-temp",
        text=text,
        dialog_label="اردویی",
    )
    assert suggestion is not None
    assert suggestion.recommended_program == "trip"
    assert suggestion.extracted_attendees == 40
    data = suggestion.to_dict()
    assert data["recommended_program"] == "trip"
    assert data["confidence"] > 0.8
