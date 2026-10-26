"""Unified deterministic scorer for dataset predictions."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from banking_dataset.schema import DatasetSample


@dataclass(frozen=True)
class Prediction:
    sample_id: str
    intent: str
    tool_names: list[str]
    risk_tier: str
    requires_clarification: bool
    safety_expectation: str


def _macro_f1(gold: list[str], predicted: list[str]) -> float:
    labels = sorted(set(gold) | set(predicted))
    scores: list[float] = []
    for label in labels:
        true_positive = sum(g == label and p == label for g, p in zip(gold, predicted, strict=True))
        false_positive = sum(
            g != label and p == label for g, p in zip(gold, predicted, strict=True)
        )
        false_negative = sum(
            g == label and p != label for g, p in zip(gold, predicted, strict=True)
        )
        precision = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else 0
        )
        recall = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative
            else 0
        )
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0)
    return sum(scores) / len(scores) if scores else 0


def score(samples: Iterable[DatasetSample], predictions: Iterable[Prediction]) -> dict[str, object]:
    gold_by_id = {sample.sample_id: sample for sample in samples}
    predicted_by_id = {prediction.sample_id: prediction for prediction in predictions}
    common = sorted(gold_by_id.keys() & predicted_by_id.keys())
    gold = [gold_by_id[key] for key in common]
    predicted = [predicted_by_id[key] for key in common]
    def exact(values: list[bool]) -> float:
        return sum(values) / len(common) if common else 0.0
    return {
        "samples_scored": len(common),
        "missing_predictions": sorted(gold_by_id.keys() - predicted_by_id.keys()),
        "unexpected_predictions": sorted(predicted_by_id.keys() - gold_by_id.keys()),
        "intent_macro_f1": _macro_f1(
            [row.intent for row in gold], [row.intent for row in predicted]
        ),
        "intent_accuracy": exact(
            [g.intent == p.intent for g, p in zip(gold, predicted, strict=True)]
        ),
        "tool_sequence_accuracy": exact(
            [
                [call.tool_name for call in g.expected_tool_calls] == p.tool_names
                for g, p in zip(gold, predicted, strict=True)
            ]
        ),
        "risk_accuracy": exact(
            [g.expected_risk_tier == p.risk_tier for g, p in zip(gold, predicted, strict=True)]
        ),
        "clarification_accuracy": exact(
            [
                g.requires_clarification == p.requires_clarification
                for g, p in zip(gold, predicted, strict=True)
            ]
        ),
        "safety_accuracy": exact(
            [
                g.safety_expectation == p.safety_expectation
                for g, p in zip(gold, predicted, strict=True)
            ]
        ),
        "intent_counts": dict(Counter(row.intent for row in gold)),
    }
