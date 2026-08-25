"""Build the Stage 4 report: warehouse + stats + dashboard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_skill_bench.constants import repo_root
from agent_skill_bench.dashboard import render, write_dashboard
from agent_skill_bench.stats import report as stats_report
from agent_skill_bench.summarize import summarize_job
from agent_skill_bench.warehouse import index_job, index_jobs, write_warehouse


def load_rows(results_json: Path) -> list[dict[str, Any]]:
    payload = json.loads(results_json.read_text())
    return list(payload.get("rows") or [])


def write_report(
    job_dir: Path | None = None,
    *,
    jobs_dir: Path | None = None,
    out_dir: Path | None = None,
    left: str | None = None,
    right: str | None = None,
) -> Path:
    root = repo_root()
    if job_dir is not None:
        path = job_dir if job_dir.is_absolute() else root / job_dir
        destination = out_dir or (root / "results" / path.name)
        summarize_job(path, destination)
        warehouse = {"n_jobs": 1, "jobs": [index_job(path, root)]}
        rows = load_rows(destination / "results.json")
    else:
        warehouse = index_jobs(jobs_dir, root)
        destination = out_dir or (root / "results" / "warehouse")
        rows = []
        results_root = root / "results"
        if results_root.exists():
            for path in sorted(results_root.rglob("results.json")):
                rows.extend(load_rows(path))
    stats = stats_report(rows, left=left, right=right)
    write_warehouse(warehouse, destination)
    (destination / "stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    md = _stats_markdown(stats)
    (destination / "stats.md").write_text(md)
    write_dashboard(render(stats, warehouse), destination)
    return destination / "dashboard.html"


def _stats_markdown(stats: dict[str, Any]) -> str:
    paired = stats.get("paired") or {}
    ci = paired.get("ci") or {}
    mcnemar = paired.get("mcnemar") or {}
    lines = [
        "# Statistical report",
        "",
        stats.get("disclaimer") or "",
        "",
        f"- Rows: {stats.get('n_rows')}",
    ]
    if paired:
        lines.extend(
            [
                f"- Paired: {paired.get('left')} vs {paired.get('right')} "
                f"(n={paired.get('n_pairs')})",
                f"- Mean diff: {ci.get('mean')} CI [{ci.get('low')}, {ci.get('high')}]",
                f"- McNemar p={mcnemar.get('p_value')} "
                f"n01={mcnemar.get('n01')} n10={mcnemar.get('n10')}",
            ]
        )
    lines.extend(["", "## Slices (agent × treatment)", ""])
    for row in (stats.get("slices") or {}).get("agent_x_treatment") or []:
        lines.append(
            f"- {row.get('agent')} / {row.get('treatment')}: "
            f"success={row.get('success_rate')} n={row.get('n_scored')} "
            f"infra={row.get('n_infra')} cost={row.get('cost_usd_mean')} "
            f"duration={row.get('duration_sec_mean')} failures={row.get('failures')}"
        )
    return "\n".join(lines) + "\n"
