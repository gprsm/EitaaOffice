"""Run a deterministic synthetic Lab comparison for the local index."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eitaa_bridge.application.content_index import (  # noqa: E402
    IndexLabel,
    LightweightContentClassifier,
    PersianNormalizer,
    TrainingDocument,
)


def scores(expected: list[set[int]], predicted: list[set[int]]) -> dict[str, float]:
    true_positive = sum(len(left & right) for left, right in zip(expected, predicted))
    false_positive = sum(len(right - left) for left, right in zip(expected, predicted))
    false_negative = sum(len(left - right) for left, right in zip(expected, predicted))
    precision = true_positive / max(1, true_positive + false_positive)
    recall = true_positive / max(1, true_positive + false_negative)
    f1 = 2 * precision * recall / max(1e-12, precision + recall)
    exact = sum(left == right for left, right in zip(expected, predicted)) / max(1, len(expected))
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "exact_match": round(exact, 4),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
    }


def main() -> int:
    payload = json.loads((ROOT / "lab" / "content_index_synthetic.json").read_text(encoding="utf-8"))
    labels = tuple(
        IndexLabel(
            id=int(item["id"]),
            name=str(item["name"]),
            aliases=tuple(str(value) for value in item.get("aliases", [])),
        )
        for item in payload["labels"]
    )
    training = tuple(
        TrainingDocument(
            text=str(item["text"]),
            positive_label_ids=tuple(int(value) for value in item["labels"]),
        )
        for item in payload["train"]
    )
    expected = [set(int(value) for value in item["labels"]) for item in payload["test"]]

    phrase_predictions: list[set[int]] = []
    for item in payload["test"]:
        normalized = PersianNormalizer.normalize(str(item["text"]))
        found: set[int] = set()
        for label in labels:
            phrases = (label.name, *label.aliases)
            if any(PersianNormalizer.normalize(phrase) in normalized for phrase in phrases):
                found.add(label.id)
        phrase_predictions.append(found)

    started = time.perf_counter()
    model = LightweightContentClassifier(labels).fit(training)
    model_predictions: list[set[int]] = []
    cases: list[dict[str, object]] = []
    for item, wanted in zip(payload["test"], expected):
        predictions = model.predict(str(item["text"]))
        selected = {value.label_id for value in predictions}
        model_predictions.append(selected)
        cases.append(
            {
                "text": item["text"],
                "expected": sorted(wanted),
                "predicted": sorted(selected),
                "predictions": [value.safe_summary() for value in predictions],
                "correct": selected == wanted,
            }
        )
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    report = {
        "dataset_notice": payload["notice"],
        "algorithm": "persian-tfidf-centroid-v1",
        "model_version": model.model_version,
        "train_count": len(training),
        "test_count": len(expected),
        "elapsed_ms": elapsed_ms,
        "phrase_baseline": scores(expected, phrase_predictions),
        "model": scores(expected, model_predictions),
        "cases": cases,
        "limitations": [
            "Synthetic results do not estimate accuracy on real user data.",
            "Scores are similarities, not calibrated probabilities.",
            "Cold-start behavior is materially weaker than this trained Lab.",
        ],
    }
    output = ROOT / "lab" / "output"
    output.mkdir(parents=True, exist_ok=True)
    (output / "content_index_lab_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    failed = [item for item in cases if not item["correct"]]
    markdown = [
        "# Synthetic local content-index Lab report",
        "",
        f"- Training examples: {len(training)}",
        f"- Test examples: {len(expected)}",
        f"- Runtime: {elapsed_ms} ms",
        f"- Phrase baseline F1: {report['phrase_baseline']['f1']}",
        f"- Model F1: {report['model']['f1']}",
        f"- Model exact match: {report['model']['exact_match']}",
        f"- Incorrect exact cases: {len(failed)}",
        "",
        "This is a synthetic architecture test, not evidence of production accuracy.",
    ]
    (output / "CONTENT_INDEX_LAB_REPORT.md").write_text(
        "\n".join(markdown) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: report[key] for key in ("elapsed_ms", "phrase_baseline", "model")}, indent=2))
    return 0 if report["model"]["f1"] >= report["phrase_baseline"]["f1"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
