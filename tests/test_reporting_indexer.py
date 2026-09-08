"""Tests for the Eitaa intent indexer, monitor, and Bale messaging facade."""

from __future__ import annotations

import pytest

from eitaa_bridge.reporting import ReportingService
from eitaa_bridge.reporting.bale_messaging import (
    BaleMessageRecord,
    BaleMessagingError,
    BaleMessagingFacade,
    BaleSendReport,
)
from eitaa_bridge.reporting.indexer import (
    DEFAULT_MONITOR_TARGETS,
    EitaaIntentIndexer,
    MessageIntent,
)
from eitaa_bridge.reporting.model import OccasionClass, ProgramKind
from eitaa_bridge.reporting.monitor import (
    EitaaReportMonitor,
    default_watch_configs,
)


# --------------------------------------------------------------------------
# Intent classification: the three-way split the user mandated
# --------------------------------------------------------------------------


class TestIntentClassification:
    def test_executed_ceremony_report_is_event(self) -> None:
        indexer = EitaaIntentIndexer()
        decision = indexer.classify(
            "مراسم عزاداری ماه محرم با حضور ۱۲۰ نفر کارکنان در دادگستری سوادکوه شمالی برگزار شد",
            message_ref="eitaa:1:10",
            dialog_label="رابطان فرهنگی دادگستری",
        )
        assert decision.intent == MessageIntent.EVENT_REPORT
        assert decision.attendee_count == 120
        assert decision.occasion_class is OccasionClass.RELIGIOUS
        assert "ceremony" in decision.matched_programs
        assert decision.matched_execution

    def test_past_tense_trip_report_maps_to_trip_program(self) -> None:
        indexer = EitaaIntentIndexer()
        decision = indexer.classify(
            "اردوی زیارتی کارکنان با حضور ۶۵ نفر از کارکنان حوزه قضایی انجام شد",
            message_ref="eitaa:1:11",
        )
        assert decision.is_event_report
        assert "trip" in decision.matched_programs

    def test_future_invitation_is_informational_not_event(self) -> None:
        indexer = EitaaIntentIndexer()
        decision = indexer.classify(
            "همکاران محترم به مراسم عید نوروز روز شنبه دعوت میشوید؛ منتظر حضور شما هستیم",
            message_ref="eitaa:1:12",
        )
        assert decision.intent == MessageIntent.INFORMATIONAL
        assert decision.matched_future

    def test_registration_deadline_announcement_is_informational(self) -> None:
        indexer = EitaaIntentIndexer()
        decision = indexer.classify(
            "مهلت ثبتنام مسابقات قرآنی تا پایان هفته است؛ لینک ثبت نام در کانال اطلاع‌رسانی می‌شود",
            message_ref="eitaa:1:13",
        )
        assert decision.intent is not MessageIntent.EVENT_REPORT

    def test_pure_ad_is_promotional(self) -> None:
        indexer = EitaaIntentIndexer()
        decision = indexer.classify(
            "به کانال ما بپیوندید و از تخفیف ویژه خرید بهره‌مند شوید",
            message_ref="eitaa:1:14",
        )
        assert decision.intent == MessageIntent.PROMOTIONAL

    def test_link_only_short_text_is_informational(self) -> None:
        indexer = EitaaIntentIndexer()
        decision = indexer.classify("https://eitaa.me/somechannel", message_ref="eitaa:1:15")
        assert decision.intent == MessageIntent.INFORMATIONAL

    def test_honor_report_requires_execution_signal(self) -> None:
        indexer = EitaaIntentIndexer()
        decision = indexer.classify(
            "مراسم تکریم از همکاران نمونه با حضور مدیران انجام شد و ۱۵ نفر تقدیر شدند",
            message_ref="eitaa:1:16",
        )
        assert decision.is_event_report
        assert "honor" in decision.matched_programs
        assert decision.attendee_count == 15

    def test_greeting_without_activity_is_informational(self) -> None:
        indexer = EitaaIntentIndexer()
        decision = indexer.classify(
            "عید شما مبارک؛ امیدوارم سالی پر از برکت داشته باشید",
            message_ref="eitaa:1:17",
        )
        assert decision.intent == MessageIntent.INFORMATIONAL

    def test_photo_media_mention_counts_as_activity_signal(self) -> None:
        indexer = EitaaIntentIndexer()
        decision = indexer.classify(
            "گالری عکس مراسم هفته وحدت در ستاد استان منتشر شد",
            message_ref="eitaa:1:18",
        )
        assert decision.is_event_report

    def test_evidence_is_fully_visible(self) -> None:
        indexer = EitaaIntentIndexer()
        decision = indexer.classify(
            "مراسم یادبود شهدا در دادگستری با ۵۰ نفر برگزار شد",
            message_ref="eitaa:1:19",
        )
        evidence = decision.evidence()
        assert evidence["intent"] == MessageIntent.EVENT_REPORT
        assert evidence["attendee_count"] == 50
        assert evidence["message_ref"] == "eitaa:1:19"
        assert isinstance(evidence["matched_programs"], list)

    def test_persian_digits_normalized_for_attendees(self) -> None:
        indexer = EitaaIntentIndexer()
        decision = indexer.classify("در مراسم ۷۵ نفر شرکت کننده داشتیم")
        assert decision.attendee_count == 75
        assert decision.is_event_report


