"""Local-only indexing orchestration over public Core message services."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import hashlib
import threading
from typing import Any

from eitaa_core import Peer, PeerType

from .content_index import (
    DEFAULT_SCORE_THRESHOLD,
    IndexLabel,
    LightweightContentClassifier,
    PersianNormalizer,
    TrainingDocument,
)
from ..infrastructure.content_index_store import SQLiteContentIndexStore


ProgressCallback = Callable[[Mapping[str, object]], None]


def _parse_source_key(source_key: str) -> tuple[Peer, int] | None:
    parts = source_key.split(":")
    if len(parts) != 3:
        return None
    try:
        peer = Peer(id=int(parts[1]), type=PeerType(parts[0]))
        message_id = int(parts[2])
    except (TypeError, ValueError):
        return None
    if peer.id <= 0 or message_id <= 0:
        return None
    return peer, message_id


def _text_hash(text: str) -> str:
    return hashlib.sha256(PersianNormalizer.normalize(text).encode("utf-8")).hexdigest()


class LocalContentIndexService:
    """Build a transient model, index local messages and persist suggestions."""

    def __init__(self, store: SQLiteContentIndexStore) -> None:
        self.store = store

    def training_documents(
        self,
        bridge: Any,
        *,
        site_key: str,
        labels: Sequence[IndexLabel],
    ) -> tuple[TrainingDocument, ...]:
        label_ids = {item.id for item in labels}
        evidence: dict[str, dict[str, object]] = {}
        records = bridge.compose_messages_workflow.store.list(site_key=site_key, limit=1000)
        for record in records:
            positive = tuple(sorted(set(record.category_ids) & label_ids))
            if not positive:
                continue
            for source_key in record.source_keys:
                parsed = _parse_source_key(source_key)
                if parsed is None:
                    continue
                peer, message_id = parsed
                message = bridge.core.messages.get(peer, message_id)
                if message is None or not message.text.strip():
                    continue
                current = evidence.setdefault(
                    source_key,
                    {"text": message.text, "positive": set(), "negative": set(), "source": "wordpress"},
                )
                current["positive"].update(positive)

        feedback = self.store.list_feedback(site_key=site_key)
        latest: dict[tuple[str, int], Mapping[str, object]] = {}
        for item in feedback:
            latest[(str(item["source_key"]), int(item["label_id"]))] = item
        for (source_key, label_id), item in latest.items():
            if label_id not in label_ids:
                continue
            parsed = _parse_source_key(source_key)
            if parsed is None:
                continue
            peer, message_id = parsed
            message = bridge.core.messages.get(peer, message_id)
            if message is None or not message.text.strip():
                continue
            current = evidence.setdefault(
                source_key,
                {"text": message.text, "positive": set(), "negative": set(), "source": "feedback"},
            )
            current["source"] = "feedback"
            if item["decision"] == "accept":
                current["positive"].add(label_id)
                current["negative"].discard(label_id)
            else:
                current["negative"].add(label_id)
                current["positive"].discard(label_id)

        return tuple(
            TrainingDocument(
                text=str(item["text"]),
                positive_label_ids=tuple(sorted(item["positive"])),
                negative_label_ids=tuple(sorted(item["negative"])),
                weight=1.5 if item["source"] == "feedback" else 1.0,
                source=str(item["source"]),
            )
            for item in evidence.values()
            if item["positive"] or item["negative"]
        )

    def run(
        self,
        bridge: Any,
        *,
        job_id: str,
        site_key: str,
        peer: Peer,
        labels: Sequence[IndexLabel],
        cancel_event: threading.Event,
        progress: ProgressCallback,
        max_messages: int = 20_000,
        score_threshold: float = DEFAULT_SCORE_THRESHOLD,
    ) -> dict[str, object]:
        if not 1 <= max_messages <= 50_000:
            raise ValueError("max_messages must be between 1 and 50000.")
        self.store.initialize()
        documents = self.training_documents(bridge, site_key=site_key, labels=labels)
        classifier = LightweightContentClassifier(
            labels, score_threshold=score_threshold
        ).fit(documents)
        available = int(bridge.core.messages.count(peer))
        target = min(available, max_messages)
        summary: dict[str, object] = {
            "available_messages": available,
            "target_messages": target,
            "processed_messages": 0,
            "text_messages": 0,
            "indexed_messages": 0,
            "prediction_count": 0,
            "training_documents": len(documents),
            "cold_start": classifier.seed_only,
            "truncated": available > max_messages,
            "model_version": classifier.model_version,
        }
        self.store.start_run(
            job_id=job_id,
            site_key=site_key,
            peer_type=peer.type.value,
            peer_id=peer.id,
            labels=[
                {"id": item.id, "name": item.name, "aliases": list(item.aliases)}
                for item in labels
            ],
            summary=summary,
        )
        progress(summary)
        before_id: int | None = None
        seen_before_ids: set[int] = set()
        result_batch: list[dict[str, object]] = []
        state = "completed"
        while int(summary["processed_messages"]) < target:
            if cancel_event.is_set():
                state = "cancelled"
                break
            remaining = target - int(summary["processed_messages"])
            page = bridge.core.messages.list(
                peer, limit=min(500, remaining), before_id=before_id
            )
            if not page:
                break
            next_before_id = min(message.id for message in page)
            if next_before_id in seen_before_ids:
                break
            seen_before_ids.add(next_before_id)
            for message in page:
                if cancel_event.is_set():
                    state = "cancelled"
                    break
                summary["processed_messages"] = int(summary["processed_messages"]) + 1
                text = message.text.strip()
                predictions = ()
                if text:
                    summary["text_messages"] = int(summary["text_messages"]) + 1
                    predictions = classifier.predict(text)
                safe_predictions = [item.safe_summary() for item in predictions]
                if safe_predictions:
                    summary["indexed_messages"] = int(summary["indexed_messages"]) + 1
                    summary["prediction_count"] = int(summary["prediction_count"]) + len(
                        safe_predictions
                    )
                result_batch.append(
                    {
                        "message_id": message.id,
                        "text_hash": _text_hash(text),
                        "predictions": safe_predictions,
                    }
                )
                if len(result_batch) >= 100:
                    self.store.stage_results(
                        job_id=job_id,
                        site_key=site_key,
                        peer_type=peer.type.value,
                        peer_id=peer.id,
                        model_version=classifier.model_version,
                        rows=result_batch,
                    )
                    result_batch.clear()
                    progress(summary)
            before_id = next_before_id
            progress(summary)
            if state == "cancelled" or len(page) < min(500, remaining):
                break
        if result_batch:
            self.store.stage_results(
                job_id=job_id,
                site_key=site_key,
                peer_type=peer.type.value,
                peer_id=peer.id,
                model_version=classifier.model_version,
                rows=result_batch,
            )
        summary["state"] = state
        if state == "cancelled" and int(summary["processed_messages"]) == 0:
            self.store.discard_staged_results(job_id=job_id)
            summary["visible_results"] = 0
            summary["previous_results_preserved"] = True
            self.store.finish_run(
                job_id=job_id,
                state=state,
                model_version=classifier.model_version,
                summary=summary,
            )
            progress(summary)
            return summary
        summary["visible_results"] = int(summary["processed_messages"])
        promoted = self.store.promote_staged_results(
            job_id=job_id,
            site_key=site_key,
            peer_type=peer.type.value,
            peer_id=peer.id,
            state=state,
            model_version=classifier.model_version,
            summary=summary,
        )
        summary["visible_results"] = promoted
        progress(summary)
        return summary
