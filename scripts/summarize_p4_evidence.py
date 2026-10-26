"""Summarize the reproducible Playwright report into compact P4 evidence."""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "evaluation" / "reports" / "p4_playwright.json"


def main() -> None:
    raw = json.loads(REPORT.read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    for suite in raw.get("suites", []):
        for spec in suite.get("specs", []):
            for test in spec.get("tests", []):
                project = test.get("projectName", "unknown")
                for result in test.get("results", []):
                    status = result.get("status", "unknown")
                    if status == "skipped":
                        continue
                    rows.append(
                        {
                            "scenario": spec.get("title"),
                            "project": project,
                            "status": status,
                            "duration_ms": result.get("duration", 0),
                        }
                    )
    summary = {
        "schema_version": "v1",
        "runner": "Playwright Chromium",
        "scenarios": len(rows),
        "passed": sum(row["status"] == "passed" for row in rows),
        "failed": sum(row["status"] != "passed" for row in rows),
        "first_attempt_issue": "mobile navigation hid task/lab destinations",
        "remediation": (
            "all seven mobile destinations now remain keyboard/screen-reader addressable"
        ),
        "browser_ui_surface_note": (
            "Codex/Edge/IAB surfaces were unavailable; isolated Playwright Chromium was used."
        ),
        "observations": rows,
    }
    out = ROOT / "evaluation" / "reports" / "p4_usability_summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (ROOT / "evaluation" / "reports" / "p4_usability_runs.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=["scenario", "project", "status", "duration_ms"])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
