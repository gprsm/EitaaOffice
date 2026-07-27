"""Explainable, dependency-free Persian multi-label content indexing."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
import re
import unicodedata
from typing import Iterable, Mapping, Sequence


ALGORITHM_VERSION = "persian-tfidf-centroid-v1"
DEFAULT_SCORE_THRESHOLD = 0.13


@dataclass(slots=True, frozen=True)
class IndexLabel:
    id: int
    name: str
    aliases: tuple[str, ...] = ()

    def validate(self) -> None:
        if self.id <= 0:
            raise ValueError("Index label id must be positive.")
        if not self.name.strip() or len(self.name) > 200:
            raise ValueError("Index label name must contain 1 to 200 characters.")
        if len(self.aliases) > 50:
            raise ValueError("An index label cannot have more than 50 aliases.")
        if any(not item.strip() or len(item) > 200 for item in self.aliases):
            raise ValueError("Index label aliases must contain 1 to 200 characters.")


@dataclass(slots=True, frozen=True)
class TrainingDocument:
    text: str
    positive_label_ids: tuple[int, ...]
    negative_label_ids: tuple[int, ...] = ()
    weight: float = 1.0
    source: str = "confirmed"

    def validate(self) -> None:
        if not self.text.strip():
            raise ValueError("Training text cannot be empty.")
        if not self.positive_label_ids and not self.negative_label_ids:
            raise ValueError("Training evidence must have a positive or negative label.")
        if self.weight <= 0 or self.weight > 10:
            raise ValueError("Training document weight must be between 0 and 10.")


@dataclass(slots=True, frozen=True)
class IndexPrediction:
    label_id: int
    label_name: str
    score: float
    evidence: tuple[str, ...]
    accepted: bool

    def safe_summary(self) -> dict[str, object]:
        return {
            "label_id": self.label_id,
            "label_name": self.label_name,
            "score": round(self.score, 4),
            "evidence": list(self.evidence),
            "accepted": self.accepted,
        }


class PersianNormalizer:
    """Normalize common Persian/Arabic variants without external libraries."""

    _translation = str.maketrans(
        {
            "ي": "ی",
            "ى": "ی",
            "ئ": "ی",
            "ك": "ک",
            "ة": "ه",
            "ۀ": "ه",
            "ؤ": "و",
            "أ": "ا",
            "إ": "ا",
            "ٱ": "ا",
            "ـ": "",
            "\u200c": " ",
            "\u200d": " ",
            "\ufeff": " ",
            "۰": "0",
            "۱": "1",
            "۲": "2",
            "۳": "3",
            "۴": "4",
            "۵": "5",
            "۶": "6",
            "۷": "7",
            "۸": "8",
            "۹": "9",
            "٠": "0",
            "١": "1",
            "٢": "2",
            "٣": "3",
            "٤": "4",
            "٥": "5",
            "٦": "6",
            "٧": "7",
            "٨": "8",
            "٩": "9",
        }
    )
    _token_pattern = re.compile(r"[آ-یa-z0-9]+", re.IGNORECASE)

    @classmethod
    def normalize(cls, text: str) -> str:
        selected = unicodedata.normalize("NFKC", str(text)).translate(cls._translation).lower()
        selected = "".join(
            character
            for character in selected
            if unicodedata.category(character) not in {"Mn", "Me"}
        )
        return " ".join(cls._token_pattern.findall(selected))

    @classmethod
    def tokens(cls, text: str) -> tuple[str, ...]:
        return tuple(cls.normalize(text).split())


_STOPWORDS = {
    "از",
    "به",
    "با",
    "در",
    "برای",
    "و",
    "یا",
    "که",
    "این",
    "آن",
    "یک",
    "را",
    "شد",
    "شده",
    "می",
    "است",
    "بود",
    "بر",
    "تا",
    "هم",
}


def _features(text: str) -> Counter[str]:
    normalized = PersianNormalizer.normalize(text)
    tokens = tuple(item for item in normalized.split() if len(item) > 1)
    content_tokens = tuple(item for item in tokens if item not in _STOPWORDS)
    selected = content_tokens or tokens
    result: Counter[str] = Counter()
    for token in selected:
        result[f"w:{token}"] += 1.0
    for left, right in zip(selected, selected[1:]):
        result[f"b:{left} {right}"] += 1.35
    compact = " ".join(selected)
    for size, weight in ((3, 0.16), (4, 0.20), (5, 0.24)):
        if len(compact) < size:
            continue
        for offset in range(len(compact) - size + 1):
            gram = compact[offset : offset + size]
            if gram.strip() and not gram.isspace():
                result[f"c{size}:{gram}"] += weight
    return result


def _normalize_vector(vector: Mapping[str, float]) -> dict[str, float]:
    norm = math.sqrt(sum(value * value for value in vector.values()))
    if norm <= 0:
        return {}
    return {key: value / norm for key, value in vector.items() if value}


def _cosine(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(key, 0.0) for key, value in left.items())


class LightweightContentClassifier:
    """Small TF-IDF centroid model with explainable cautious predictions."""

    def __init__(
        self,
        labels: Sequence[IndexLabel],
        *,
        score_threshold: float = DEFAULT_SCORE_THRESHOLD,
    ) -> None:
        if not 0.05 <= score_threshold <= 0.95:
            raise ValueError("score_threshold must be between 0.05 and 0.95.")
        self.labels = tuple(labels)
        for label in self.labels:
            label.validate()
        ids = [label.id for label in self.labels]
        if len(ids) != len(set(ids)):
            raise ValueError("Index label ids must be unique.")
        self.score_threshold = score_threshold
        self._label_by_id = {label.id: label for label in self.labels}
        self._idf: dict[str, float] = {}
        self._positive: dict[int, dict[str, float]] = {}
        self._negative: dict[int, dict[str, float]] = {}
        self.model_version = ""
        self.confirmed_document_count = 0
        self.seed_only = True

    def fit(self, documents: Iterable[TrainingDocument]) -> "LightweightContentClassifier":
        selected = list(documents)
        for document in selected:
            document.validate()
            unknown = (
                set(document.positive_label_ids) | set(document.negative_label_ids)
            ) - set(self._label_by_id)
            if unknown:
                raise ValueError("Training evidence refers to an unknown label.")

        seed_documents = [
            TrainingDocument(
                text=" ".join((label.name, *label.aliases)),
                positive_label_ids=(label.id,),
                weight=0.35,
                source="seed",
            )
            for label in self.labels
        ]
        all_documents = [*seed_documents, *selected]
        raw_vectors = [_features(item.text) for item in all_documents]
        document_frequency: Counter[str] = Counter()
        for vector in raw_vectors:
            document_frequency.update(vector.keys())
        count = max(1, len(raw_vectors))
        self._idf = {
            key: math.log((1 + count) / (1 + frequency)) + 1.0
            for key, frequency in document_frequency.items()
        }

        vectors: list[dict[str, float]] = []
        for raw in raw_vectors:
            weighted = {
                key: math.log1p(value) * self._idf.get(key, 1.0)
                for key, value in raw.items()
            }
            vectors.append(_normalize_vector(weighted))

        positive: dict[int, defaultdict[str, float]] = {
            label.id: defaultdict(float) for label in self.labels
        }
        negative: dict[int, defaultdict[str, float]] = {
            label.id: defaultdict(float) for label in self.labels
        }
        positive_weights: Counter[int] = Counter()
        negative_weights: Counter[int] = Counter()
        for document, vector in zip(all_documents, vectors):
            for label_id in document.positive_label_ids:
                positive_weights[label_id] += document.weight
                for key, value in vector.items():
                    positive[label_id][key] += value * document.weight
            for label_id in document.negative_label_ids:
                negative_weights[label_id] += document.weight
                for key, value in vector.items():
                    negative[label_id][key] += value * document.weight

        self._positive = {
            label_id: _normalize_vector(
                {
                    key: value / max(positive_weights[label_id], 1e-9)
                    for key, value in centroid.items()
                }
            )
            for label_id, centroid in positive.items()
        }
        self._negative = {
            label_id: _normalize_vector(
                {
                    key: value / max(negative_weights[label_id], 1e-9)
                    for key, value in centroid.items()
                }
            )
            for label_id, centroid in negative.items()
            if negative_weights[label_id] > 0
        }
        self.confirmed_document_count = sum(
            1 for item in selected if item.source != "seed"
        )
        self.seed_only = self.confirmed_document_count == 0
        fingerprint = {
            "algorithm": ALGORITHM_VERSION,
            "threshold": self.score_threshold,
            "labels": [
                {"id": item.id, "name": item.name, "aliases": item.aliases}
                for item in self.labels
            ],
            "documents": [
                {
                    "text_hash": hashlib.sha256(
                        PersianNormalizer.normalize(item.text).encode("utf-8")
                    ).hexdigest(),
                    "positive": item.positive_label_ids,
                    "negative": item.negative_label_ids,
                    "weight": item.weight,
                    "source": item.source,
                }
                for item in selected
            ],
        }
        self.model_version = hashlib.sha256(
            json.dumps(fingerprint, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:20]
        return self

    def predict(
        self,
        text: str,
        *,
        max_labels: int = 3,
        include_uncertain: bool = False,
    ) -> tuple[IndexPrediction, ...]:
        if not self.model_version:
            raise RuntimeError("Classifier must be fitted before prediction.")
        if not 1 <= max_labels <= 20:
            raise ValueError("max_labels must be between 1 and 20.")
        raw = _features(text)
        vector = _normalize_vector(
            {
                key: math.log1p(value) * self._idf.get(key, 1.0)
                for key, value in raw.items()
            }
        )
        normalized_text = PersianNormalizer.normalize(text)
        ranked: list[IndexPrediction] = []
        for label in self.labels:
            positive = self._positive.get(label.id, {})
            positive_score = _cosine(vector, positive)
            negative_score = _cosine(vector, self._negative.get(label.id, {}))
            score = max(0.0, positive_score - 0.45 * negative_score)
            phrases = tuple(
                item
                for item in (
                    PersianNormalizer.normalize(label.name),
                    *(PersianNormalizer.normalize(alias) for alias in label.aliases),
                )
                if item
            )
            if any(phrase in normalized_text for phrase in phrases):
                score = min(1.0, score + 0.20)
            accepted = score >= self.score_threshold
            if not accepted and not include_uncertain:
                continue
            contributions = sorted(
                (
                    (key, value * positive.get(key, 0.0))
                    for key, value in vector.items()
                    if key.startswith(("w:", "b:")) and positive.get(key, 0.0) > 0
                ),
                key=lambda item: item[1],
                reverse=True,
            )
            evidence = tuple(
                key.split(":", 1)[1] for key, _ in contributions[:4]
            )
            ranked.append(
                IndexPrediction(
                    label_id=label.id,
                    label_name=label.name,
                    score=round(min(score, 1.0), 6),
                    evidence=evidence,
                    accepted=accepted,
                )
            )
        ranked.sort(key=lambda item: (-item.score, item.label_id))
        return tuple(ranked[:max_labels])
