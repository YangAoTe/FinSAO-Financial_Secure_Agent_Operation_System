"""Validate dataset rows, tool alignment, duplicates and split leakage."""

from __future__ import annotations

import hashlib
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from banking_dataset.schema import DatasetSample

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evaluation" / "dataset"


def normalized_text(sample: DatasetSample) -> str:
    text = " ".join(message.content for message in sample.conversation)
    return re.sub(r"[^\w]+", "", text.casefold())


def load() -> list[DatasetSample]:
    rows: list[DatasetSample] = []
    for split in ("train", "dev", "test"):
        path = DATA / f"banking_agent_v1_{split}.jsonl"
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            sample = DatasetSample.model_validate_json(line)
            if sample.split != split:
                raise ValueError(f"{path.name}:{line_number}: split mismatch")
            rows.append(sample)
    return rows


def validate() -> dict[str, object]:
    rows = load()
    ids = [row.sample_id for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate sample_id")
    cluster_splits: dict[str, set[str]] = {}
    text_splits: dict[str, set[str]] = {}
    for row in rows:
        cluster_splits.setdefault(row.cluster_id, set()).add(row.split)
        digest = hashlib.sha256(normalized_text(row).encode()).hexdigest()
        text_splits.setdefault(digest, set()).add(row.split)
    leaked_clusters = [key for key, value in cluster_splits.items() if len(value) > 1]
    exact_leaks = [key for key, value in text_splits.items() if len(value) > 1]
    if leaked_clusters or exact_leaks:
        raise ValueError(f"split leakage: clusters={leaked_clusters}, exact={exact_leaks}")

    tool_snapshot = json.loads(
        (ROOT / "evaluation" / "reports" / "p0_tool_schemas.json").read_text(encoding="utf-8")
    )
    known_tools = {item["name"] for item in tool_snapshot}
    unknown_tools = sorted(
        {
            call.tool_name
            for row in rows
            for call in row.expected_tool_calls
            if call.tool_name not in known_tools
        }
    )
    if unknown_tools:
        raise ValueError(f"unknown tools: {unknown_tools}")

    by_split = {
        split: [normalized_text(row) for row in rows if row.split == split]
        for split in ("train", "dev", "test")
    }
    max_ratio = 0.0
    max_pair = ["", ""]
    for left_split, right_split in (("train", "dev"), ("train", "test"), ("dev", "test")):
        for left in by_split[left_split]:
            for right in by_split[right_split]:
                ratio = SequenceMatcher(None, left, right).ratio()
                if ratio > max_ratio:
                    max_ratio, max_pair = ratio, [left, right]
    return {
        "schema_version": "v1",
        "valid_rows": len(rows),
        "split_counts": {split: len(by_split[split]) for split in by_split},
        "unique_clusters": len(cluster_splits),
        "exact_cross_split_leaks": 0,
        "maximum_cross_split_fuzzy_ratio": round(max_ratio, 4),
        "maximum_fuzzy_pair": max_pair,
        "tool_schema_alignment": True,
        "second_human_review_complete": (
            sum(row.source == "manual_seed" and row.review_status == "reviewed" for row in rows)
            == 100
        ),
    }


def main() -> None:
    report = validate()
    target = ROOT / "evaluation" / "reports" / "p5_validation.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
