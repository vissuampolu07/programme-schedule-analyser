"""
RAG status assessment and PMO dashboard generation.

Produces:
  1. A Gantt chart with the critical path highlighted
  2. A RAG status summary by workstream
  3. A milestone tracker
All charts are saved to the output/ directory as PNG files.
"""

from __future__ import annotations

from datetime import date, timedelta

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

from cpm import Task

RAG_COLOURS = {"Red": "#C00000", "Amber": "#E8A33D", "Green": "#2E7D32"}
CRITICAL_COLOUR = "#C00000"
NORMAL_COLOUR = "#3B6EA5"
DONE_COLOUR = "#9E9E9E"


def assess_rag(task: Task, today_offset: int) -> str:
    """
    Simple, transparent RAG logic based on schedule performance:

    - Green: complete, or progress is at/ahead of where the schedule expects
    - Amber: behind expected progress but has float to absorb the slip
    - Red:   behind expected progress on a critical-path task (no float)
    """
    if task.percent_complete >= 100:
        return "Green"

    if today_offset <= task.early_start:
        return "Green"  # not yet due to start

    elapsed = min(today_offset, task.early_finish) - task.early_start
    expected = 100 * elapsed / task.duration if task.duration else 100.0

    if task.percent_complete >= expected - 5:  # 5% tolerance band
        return "Green"
    return "Red" if task.is_critical else "Amber"


def build_status_table(
    tasks: dict[str, Task], start_date: date, today: date
) -> pd.DataFrame:
    today_offset = (today - start_date).days
    rows = []
    for t in tasks.values():
        rows.append(
            {
                "Task ID": t.task_id,
                "Task": t.name,
                "Workstream": t.workstream,
                "RAG": assess_rag(t, today_offset),
                "Critical": t.is_critical,
                "% Complete": t.percent_complete,
            }
        )
    return pd.DataFrame(rows)


def plot_gantt(
    tasks: dict[str, Task], start_date: date, today: date, path: str
) -> None:
    ordered = sorted(tasks.values(), key=lambda t: t.early_start, reverse=True)
    fig, ax = plt.subplots(figsize=(12, 8))

    for i, t in enumerate(ordered):
        begin = start_date + timedelta(days=t.early_start)
        if t.is_milestone:
            ax.plot(
                mdates.date2num(begin), i, marker="D", markersize=10,
                color="#1A1A1A", zorder=3,
            )
            continue
        if t.percent_complete >= 100:
            colour = DONE_COLOUR
        elif t.is_critical:
            colour = CRITICAL_COLOUR
        else:
            colour = NORMAL_COLOUR
        ax.barh(i, t.duration, left=mdates.date2num(begin), height=0.55,
                color=colour, edgecolor="white", zorder=2)
        # progress overlay
        done_days = t.duration * t.percent_complete / 100
        if 0 < done_days < t.duration:
            ax.barh(i, done_days, left=mdates.date2num(begin), height=0.55,
                    color="#1A1A1A", alpha=0.35, zorder=2)

    ax.axvline(mdates.date2num(today), color="#1A1A1A", linestyle="--",
               linewidth=1.2, label="Today")
    ax.set_yticks(range(len(ordered)))
    ax.set_yticklabels([f"{t.task_id}  {t.name}" for t in ordered], fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
    ax.set_title("Programme Schedule — Critical Path Highlighted", fontsize=13,
                 fontweight="bold")

    handles = [
        plt.Rectangle((0, 0), 1, 1, color=CRITICAL_COLOUR, label="Critical path"),
        plt.Rectangle((0, 0), 1, 1, color=NORMAL_COLOUR, label="Non-critical"),
        plt.Rectangle((0, 0), 1, 1, color=DONE_COLOUR, label="Complete"),
        plt.Line2D([0], [0], marker="D", color="w", markerfacecolor="#1A1A1A",
                   markersize=9, label="Milestone"),
        plt.Line2D([0], [0], color="#1A1A1A", linestyle="--", label="Today"),
    ]
    ax.legend(handles=handles, loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_rag_summary(status: pd.DataFrame, path: str) -> None:
    pivot = (
        status.groupby(["Workstream", "RAG"]).size().unstack(fill_value=0)
        .reindex(columns=["Green", "Amber", "Red"], fill_value=0)
    )
    fig, ax = plt.subplots(figsize=(9, 5))
    pivot.plot(kind="barh", stacked=True, ax=ax,
               color=[RAG_COLOURS[c] for c in pivot.columns])
    ax.set_title("RAG Status by Workstream", fontsize=13, fontweight="bold")
    ax.set_xlabel("Number of tasks")
    ax.legend(title="RAG")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_milestones(
    tasks: dict[str, Task], start_date: date, today: date, path: str
) -> None:
    milestones = [t for t in tasks.values() if t.is_milestone]
    milestones.sort(key=lambda t: t.early_start)
    fig, ax = plt.subplots(figsize=(9, 3.2))
    for i, m in enumerate(milestones):
        when = start_date + timedelta(days=m.early_start)
        colour = "#2E7D32" if m.percent_complete >= 100 else (
            "#C00000" if when < today else "#3B6EA5")
        ax.plot(mdates.date2num(when), 0, marker="D", markersize=14, color=colour)
        ax.annotate(
            f"{m.name}\n{when.strftime('%d %b %Y')}",
            (mdates.date2num(when), 0),
            textcoords="offset points",
            xytext=(0, 18 if i % 2 == 0 else -34),
            ha="center", fontsize=8,
        )
    ax.axvline(mdates.date2num(today), color="#1A1A1A", linestyle="--",
               linewidth=1.2)
    ax.get_yaxis().set_visible(False)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.set_ylim(-1, 1)
    ax.set_title("Milestone Tracker", fontsize=13, fontweight="bold")
    for spine in ["left", "right", "top"]:
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
