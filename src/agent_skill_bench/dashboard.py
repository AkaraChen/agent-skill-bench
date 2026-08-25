"""Static dashboard HTML. Slices only — no composite score."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.3f}"
    return html.escape(str(value))


def _table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "<p><em>none</em></p>"
    head = "".join(f"<th>{html.escape(col)}</th>" for col in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{_cell(row.get(col))}</td>" for col in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def render(report: dict[str, Any], warehouse: dict[str, Any] | None = None) -> str:
    slices = report.get("slices") or {}
    paired = report.get("paired") or {}
    reliability = report.get("reliability") or {}
    interaction = report.get("interaction") or {}
    jobs = (warehouse or {}).get("jobs") or []
    trial_rows: list[dict[str, Any]] = []
    for job in jobs:
        for trial in job.get("trials") or []:
            artifacts = trial.get("artifacts") or {}
            trial_rows.append(
                {
                    "trial_id": trial.get("trial_id"),
                    "job": trial.get("job"),
                    "task": trial.get("task"),
                    "agent": trial.get("agent"),
                    "treatment": trial.get("treatment"),
                    "manifest": artifacts.get("manifest"),
                    "result": artifacts.get("result"),
                    "trial_dir": artifacts.get("trial_dir"),
                    "patch_digest": (artifacts.get("patch_digest") or "")[:16],
                }
            )
    mcnemar = paired.get("mcnemar") or {}
    ci = paired.get("ci") or {}
    agent_ix = interaction.get("agent") or {}
    contrast = agent_ix.get("contrast") or {}
    parts = [
        "<!doctype html><html><head><meta charset='utf-8'><title>ASB report</title>",
        "<style>body{font-family:sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem}",
        "table{border-collapse:collapse;margin:1rem 0;width:100%}",
        "th,td{border:1px solid #ccc;padding:.4rem .6rem;text-align:left;font-size:.9rem}",
        "th{background:#f4f4f4}.note{background:#fff8e1;padding:.8rem 1rem}</style></head><body>",
        "<h1>Experiment report</h1>",
        f"<p class='note'>{_cell(report.get('disclaimer'))}</p>",
        f"<p>Trials: {report.get('n_rows', 0)}. Jobs: {(warehouse or {}).get('n_jobs', 0)}.</p>",
        "<h2>Paired comparison</h2>",
        (
            f"<p>{_cell(paired.get('left'))} vs {_cell(paired.get('right'))}: "
            f"mean diff { _cell(ci.get('mean')) } "
            f"CI [{_cell(ci.get('low'))}, {_cell(ci.get('high'))}]. "
            f"McNemar p={_cell(mcnemar.get('p_value'))} "
            f"(n01={_cell(mcnemar.get('n01'))}, n10={_cell(mcnemar.get('n10'))}). "
            f"Unit: {_cell(paired.get('unit'))}.</p>"
            if paired
            else "<p>No paired treatments.</p>"
        ),
        "<h2>Reliability</h2>",
        f"<p>pass^1={_cell((reliability.get('pass_hat_1') or {}).get('pass_hat_k'))} "
        f"n={_cell((reliability.get('pass_hat_1') or {}).get('n'))}; "
        f"pass^3={_cell((reliability.get('pass_hat_3') or {}).get('pass_hat_k'))} "
        f"n={_cell((reliability.get('pass_hat_3') or {}).get('n'))}.</p>",
        "<h2>Interaction (treatment × agent)</h2>",
        (
            f"<p>{_cell(contrast.get('interpretation'))}: "
            f"mean { _cell(contrast.get('mean')) } "
            f"CI [{_cell(contrast.get('low'))}, {_cell(contrast.get('high'))}]. "
            f"Method: task-clustered bootstrap.</p>"
            if contrast
            else "<p>Need two agents to estimate an agent interaction.</p>"
        ),
        "<h2>Slices</h2>",
    ]
    for name, key_cols in (
        ("agent", ["agent"]),
        ("treatment / skill", ["treatment"]),
        ("task", ["task"]),
        ("agent × treatment", ["agent", "treatment"]),
        ("model", ["model"]),
        ("prompt", ["prompt"]),
    ):
        slug = {
            "agent": "agent",
            "treatment / skill": "skill",
            "task": "task",
            "agent × treatment": "agent_x_treatment",
            "model": "model",
            "prompt": "prompt",
        }[name]
        parts.append(f"<h3>{name}</h3>")
        parts.append(
            _table(
                slices.get(slug) or [],
                [*key_cols, "n", "n_scored", "n_infra", "success_rate", "cost_usd_mean", "duration_sec_mean"],
            )
        )
    parts.extend(
        [
            "<h2>Artifact index</h2>",
            "<p>Each trial_id maps to its manifest and raw result. Patches are per trial_dir.</p>",
            _table(
                trial_rows,
                ["trial_id", "job", "task", "agent", "treatment", "manifest", "result", "trial_dir", "patch_digest"],
            ),
            "</body></html>",
        ]
    )
    return "\n".join(parts)


def write_dashboard(html_text: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "dashboard.html"
    path.write_text(html_text)
    return path
