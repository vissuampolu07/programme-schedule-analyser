"""
Critical Path Method (CPM) engine.

Performs forward and backward pass scheduling over a task network to compute
early/late start and finish dates, total float (slack), and the critical path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd


@dataclass
class Task:
    task_id: str
    name: str
    workstream: str
    owner: str
    duration: int
    dependencies: list[str] = field(default_factory=list)
    percent_complete: float = 0.0
    is_milestone: bool = False

    # Computed by the scheduler
    early_start: int = 0
    early_finish: int = 0
    late_start: int = 0
    late_finish: int = 0

    @property
    def total_float(self) -> int:
        """Days this task can slip without delaying the programme end date."""
        return self.late_start - self.early_start

    @property
    def is_critical(self) -> bool:
        return self.total_float == 0


def load_schedule(csv_path: str) -> dict[str, Task]:
    """Load the programme schedule CSV into a dict of Task objects."""
    df = pd.read_csv(csv_path)
    tasks: dict[str, Task] = {}
    for _, row in df.iterrows():
        deps = []
        if pd.notna(row["dependencies"]) and str(row["dependencies"]).strip():
            deps = [d.strip() for d in str(row["dependencies"]).split(";")]
        tasks[row["task_id"]] = Task(
            task_id=row["task_id"],
            name=row["task_name"],
            workstream=row["workstream"],
            owner=row["owner"],
            duration=int(row["duration_days"]),
            dependencies=deps,
            percent_complete=float(row["percent_complete"]),
            is_milestone=bool(row["is_milestone"]),
        )
    _validate(tasks)
    return tasks


def _validate(tasks: dict[str, Task]) -> None:
    """Check for unknown dependencies and circular references."""
    for t in tasks.values():
        for dep in t.dependencies:
            if dep not in tasks:
                raise ValueError(f"Task {t.task_id} depends on unknown task {dep}")

    # Cycle detection via depth-first search
    WHITE, GREY, BLACK = 0, 1, 2
    colour = {tid: WHITE for tid in tasks}

    def visit(tid: str) -> None:
        colour[tid] = GREY
        for dep in tasks[tid].dependencies:
            if colour[dep] == GREY:
                raise ValueError(f"Circular dependency detected involving {dep}")
            if colour[dep] == WHITE:
                visit(dep)
        colour[tid] = BLACK

    for tid in tasks:
        if colour[tid] == WHITE:
            visit(tid)


def _topological_order(tasks: dict[str, Task]) -> list[str]:
    """Kahn's algorithm — order tasks so dependencies always come first."""
    in_degree = {tid: len(t.dependencies) for tid, t in tasks.items()}
    successors: dict[str, list[str]] = {tid: [] for tid in tasks}
    for tid, t in tasks.items():
        for dep in t.dependencies:
            successors[dep].append(tid)

    queue = [tid for tid, deg in in_degree.items() if deg == 0]
    order: list[str] = []
    while queue:
        tid = queue.pop(0)
        order.append(tid)
        for succ in successors[tid]:
            in_degree[succ] -= 1
            if in_degree[succ] == 0:
                queue.append(succ)
    return order


def run_cpm(tasks: dict[str, Task]) -> tuple[dict[str, Task], int]:
    """Forward + backward pass. Returns tasks with dates filled and project duration."""
    order = _topological_order(tasks)

    # Forward pass — earliest each task can start/finish
    for tid in order:
        t = tasks[tid]
        t.early_start = max(
            (tasks[d].early_finish for d in t.dependencies), default=0
        )
        t.early_finish = t.early_start + t.duration

    project_duration = max(t.early_finish for t in tasks.values())

    # Backward pass — latest each task can start/finish without delaying the end
    for tid in reversed(order):
        t = tasks[tid]
        successors = [s for s in tasks.values() if tid in s.dependencies]
        t.late_finish = min(
            (s.late_start for s in successors), default=project_duration
        )
        t.late_start = t.late_finish - t.duration

    return tasks, project_duration


def critical_path(tasks: dict[str, Task]) -> list[Task]:
    """Return critical tasks in schedule order."""
    return sorted(
        (t for t in tasks.values() if t.is_critical),
        key=lambda t: t.early_start,
    )


def to_dataframe(tasks: dict[str, Task], start_date: date) -> pd.DataFrame:
    """Convert the scheduled network into a reporting-friendly DataFrame."""
    rows = []
    for t in sorted(tasks.values(), key=lambda x: (x.early_start, x.task_id)):
        rows.append(
            {
                "Task ID": t.task_id,
                "Task": t.name,
                "Workstream": t.workstream,
                "Owner": t.owner,
                "Duration (d)": t.duration,
                "Start": start_date + timedelta(days=t.early_start),
                "Finish": start_date + timedelta(days=t.early_finish),
                "Float (d)": t.total_float,
                "Critical": "Yes" if t.is_critical else "",
                "% Complete": t.percent_complete,
                "Milestone": "Yes" if t.is_milestone else "",
            }
        )
    return pd.DataFrame(rows)
