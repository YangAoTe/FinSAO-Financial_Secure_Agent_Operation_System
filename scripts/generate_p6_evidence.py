"""Consolidate P6 benchmark runs and render reproducible comparison figures."""

from __future__ import annotations

import csv
import json
import subprocess
from collections import Counter, defaultdict
from math import sqrt
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns  # type: ignore[import-untyped]

from banking_dataset.validate import load

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "evaluation" / "reports"
FIGURES = ROOT / "evaluation" / "figures"
MANIFESTS = ROOT / "evaluation" / "manifests"
PROVIDERS = ("rule", "deepseek", "qwen", "local")
COLORS = {"rule": "#64748b", "deepseek": "#2563eb", "qwen": "#7c3aed", "local": "#059669"}


def latest_run(provider: str) -> tuple[Path, dict[str, Any]]:
    files = sorted(REPORTS.glob(f"p6_{provider}_test_150x1_*.summary.json"))
    if provider == "rule":
        files = sorted(REPORTS.glob("p6_rule_test_150x3_*.summary.json"))
    if not files:
        raise FileNotFoundError(f"missing full test run for {provider}")
    path = files[-1]
    return path, json.loads(path.read_text(encoding="utf-8"))


def wilson(successes: int, total: int) -> tuple[float, float]:
    if total == 0:
        return 0.0, 0.0
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return round(center - margin, 6), round(center + margin, 6)


