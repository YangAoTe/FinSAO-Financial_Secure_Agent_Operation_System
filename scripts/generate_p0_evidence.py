"""Generate reproducible P0 contract snapshots, raw summaries, and figures."""

from __future__ import annotations

import csv
import json
import platform
import sys
from collections import Counter, defaultdict
from importlib import import_module
from pathlib import Path
from typing import Any
from unittest.mock import Mock
from xml.etree import ElementTree

from agent_tools.registry import ToolRegistry
from agent_tools.tools import register_default_tools
from banking_core.app.main import app

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "evaluation" / "reports"
FIGURES = ROOT / "evaluation" / "figures"
plt: Any = import_module("matplotlib.pyplot")
pd: Any = import_module("pandas")
sns: Any = import_module("seaborn")


def _domain_for_path(path: str) -> str:
    first = path.strip("/").split("/", 1)[0] or "root"
    return {
        "analytics": "analytics",
        "transactions": "analytics",
        "budgets": "budgets",
        "subscriptions": "subscriptions",
        "security": "security",
        "wealth": "wealth",
    }.get(first, first)


def _load_pytest(xml_path: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, float]]]:
    root = ElementTree.parse(xml_path).getroot()
    cases: list[dict[str, Any]] = []
    modules: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0, "seconds": 0.0})
    for case in root.iter("testcase"):
        classname = case.attrib.get("classname", "unknown")
        module = classname.rsplit(".", 1)[-1]
        status = "passed"
        if case.find("failure") is not None:
            status = "failed"
        elif case.find("error") is not None:
            status = "error"
        elif case.find("skipped") is not None:
            status = "skipped"
        seconds = float(case.attrib.get("time", "0"))
        cases.append(
            {
                "module": module,
                "name": case.attrib.get("name", "unknown"),
                "status": status,
                "seconds": seconds,
            }
        )
        modules[module]["count"] += 1
        modules[module]["seconds"] += seconds
    return cases, dict(modules)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    pytest_xml = REPORTS / "p0_pytest.xml"
    if not pytest_xml.exists():
        raise SystemExit(f"missing {pytest_xml}; run pytest with --junitxml first")

    openapi = app.openapi()
    operations: list[dict[str, str]] = []
    methods = {"get", "post", "put", "patch", "delete"}
    for path, path_item in openapi["paths"].items():
        for method, operation in path_item.items():
            if method not in methods:
                continue
            operations.append(
                {
                    "domain": _domain_for_path(path),
                    "method": method.upper(),
                    "path": path,
                    "operation_id": operation.get("operationId", ""),
                }
            )

    registry = ToolRegistry()
    register_default_tools(registry, Mock())
    tools = registry.list_allowed()
    tool_rows = [
        {
            "domain": str(tool["action"]).split(".", 1)[0],
            "name": str(tool["name"]),
            "action": str(tool["action"]),
            "risk_policy": str(tool["risk_policy"]),
        }
        for tool in tools
    ]
    cases, modules = _load_pytest(pytest_xml)

    (REPORTS / "p0_openapi.json").write_text(
        json.dumps(openapi, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (REPORTS / "p0_tool_schemas.json").write_text(
        json.dumps(tools, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _write_csv(REPORTS / "p0_tests.csv", cases)
    _write_csv(REPORTS / "p0_api_operations.csv", operations)
    _write_csv(REPORTS / "p0_tools.csv", tool_rows)

    status_counts = Counter(case["status"] for case in cases)
    api_domains = Counter(row["domain"] for row in operations)
    tool_domains = Counter(row["domain"] for row in tool_rows)
    risk_counts = Counter(row["risk_policy"] for row in tool_rows)
    summary = {
        "runtime": {"python": sys.version.split()[0], "platform": platform.platform()},
        "tests": {
            "total": len(cases),
            "status": dict(sorted(status_counts.items())),
            "seconds": round(sum(case["seconds"] for case in cases), 6),
            "by_module": modules,
        },
        "openapi": {
            "paths": len(openapi["paths"]),
            "operations": len(operations),
            "schemas": len(openapi["components"]["schemas"]),
            "by_domain": dict(sorted(api_domains.items())),
        },
        "tools": {
            "total": len(tools),
            "by_domain": dict(sorted(tool_domains.items())),
            "by_risk_policy": dict(sorted(risk_counts.items())),
        },
    }
    (REPORTS / "p0_baseline.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    sns.set_theme(style="whitegrid")
    module_rows = [
        {"module": name, "metric": "test count", "value": values["count"]}
        for name, values in modules.items()
    ]
    plt.figure(figsize=(10, 5))
    sns.barplot(
        data=pd.DataFrame(module_rows),
        x="value",
        y="module",
        hue="metric",
        legend=False,
    )
    plt.xlabel("Collected test cases")
    plt.ylabel("Test module")
    plt.tight_layout()
    plt.savefig(FIGURES / "p0_test_counts_by_module.png", dpi=180)
    plt.close()

    api_rows = [{"domain": key, "count": value} for key, value in api_domains.items()]
    plt.figure(figsize=(10, 5))
    sns.barplot(data=pd.DataFrame(api_rows), x="count", y="domain", color="#4c72b0")
    plt.xlabel("OpenAPI operations")
    plt.ylabel("Business domain")
    plt.tight_layout()
    plt.savefig(FIGURES / "p0_api_operations_by_domain.png", dpi=180)
    plt.close()

    risk_rows = [{"risk": key, "count": value} for key, value in risk_counts.items()]
    plt.figure(figsize=(7, 4))
    sns.barplot(
        data=pd.DataFrame(risk_rows),
        x="risk",
        y="count",
        hue="risk",
        palette={
            "GREEN": "#55a868",
            "YELLOW": "#ddaa33",
            "RED": "#c44e52",
            "YELLOW_OR_RED": "#8172b2",
        },
        legend=False,
    )
    plt.xlabel("Declared tool risk policy")
    plt.ylabel("Tool count")
    plt.tight_layout()
    plt.savefig(FIGURES / "p0_tool_risk_coverage.png", dpi=180)
    plt.close()

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
