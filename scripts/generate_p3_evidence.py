"""Export persisted P3 task/event evidence and generate descriptive figures."""

from __future__ import annotations

import csv
import json
from collections import Counter
from importlib import import_module
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from agent.config import AgentSettings
from agent_persistence.models import AgentEventModel, AgentTaskModel

ROOT = Path(__file__).resolve().parents[1]
plt: Any = import_module("matplotlib.pyplot")
pd: Any = import_module("pandas")
sns: Any = import_module("seaborn")


def main() -> None:
    reports = ROOT / "evaluation" / "reports"
    figures = ROOT / "evaluation" / "figures"
    reports.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    engine = create_engine(AgentSettings().agent_database_url)
    with Session(engine) as session:
        tasks = list(session.scalars(select(AgentTaskModel).order_by(AgentTaskModel.created_at)))
        events = list(session.scalars(select(AgentEventModel).order_by(AgentEventModel.created_at)))
    task_rows = [
        {
            "task_id": str(task.id),
            "status": task.status,
            "duration_ms": round((task.updated_at - task.created_at).total_seconds() * 1000, 3),
            "version": task.version,
            "error_code": task.error_code or "",
            "recovery_action": task.recovery_action or "",
        }
        for task in tasks
    ]
    event_rows = [
        {
            "task_id": str(event.task_id),
            "sequence": event.sequence,
            "event_type": event.event_type,
            "created_at": event.created_at.isoformat(),
        }
        for event in events
    ]
    for path, rows in (
        (reports / "p3_tasks.csv", task_rows),
        (reports / "p3_events.csv", event_rows),
    ):
        if rows:
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
    summary = {
        "task_count": len(task_rows),
        "task_status": dict(Counter(row["status"] for row in task_rows)),
        "event_count": len(event_rows),
        "event_types": dict(Counter(row["event_type"] for row in event_rows)),
        "scope": "local persisted P3 demonstration runs; not a benchmark",
    }
    (reports / "p3_durable_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if task_rows:
        frame = pd.DataFrame(task_rows)
        plt.figure(figsize=(7, 4))
        sns.countplot(data=frame, x="status", hue="status", legend=False)
        plt.title(f"Persisted demonstration task outcomes (n={len(task_rows)})")
        plt.tight_layout()
        plt.savefig(figures / "p3_task_outcomes.png", dpi=180)
        plt.close()
    if event_rows:
        event_frame = pd.DataFrame(event_rows)
        plt.figure(figsize=(8, 4))
        sns.countplot(data=event_frame, y="event_type", color="#4c72b0")
        plt.title(f"Persisted task events (n={len(event_rows)})")
        plt.tight_layout()
        plt.savefig(figures / "p3_event_types.png", dpi=180)
        plt.close()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
