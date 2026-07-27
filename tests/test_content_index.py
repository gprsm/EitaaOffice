from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import threading
import time
from types import SimpleNamespace

import pytest

from eitaa_core import MediaReference, MediaType, Message, Peer, PeerType, save_peer_file

from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.application.content_index import (
    IndexLabel,
    LightweightContentClassifier,
    PersianNormalizer,
    TrainingDocument,
)
from eitaa_bridge.application.content_index_service import LocalContentIndexService
from eitaa_bridge.errors import LocalContentIndexStoreError
from eitaa_bridge.facade import EitaaBridge
from eitaa_bridge.infrastructure.content_index_store import (
    CONTENT_INDEX_SCHEMA,
    SQLiteContentIndexStore,
)


PEER = Peer(id=77001, type=PeerType.CHANNEL, access_hash=123)


def _schema1(path: Path, *, conflicting_staging: bool = False) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            f"""
            CREATE TABLE index_results (
                site_key TEXT, peer_type TEXT, peer_id INTEGER, message_id INTEGER,
                text_hash TEXT, model_version TEXT, predictions_json TEXT,
                indexed_at TEXT,
                PRIMARY KEY (site_key,peer_type,peer_id,message_id)
            );
            CREATE TABLE index_feedback (
                feedback_id INTEGER PRIMARY KEY, site_key TEXT, source_key TEXT,
                label_id INTEGER, label_name TEXT, decision TEXT, created_at TEXT
            );
            CREATE TABLE index_runs (
                job_id TEXT PRIMARY KEY, site_key TEXT, peer_type TEXT,
                peer_id INTEGER, state TEXT, model_version TEXT, labels_json TEXT,
                summary_json TEXT, started_at TEXT, completed_at TEXT
            );
            {"CREATE TABLE index_staging_results (broken TEXT);" if conflicting_staging else ""}
            PRAGMA user_version = 1;
            """
        )


def _start_run(store: SQLiteContentIndexStore, job_id: str) -> None:
    store.start_run(
        job_id=job_id,
        site_key="medical-site",
        peer_type="channel",
        peer_id=PEER.id,
        labels=[{"id": 12, "name": "خدمت اجتماعی", "aliases": []}],
        summary={"state": "running"},
    )


def test_persian_normalizer_unifies_letters_digits_and_half_space():
    assert PersianNormalizer.normalize("كلاس\u200cهاي ۱۲۳") == "کلاس های 123"


def test_classifier_learns_related_phrasing_without_exact_label_phrase():
    classifier = LightweightContentClassifier(
        (IndexLabel(12, "خدمت اجتماعی", ("یادمان شهدا",)),)
    ).fit(
        (
            TrainingDocument(
                text="همکاران با حضور در گلزار، مزار شهیدان را عطرافشانی کردند",
                positive_label_ids=(12,),
            ),
        )
    )
    predictions = classifier.predict(
        "آیین ادای احترام و گل‌افشانی قبور شهیدان برگزار شد"
    )
    assert predictions
    assert predictions[0].label_id == 12
    assert predictions[0].accepted is True
    assert classifier.seed_only is False