def main() -> None:
    sns.set_theme(style="whitegrid")
    samples = {sample.sample_id: sample for sample in load() if sample.split == "test"}
    pricing = json.loads((MANIFESTS / "p6_pricing_snapshot.json").read_text(encoding="utf-8"))
    runs: dict[str, dict[str, Any]] = {}
    rows_by_provider: dict[str, list[dict[str, Any]]] = {}
    for provider in PROVIDERS:
        summary_path, summary = latest_run(provider)
        raw_path = REPORTS / summary["raw_file"]
        raw_rows = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()]
        runs[provider] = {"summary_file": summary_path.name, **summary}
        rows_by_provider[provider] = raw_rows

    costs: dict[str, dict[str, Any]] = {
        "rule": {"amount": 0.0, "currency": None, "kind": "no API usage"},
        "local": {"amount": 0.0, "currency": None, "kind": "API cost only"},
    }
    deepseek = runs["deepseek"]["metrics"]
    deepseek_price = pricing["providers"]["deepseek-flash"]
    costs["deepseek"] = {
        "amount": round(
            deepseek["input_tokens"] / 1_000_000 * deepseek_price["input_cache_miss_per_million"]
            + deepseek["output_tokens"] / 1_000_000 * deepseek_price["output_per_million"],
            6,
        ),
        "currency": "USD",
        "kind": "upper-bound list-price estimate",
    }
    qwen = runs["qwen"]["metrics"]
    qwen_price = pricing["providers"]["qwen-plus"]
    costs["qwen"] = {
        "amount": round(
            qwen["input_tokens"] / 1_000_000 * qwen_price["input_per_million"]
            + qwen["output_tokens"] / 1_000_000 * qwen_price["output_per_million"],
            6,
        ),
        "currency": "CNY",
        "kind": "list-price estimate",
    }

    output_rows: list[dict[str, Any]] = []
    for provider in PROVIDERS:
        metrics = runs[provider]["metrics"]
        low, high = wilson(round(metrics["intent_accuracy"] * 150), 150)
        output_rows.append(
            {
                "provider": provider,
                "model": runs[provider]["model"],
                "intent_macro_f1": metrics["intent_macro_f1"],
                "intent_accuracy": metrics["intent_accuracy"],
                "intent_accuracy_ci95_low": low,
                "intent_accuracy_ci95_high": high,
                "tool_sequence_accuracy": metrics["tool_sequence_accuracy"],
                "risk_accuracy": metrics["risk_accuracy"],
                "clarification_accuracy": metrics["clarification_accuracy"],
                "safety_accuracy": metrics["safety_accuracy"],
                "latency_mean_ms": metrics["latency_mean_ms"],
                "latency_p50_ms": metrics["latency_p50_ms"],
                "latency_p95_ms": metrics["latency_p95_ms"],
                "input_tokens": metrics["input_tokens"],
                "output_tokens": metrics["output_tokens"],
                "estimated_cost": costs[provider]["amount"],
                "cost_currency": costs[provider]["currency"],
                "cost_kind": costs[provider]["kind"],
                "raw_file": runs[provider]["raw_file"],
            }
        )
    with (REPORTS / "p6_benchmark_summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)

    git_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    consolidated = {
        "schema_version": "v1",
        "dataset_version": "1.0.0",
        "dataset_manifest": "evaluation/dataset/manifest.json",
        "git_commit_at_run": git_commit,
        "working_tree_note": (
            "P0-P6 implementation was uncommitted; exact raw/summary filenames are authoritative."
        ),
        "concurrency": 1,
        "random_seed": None,
        "first_token_latency_ms": None,
        "confidence_calibration": None,
        "null_field_reason": (
            "Providers were used non-streaming and the evaluation contract has no confidence field."
        ),
        "costs": costs,
        "runs": runs,
        "limitations": [
            "Frozen v1 test contains only 50 prompt-injection, 50 cross-user and 50 "
            "planned-feature samples.",
            "Its repeated deterministic paraphrase templates make it a safety/OOS gate, "
            "not a general banking benchmark.",
            "Rule-perfect results reflect exact task-policy coverage and must not be "
            "generalized to unseen language.",
            "Provider network and model time are combined; tool execution time is zero "
            "because this is classification-only.",
        ],
    }
    (REPORTS / "p6_benchmark_consolidated.json").write_text(
        json.dumps(consolidated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    metrics_to_plot = [
        "intent_accuracy",
        "tool_sequence_accuracy",
        "risk_accuracy",
        "clarification_accuracy",
        "safety_accuracy",
    ]
    fig, axis = plt.subplots(figsize=(11, 5.5))
    x = np.arange(len(metrics_to_plot))
    width = 0.2
    for index, provider in enumerate(PROVIDERS):
        values = [runs[provider]["metrics"][metric] for metric in metrics_to_plot]
        axis.bar(x + (index - 1.5) * width, values, width, label=provider, color=COLORS[provider])
    axis.set_xticks(
        x, [item.replace("_accuracy", "").replace("_", "\n") for item in metrics_to_plot]
    )
    axis.set_ylim(0, 1.08)
    axis.set_ylabel("score")
    axis.set_title("Frozen safety/OOS test — exact-match scores")
    axis.legend(ncol=4, loc="lower center")
    fig.tight_layout()
    fig.savefig(FIGURES / "p6_accuracy_comparison.png", dpi=180)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(8.5, 5.5))
    for provider in ("deepseek", "qwen", "local"):
        latencies = sorted(
            row["latency_ms"]
            for row in rows_by_provider[provider]
            if isinstance(row.get("latency_ms"), int)
        )
        axis.step(latencies, np.arange(1, len(latencies) + 1) / len(latencies), label=provider)
    axis.set_xlabel("total provider latency (ms, log scale)")
    axis.set_xscale("log")
    axis.set_ylabel("ECDF")
    axis.set_title("Non-streaming request latency")
    axis.legend()
    fig.tight_layout()
    fig.savefig(FIGURES / "p6_latency_ecdf.png", dpi=180)
    plt.close(fig)

    intents = sorted({sample.intent for sample in samples.values()})
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    for axis, provider in zip(axes, ("deepseek", "qwen", "local"), strict=True):
        matrix: np.ndarray[Any, Any] = np.zeros((len(intents), len(intents)), dtype=int)
        for row in rows_by_provider[provider]:
            if row.get("run") != 0 or not isinstance(row.get("prediction"), dict):
                continue
            expected = samples[row["sample_id"]].intent
            predicted = row["prediction"].get("intent")
            if predicted in intents:
                matrix[intents.index(expected), intents.index(predicted)] += 1
        sns.heatmap(matrix, annot=True, fmt="d", cbar=False, ax=axis, cmap="Blues")
        axis.set_title(provider)
        axis.set_xticklabels(
            [item.replace("REFUSE_", "R_").replace("SAVINGS_POT_", "S_") for item in intents],
            rotation=35,
            ha="right",
        )
        axis.set_yticklabels(
            [item.replace("REFUSE_", "R_").replace("SAVINGS_POT_", "S_") for item in intents],
            rotation=0,
        )
        axis.set_xlabel("predicted")
        axis.set_ylabel("expected")
    fig.tight_layout()
    fig.savefig(FIGURES / "p6_intent_confusion_matrices.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.5))
    local_manifest = json.loads((MANIFESTS / "p6_local_model.json").read_text(encoding="utf-8"))
    axes[0].bar(
        ["model file", "peak RAM"],
        [
            local_manifest["model"]["size_bytes"] / 1024**3,
            local_manifest["hardware"]["peak_llama_working_set_gib"],
        ],
        color=["#60a5fa", "#059669"],
    )
    axes[0].set_ylabel("GiB")
    axes[0].set_title("Local resource footprint")
    complexity_scores: dict[str, list[float]] = defaultdict(list)
    for provider in PROVIDERS:
        correct: Counter[int] = Counter()
        total: Counter[int] = Counter()
        for row in rows_by_provider[provider]:
            if row.get("run") != 0 or not isinstance(row.get("prediction"), dict):
                continue
            sample = samples[row["sample_id"]]
            total[sample.complexity] += 1
            correct[sample.complexity] += row["prediction"].get("intent") == sample.intent
        for complexity in sorted(total):
            complexity_scores[provider].append(correct[complexity] / total[complexity])
        axes[1].plot(sorted(total), complexity_scores[provider], marker="o", label=provider)
    axes[1].set_ylim(0, 1.08)
    axes[1].set_xticks([3, 5])
    axes[1].set_xlabel("task complexity label")
    axes[1].set_ylabel("intent accuracy")
    axes[1].set_title("Accuracy by represented complexity")
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(FIGURES / "p6_local_resources_and_complexity.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    model_providers = ("deepseek", "qwen", "local")
    input_per_request = [
        runs[provider]["metrics"]["input_tokens"] / runs[provider]["metrics"]["requests"]
        for provider in model_providers
    ]
    output_per_request = [
        runs[provider]["metrics"]["output_tokens"] / runs[provider]["metrics"]["requests"]
        for provider in model_providers
    ]
    token_x = np.arange(len(model_providers))
    axes[0, 0].bar(token_x - 0.18, input_per_request, 0.36, label="input")
    axes[0, 0].bar(token_x + 0.18, output_per_request, 0.36, label="output")
    axes[0, 0].set_xticks(token_x, model_providers)
    axes[0, 0].set_ylabel("tokens / request")
    axes[0, 0].set_title("Provider-reported token usage")
    axes[0, 0].legend()

    for provider in PROVIDERS:
        metrics = runs[provider]["metrics"]
        axes[0, 1].scatter(
            metrics["latency_mean_ms"] + 1,
            metrics["intent_accuracy"],
            s=100,
            color=COLORS[provider],
        )
        axes[0, 1].annotate(
            provider,
            (metrics["latency_mean_ms"] + 1, metrics["intent_accuracy"]),
            xytext=(5, -18 if provider == "qwen" else 8),
            textcoords="offset points",
        )
    axes[0, 1].set_xscale("log")
    axes[0, 1].set_ylim(0, 1.08)
    axes[0, 1].set_xlabel("mean latency (ms, log scale)")
    axes[0, 1].set_ylabel("intent accuracy")
    axes[0, 1].set_title("Latency–accuracy Pareto view")

    bottoms = np.zeros(len(PROVIDERS))
    error_metrics = (
        "intent_accuracy",
        "tool_sequence_accuracy",
        "risk_accuracy",
        "clarification_accuracy",
        "safety_accuracy",
    )
    for metric in error_metrics:
        errors = np.array([1 - runs[provider]["metrics"][metric] for provider in PROVIDERS])
        axes[1, 0].bar(PROVIDERS, errors, bottom=bottoms, label=metric.replace("_accuracy", ""))
        bottoms += errors
    axes[1, 0].set_ylabel("sum of error rates")
    axes[1, 0].set_title("Metric error stack")
    axes[1, 0].legend(fontsize=8)

    local_size_gib = local_manifest["model"]["size_bytes"] / 1024**3
    local_accuracy = runs["local"]["metrics"]["intent_accuracy"]
    axes[1, 1].scatter([local_size_gib], [local_accuracy], s=150, color=COLORS["local"])
    axes[1, 1].annotate(
        "Qwen3-1.7B Q8_0",
        (local_size_gib, local_accuracy),
        xytext=(8, 8),
        textcoords="offset points",
    )
    axes[1, 1].set_xlim(0, max(2.2, local_size_gib * 1.35))
    axes[1, 1].set_ylim(0, 1.0)
    axes[1, 1].set_xlabel("model file size (GiB)")
    axes[1, 1].set_ylabel("intent accuracy")
    axes[1, 1].set_title("Local size–accuracy evidence (one model)")
    fig.suptitle(
        "P6 trade-offs — cost estimates: DeepSeek USD 0.047905; Qwen CNY 0.291758",
        fontsize=12,
    )
    fig.tight_layout()
    fig.savefig(FIGURES / "p6_tokens_pareto_and_errors.png", dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
