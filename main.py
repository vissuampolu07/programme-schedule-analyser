"""
Programme Schedule Analyser — entry point.

Usage:
    python main.py [--schedule programme_schedule.csv]
                    [--start 2026-06-01] [--today 2026-07-27]
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from cpm import load_schedule, run_cpm, critical_path, to_dataframe
from dashboard import build_status_table, plot_gantt, plot_rag_summary, plot_milestones

ROOT = Path(__file__).resolve().parent

def main() -> None:
    parser = argparse.ArgumentParser(description="Programme Schedule Analyser")
    parser.add_argument("--schedule", default=str(ROOT / "programme_schedule.csv"))
    parser.add_argument("--start", default="2026-06-01", help="Programme start date")
    parser.add_argument("--today", default="2026-07-27", help="Reporting date")
    args = parser.parse_args()

    start = date.fromisoformat(args.start)
    today = date.fromisoformat(args.today)
    out = ROOT

    # 1. Schedule the network
    tasks = load_schedule(args.schedule)
    tasks, duration = run_cpm(tasks)

    # 2. Console report
    print(f"Programme duration: {duration} working days "
          f"({start} → finish day offset {duration})")
    print("\nCritical path:")
    for t in critical_path(tasks):
        print(f"  {t.task_id} {t.name} ({t.duration}d)")

    # 3. Schedule table
    df = to_dataframe(tasks, start)
    df.to_csv(out / "schedule_analysis.csv", index=False)
    print(f"\nSchedule table -> {out / 'schedule_analysis.csv'}")

    # 4. RAG status
    status = build_status_table(tasks, start, today)
    status.to_csv(out / "rag_status.csv", index=False)
    reds = status[status["RAG"] == "Red"]
    if not reds.empty:
        print("\nRED items requiring escalation:")
        for _, r in reds.iterrows():
            print(f"  {r['Task ID']} {r['Task']} ({r['% Complete']:.0f}% complete)")

    # 5. Dashboard visuals
    plot_gantt(tasks, start, today, str(out / "gantt_critical_path.png"))
    plot_rag_summary(status, str(out / "rag_by_workstream.png"))
    plot_milestones(tasks, start, today, str(out / "milestone_tracker.png"))
    print(f"Dashboards         -> {out}/")


if __name__ == "__main__":
    main()
