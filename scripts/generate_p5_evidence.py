"""Generate reproducible P5 distribution tables and figures."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import seaborn as sns  # type: ignore[import-untyped]

from banking_dataset.validate import load

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    rows = load()
    reports = ROOT / "evaluation" / "reports"
    figures = ROOT / "evaluation" / "figures"
    dimensions: dict[str, Counter[str]] = {
        "scenario": Counter(row.scenario for row in rows),
        "risk": Counter(row.expected_risk_tier for row in rows),
        "split": Counter(row.split for row in rows),
        "complexity": Counter(str(row.complexity) for row in rows),
        "review": Counter(row.review_status for row in rows),
    }
    with (reports / "p5_distributions.csv").open("w", encoding="utf-8", newline="") as handle:
        distribution_writer = csv.writer(handle)
        distribution_writer.writerow(["dimension", "value", "count"])
        for dimension, values in dimensions.items():
            for value, count in sorted(values.items()):
                distribution_writer.writerow([dimension, value, count])
    review_path = reports / "p5_manual_seed_review.csv"
    existing_reviews: dict[str, tuple[str, str]] = {}
    if review_path.exists():
        with review_path.open(encoding="utf-8-sig", newline="") as handle:
            for review in csv.DictReader(handle):
                existing_reviews[review["sample_id"]] = (
                    review.get("review_decision", ""),
                    review.get("review_notes", ""),
                )
    with review_path.open("w", encoding="utf-8-sig", newline="") as handle:
        fieldnames = [
            "sample_id",
            "split",
            "conversation",
            "intent",
            "risk",
            "tools",
            "safety_expectation",
            "review_decision",
            "review_notes",
        ]
        review_writer = csv.DictWriter(handle, fieldnames=fieldnames)
        review_writer.writeheader()
        for row in rows:
            if row.source != "manual_seed":
                continue
            review_decision, review_notes = existing_reviews.get(row.sample_id, ("", ""))
            review_writer.writerow(
                {
                    "sample_id": row.sample_id,
                    "split": row.split,
                    "conversation": " | ".join(item.content for item in row.conversation),
                    "intent": row.intent,
                    "risk": row.expected_risk_tier,
                    "tools": " -> ".join(call.tool_name for call in row.expected_tool_calls),
                    "safety_expectation": row.safety_expectation,
                    "review_decision": review_decision,
                    "review_notes": review_notes,
                }
            )
    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    for axis, dimension in zip(axes, ("scenario", "risk", "split"), strict=True):
        values = dimensions[dimension]
        sns.barplot(x=list(values.keys()), y=list(values.values()), ax=axis, color="#4f8f70")
        axis.set_title(dimension.title())
        axis.tick_params(axis="x", rotation=45)
        axis.set_ylabel("samples")
    fig.tight_layout()
    fig.savefig(figures / "p5_dataset_distributions.png", dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    main()