# --------------------------------------------------------------------------
# Decision -> reporting candidate bridge
# --------------------------------------------------------------------------


class TestCandidateBridge:
    def test_event_report_becomes_candidate_with_provenance(self) -> None:
        indexer = EitaaIntentIndexer()
        decision = indexer.classify(
            "جشن تکلیف با حضور ۹۰ نفر نومکلف در حوزه قضایی انجام شد",
            message_ref="eitaa:22:33",
        )
        assert decision.is_event_report
        candidate = indexer.candidate_from_decision(decision)
        assert candidate is not None
        assert "prayer" in candidate.suggested_kinds
        assert candidate.extracted_attendees == 90
        assert candidate.source_message_refs == ("eitaa:22:33",)

    def test_non_event_decision_yields_no_candidate(self) -> None:
        indexer = EitaaIntentIndexer()
        decision = indexer.classify("به کانال ما بپیوندید و عضو شوید", message_ref="x:1")
        assert indexer.candidate_from_decision(decision) is None


# --------------------------------------------------------------------------
# Monitor: mandated channels, batching, provider abstention
# --------------------------------------------------------------------------


class TestMonitor:
    def test_default_watch_configs_cover_mandated_targets(self) -> None:
        configs = default_watch_configs()
        labels = tuple(config.label for config in configs)
        assert DEFAULT_MONITOR_TARGETS[0] in labels
        assert DEFAULT_MONITOR_TARGETS[1] in labels

    def test_matches_dialog_by_label_and_keyword(self) -> None:
        monitor = EitaaReportMonitor()
        assert monitor.matches_dialog("مدیریت امور فرهنگی دادگستری") is not None
        assert monitor.matches_dialog("کانال اطلاع رسانی رابطان فرهنگی استان") is not None
        assert monitor.matches_dialog("گروه خانواده") is None

    def test_scan_texts_batches_and_counts(self) -> None:
        monitor = EitaaReportMonitor()
        batch = [
            ("eitaa:1:1", "مدیریت امور فرهنگی دادگستری", "مراسم محرم با ۸۰ نفر برگزار شد"),
            ("eitaa:1:2", "رابطان فرهنگی دادگستری", "به مناسبت هفته آینده دعوت میشوید"),
            ("eitaa:1:3", "رابطان فرهنگی دادگستری", "تخفیف ویژه خرید کالا"),
        ]
        result = monitor.scan_texts(batch)
        assert result.scanned == 3
        assert result.event_reports == 1
        assert result.informational == 1
        assert result.promotional == 1
        assert len(result.candidates) == 1

    def test_scan_provider_abstains_without_runtime(self) -> None:
        class NoRuntime:
            pass

        monitor = EitaaReportMonitor()
        result = monitor.scan_once(NoRuntime())
        assert result.scanned == 0  # abstain, never guess

    def test_scan_provider_with_search_messages(self) -> None:
        class FakeMessage:
            def __init__(self, mid: int, text: str) -> None:
                self.id = mid
                self.text = text
                self.peer = type("P", (), {"id": 1})()

        class FakePage:
            messages = [FakeMessage(1, "مراسم عید فطر با ۶۰ نفر برگزار شد"), FakeMessage(2, "خبر فوری")]

        class FakeCore:
            def search_messages(self, query):  # noqa: ANN001
                return FakePage()

        monitor = EitaaReportMonitor()
        result = monitor.scan_once(FakeCore())
        assert result.scanned == 2
        assert result.event_reports == 1
        assert result.candidates[0].source_message_refs[0].startswith("eitaa:1:")


# --------------------------------------------------------------------------
# ReportingService integration
# --------------------------------------------------------------------------