def test_schema1_migration_creates_backup_and_staging_table(tmp_path):
    path = tmp_path / "content_index.sqlite3"
    _schema1(path)
    SQLiteContentIndexStore(path).initialize()

    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == CONTENT_INDEX_SCHEMA
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert "index_staging_results" in tables
    backups = list(tmp_path.glob("content_index.schema1.*.bak.sqlite3"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1


def test_failed_schema2_migration_rolls_back_and_keeps_recovery_backup(tmp_path):
    path = tmp_path / "content_index.sqlite3"
    _schema1(path, conflicting_staging=True)

    with pytest.raises(LocalContentIndexStoreError):
        SQLiteContentIndexStore(path).initialize()

    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(index_staging_results)")
        }
    assert columns == {"broken"}
    assert len(list(tmp_path.glob("content_index.schema1.*.bak.sqlite3"))) == 1


def test_staging_promotion_is_atomic_and_failed_run_preserves_visible_results(tmp_path):
    store = SQLiteContentIndexStore(tmp_path / "content_index.sqlite3")
    store.initialize()
    old = [{
        "message_id": 1,
        "text_hash": "a" * 64,
        "predictions": [{"label_id": 12, "label_name": "قدیم"}],
    }]
    store.save_results(
        site_key="medical-site",
        peer_type="channel",
        peer_id=PEER.id,
        model_version="old",
        rows=old,
    )

    _start_run(store, "job-success")
    store.stage_results(
        job_id="job-success",
        site_key="medical-site",
        peer_type="channel",
        peer_id=PEER.id,
        model_version="new",
        rows=[{
            "message_id": 2,
            "text_hash": "b" * 64,
            "predictions": [{"label_id": 12, "label_name": "جدید"}],
        }],
    )
    assert [row["message_id"] for row in store.list_results(
        site_key="medical-site", peer_type="channel", peer_id=PEER.id
    )] == [1]
    promoted = store.promote_staged_results(
        job_id="job-success",
        site_key="medical-site",
        peer_type="channel",
        peer_id=PEER.id,
        state="completed",
        model_version="new",
        summary={"state": "completed"},
    )
    assert promoted == 1
    assert [row["message_id"] for row in store.list_results(
        site_key="medical-site", peer_type="channel", peer_id=PEER.id
    )] == [2]

    _start_run(store, "job-failed")
    store.stage_results(
        job_id="job-failed",
        site_key="medical-site",
        peer_type="channel",
        peer_id=PEER.id,
        model_version="broken",
        rows=[{"message_id": 3, "text_hash": "c" * 64, "predictions": []}],
    )
    store.discard_staged_results(job_id="job-failed")
    store.finish_run(
        job_id="job-failed",
        state="failed",
        model_version=None,
        summary={"state": "failed"},
    )
    assert [row["message_id"] for row in store.list_results(
        site_key="medical-site", peer_type="channel", peer_id=PEER.id
    )] == [2]


def test_index_database_never_receives_raw_message_text(tmp_path):
    path = tmp_path / "content_index.sqlite3"
    store = SQLiteContentIndexStore(path)
    store.initialize()
    _start_run(store, "privacy")
    secret = "متن خصوصی کامل که نباید در پایگاه ایندکس ذخیره شود"
    store.stage_results(
        job_id="privacy",
        site_key="medical-site",
        peer_type="channel",
        peer_id=PEER.id,
        model_version="v1",
        rows=[{"message_id": 9, "text_hash": "d" * 64, "predictions": []}],
    )
    store.promote_staged_results(
        job_id="privacy",
        site_key="medical-site",
        peer_type="channel",
        peer_id=PEER.id,
        state="completed",
        model_version="v1",
        summary={"processed_messages": 1},
    )
    assert secret.encode("utf-8") not in path.read_bytes()


def test_zero_progress_cancel_preserves_previous_results(tmp_path):
    store = SQLiteContentIndexStore(tmp_path / "content_index.sqlite3")
    store.initialize()
    store.save_results(
        site_key="medical-site",
        peer_type="channel",
        peer_id=PEER.id,
        model_version="old",
        rows=[{"message_id": 1, "text_hash": "e" * 64, "predictions": []}],
    )
    cancellation = threading.Event()
    cancellation.set()
    bridge = SimpleNamespace(
        compose_messages_workflow=SimpleNamespace(
            store=SimpleNamespace(list=lambda **kwargs: ())
        ),
        core=SimpleNamespace(
            messages=SimpleNamespace(
                count=lambda peer: 10,
                list=lambda peer, **kwargs: pytest.fail("cancelled run must not read rows"),
                get=lambda peer, message_id: None,
            )
        ),
    )
    result = LocalContentIndexService(store).run(
        bridge,
        job_id="cancel-zero",
        site_key="medical-site",
        peer=PEER,
        labels=(IndexLabel(12, "خدمت اجتماعی"),),
        cancel_event=cancellation,
        progress=lambda summary: None,
    )
    assert result["state"] == "cancelled"
    assert result["previous_results_preserved"] is True
    assert [row["message_id"] for row in store.list_results(
        site_key="medical-site", peer_type="channel", peer_id=PEER.id
    )] == [1]


def test_mid_run_cancel_promotes_only_the_processed_consistent_prefix(tmp_path):
    store = SQLiteContentIndexStore(tmp_path / "content_index.sqlite3")
    cancellation = threading.Event()
    items = tuple(
        Message(
            id=message_id,
            peer=PEER,
            date=datetime(2026, 7, 24, tzinfo=timezone.utc),
            text=f"گزارش خدمت اجتماعی شماره {message_id}",
        )
        for message_id in range(150, 0, -1)
    )

    def list_messages(peer, *, limit, before_id=None):
        selected = tuple(
            item for item in items if before_id is None or item.id < before_id
        )
        return selected[:limit]

    bridge = SimpleNamespace(
        compose_messages_workflow=SimpleNamespace(
            store=SimpleNamespace(list=lambda **kwargs: ())
        ),
        core=SimpleNamespace(
            messages=SimpleNamespace(
                count=lambda peer: len(items),
                list=list_messages,
                get=lambda peer, message_id: None,
            )
        ),
    )

    def progress(summary):
        if int(summary["processed_messages"]) >= 100:
            cancellation.set()

    result = LocalContentIndexService(store).run(
        bridge,
        job_id="cancel-mid",
        site_key="medical-site",
        peer=PEER,
        labels=(IndexLabel(12, "خدمت اجتماعی"),),
        cancel_event=cancellation,
        progress=progress,
    )
    visible = store.list_results(
        site_key="medical-site", peer_type="channel", peer_id=PEER.id
    )
    assert result["state"] == "cancelled"
    assert result["processed_messages"] == 100
    assert result["visible_results"] == 100
    assert len(visible) == 100
    assert len({row["model_version"] for row in visible}) == 1


def test_facade_serializes_only_reliable_sender_keys_for_inferred_gallery():
    sender = Peer(id=55, type=PeerType.USER)
    base = Message(
        id=1,
        peer=PEER,
        date=datetime(2026, 7, 24, tzinfo=timezone.utc),
        media=MediaReference(MediaType.PHOTO, remote_id=1),
        from_peer=sender,
    )

    class Harness:
        _application_message_item = EitaaBridge._application_message_item

        @staticmethod
        def wordpress_message_usage_details(peer, message_id):
            return {"used": False, "usage_state": "unused", "stale": False, "compositions": []}

    harness = Harness()
    assert harness._application_message_item(PEER, base)["sender_key"] == "user:55"
    channel_authored = Message(
        id=2,
        peer=PEER,
        date=base.date,
        media=base.media,
        from_peer=PEER,
    )
    assert harness._application_message_item(PEER, channel_authored)["sender_key"] is None


def test_api_runs_local_index_on_own_worker_without_eitaa_scheduler(
    config_file, tmp_path, monkeypatch
):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    peer_file = tmp_path / "peer.json"
    save_peer_file(peer_file, PEER)
    observed: dict[str, str] = {}

    class Context:
        def __enter__(self):
            return SimpleNamespace()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context())

    def fake_run(self, bridge, **kwargs):
        observed["thread"] = threading.current_thread().name
        return {
            "state": "completed",
            "processed_messages": 0,
            "target_messages": 0,
            "indexed_messages": 0,
        }

    monkeypatch.setattr(LocalContentIndexService, "run", fake_run)
    api = BridgeApplicationApi(config_file)
    monkeypatch.setattr(
        api,
        "_run_eitaa",
        lambda *args, **kwargs: pytest.fail("local indexing must not use Eitaa scheduler"),
    )
    started = api.dispatch(
        "POST",
        "/api/v1/messages/index/start",
        body={
            "site_key": "medical-site",
            "peer_file": str(peer_file),
            "labels": [{"id": 12, "name": "خدمت اجتماعی", "aliases": []}],
            "max_messages": 20,
        },
    )
    assert started.status == 202
    job_id = started.payload["job"]["job_id"]
    status = None
    for _ in range(100):
        status = api.dispatch(
            "GET", f"/api/v1/messages/index/status?job_id={job_id}"
        )
        if status.payload["job"]["state"] == "completed":
            break
        time.sleep(0.01)
    assert status is not None
    assert status.payload["job"]["state"] == "completed"
    assert observed["thread"].startswith("local-content-index-")
    api.close()