class TestServiceIntegration:
    def test_service_scan_texts_feeds_candidates(self) -> None:
        service = ReportingService()
        result = service.scan_texts(
            [("eitaa:9:1", "مدیریت امور فرهنگی دادگستری", "مسابقات قرآنی استان با ۴۰ نفر انجام شد")]
        )
        assert result.event_reports == 1
        candidate = result.candidates[0]
        event = service.event_from_candidate(
            candidate, event_id="evt-q1", occurred_on=__import__("datetime").date(2026, 6, 1)
        )
        assert "quran_contest" in [kind.value for kind in event.program_kinds]
        assert event.facts[0].value == 40


# --------------------------------------------------------------------------
# Bale messaging facade
# --------------------------------------------------------------------------


def run_async(coro_func):  # noqa: ANN001
    import asyncio
    import functools

    @functools.wraps(coro_func)
    def wrapper(*args, **kwargs):  # noqa: ANN002
        return asyncio.run(coro_func(*args, **kwargs))

    return wrapper


class FakeBalePeer:
    id = 5001
    title = "مدیریت امور فرهنگی دادگستری"


class FakeBaleClient:
    def __init__(self, *, fail_send: bool = False, fail_history: bool = False) -> None:
        self.sent: list[tuple[object, str]] = []
        self.fail_send = fail_send
        self.fail_history = fail_history

    async def send_text(self, peer, text, *, silent: bool = False):  # noqa: ANN001
        if self.fail_send:
            raise RuntimeError("provider boom")
        self.sent.append((peer, text))
        return b"ok"

    async def load_history(self, peer, *, limit: int = 50):  # noqa: ANN001
        if self.fail_history:
            raise RuntimeError("provider boom")

        class M:
            def __init__(self, mid: int, text: str | None) -> None:
                self.id = mid
                self.text = text
                self.date = "2026-09-08"
                self.from_peer = None

        class Page:
            messages = [
                M(1, "مراسم تکریم بازنشستگان با ۳۰ نفر برگزار شد"),
                M(2, None),  # media-only message, skipped
                M(3, "لینک کانال https://eitaa.me/x"),
            ]

        return Page


class TestBaleMessaging:
    @run_async
    async def test_send_text_success(self) -> None:
        client = FakeBaleClient()
        facade = BaleMessagingFacade(client)
        report = await facade.send_text(FakeBalePeer(), "گزارش تفضیلی ارسال شد")
        assert report.sent is True
        assert client.sent[0][1] == "گزارش تفضیلی ارسال شد"
        assert report.summary()["peer"] == "مدیریت امور فرهنگی دادگستری"

    @run_async
    async def test_send_text_wraps_provider_errors_safely(self) -> None:
        facade = BaleMessagingFacade(FakeBaleClient(fail_send=True))
        with pytest.raises(BaleMessagingError) as excinfo:
            await facade.send_text(FakeBalePeer(), "سلام")
        assert excinfo.value.safe_context["type"] == "RuntimeError"
        assert "boom" not in str(excinfo.value)  # provider text never leaks

    @run_async
    async def test_send_empty_text_rejected(self) -> None:
        facade = BaleMessagingFacade(FakeBaleClient())
        with pytest.raises(BaleMessagingError):
            await facade.send_text(FakeBalePeer(), "   ")

    @run_async
    async def test_fetch_history_normalizes_records(self) -> None:
        facade = BaleMessagingFacade(FakeBaleClient())
        records = await facade.fetch_history_records(FakeBalePeer(), limit=10)
        assert len(records) == 2  # media-only skipped
        assert records[0].message_ref == "bale:5001:1"
        assert records[0].dialog_label == "مدیریت امور فرهنگی دادگستری"

    @run_async
    async def test_fetch_history_wraps_errors(self) -> None:
        facade = BaleMessagingFacade(FakeBaleClient(fail_history=True))
        with pytest.raises(BaleMessagingError):
            await facade.fetch_history_records(FakeBalePeer())

    @run_async
    async def test_scan_peer_runs_shared_intent_pipeline(self) -> None:
        facade = BaleMessagingFacade(FakeBaleClient())
        result = await facade.scan_peer(FakeBalePeer(), limit=10)
        assert result.scanned == 2
        assert result.event_reports == 1  # honor ceremony message
        candidate = result.candidates[0]
        assert candidate.source_message_refs[0] == "bale:5001:1"
        assert candidate.extracted_attendees == 30

    def test_index_records_reuses_eitaa_pipeline(self) -> None:
        facade = BaleMessagingFacade(FakeBaleClient())
        records = [
            BaleMessageRecord(message_ref="bale:5001:1", dialog_label="د", text="اردو زیارتی با ۲۰ نفر انجام شد"),
        ]
        result = facade.index_records(records)
        assert result.event_reports == 1
        assert result.candidates[0].event_key.startswith("eitaa-index:")