def test_manual_feedback_is_visible_immediately_without_reindex(config_file, tmp_path):
    peer_file = tmp_path / "peer.json"
    save_peer_file(peer_file, PEER)
    api = BridgeApplicationApi(config_file)
    api._content_index_store.initialize()
    api._content_index_store.save_results(
        site_key="medical-site",
        peer_type=PEER.type.value,
        peer_id=PEER.id,
        model_version="test",
        rows=[
            {
                "message_id": 41,
                "text_hash": "hash",
                "predictions": [
                    {
                        "label_id": 12,
                        "label_name": "قدیمی",
                        "score": 0.7,
                        "evidence": [],
                        "accepted": True,
                    }
                ],
            }
        ],
    )
    rejected = api.dispatch(
        "POST",
        "/api/v1/messages/index/feedback",
        body={
            "site_key": "medical-site",
            "peer_file": str(peer_file),
            "message_id": 41,
            "label_id": 12,
            "label_name": "قدیمی",
            "decision": "reject",
        },
    )
    assert rejected.payload["applies_on_next_run"] is False
    accepted = api.dispatch(
        "POST",
        "/api/v1/messages/index/feedback",
        body={
            "site_key": "medical-site",
            "peer_file": str(peer_file),
            "message_id": 41,
            "label_id": 15,
            "label_name": "اصلاح‌شده",
            "decision": "accept",
        },
    )
    assert accepted.status == 201
    results = api.dispatch(
        "POST",
        "/api/v1/messages/index/results",
        body={"site_key": "medical-site", "peer_file": str(peer_file)},
    )
    predictions = results.payload["results"][0]["predictions"]
    assert [item["label_id"] for item in predictions] == [15]
    assert predictions[0]["manual"] is True
    api.close()
