"""Screen then confirm. Ranking is a filter, not a published score."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

import yaml

from agent_skill_bench.experiment import ExperimentError, Plan, expand, guard
from agent_skill_bench.stats import slice_table

PIPELINE_KIND = "pipeline"


def is_pipeline(spec: dict[str, Any]) -> bool:
    return str(spec.get("kind") or "") == PIPELINE_KIND or "screen" in spec and "confirm" in spec and "treatments" not in spec


def rank_treatments(rows: list[dict[str, Any]], top_k: int) -> list[str]:
    table = slice_table(rows, ("treatment",))
    scored = [row for row in table if row.get("success_rate") is not None]
    scored.sort(key=lambda row: (-float(row["success_rate"]), str(row["treatment"])))
    names = [str(row["treatment"]) for row in scored[: max(0, top_k)]]
    if names:
        return names
    # No results yet: keep declared order.
    seen: list[str] = []
    for row in rows:
        name = str(row.get("treatment") or "")
        if name and name not in seen:
            seen.append(name)
        if len(seen) >= top_k:
            break
    return seen


def confirm_spec(
    screen_spec: dict[str, Any],
    treatments: list[str],
    *,
    repeat: int,
    max_trials: int | None = None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not treatments:
        raise ExperimentError("confirm needs at least one treatment from the screen")
    spec = deepcopy(screen_spec)
    spec["name"] = f"{screen_spec.get('name') or 'screen'}-confirm"
    spec["repeat"] = repeat
    spec.pop("sample", None)
    # Drop fractional screen cells so confirm re-expands agents × models × shortlist.
    spec.pop("cells", None)
    declared = spec.get("treatments") or []
    keep = [item for item in declared if str(item.get("name")) in set(treatments)]
    if not keep:
        raise ExperimentError(f"screen treatments {treatments} are not in the experiment")
    spec["treatments"] = keep
    pairs = []
    names = {str(item["name"]) for item in keep}
    for pair in spec.get("pairs") or []:
        items = list(pair)
        if len(items) == 2 and items[0] in names and items[1] in names:
            pairs.append(pair)
    spec["pairs"] = pairs
    if max_trials is not None:
        spec["max_trials"] = max_trials
    # Optional confirm-only narrowing so screen can cover factors without
    # exploding confirm × repeat (ponytail: keep overrides shallow).
    for key in ("agents", "models", "tasks", "datasets", "include", "exclude", "n_concurrent"):
        if overrides and key in overrides and overrides[key] is not None:
            spec[key] = deepcopy(overrides[key])
    if overrides and overrides.get("assemble_sealed") is not None:
        spec["assemble_sealed"] = overrides["assemble_sealed"]
    if overrides and overrides.get("assembled_path") is not None:
        spec["assembled_path"] = overrides["assembled_path"]
    return spec


def plan_pipeline(
    pipeline_spec: dict[str, Any],
    screen_spec: dict[str, Any],
    root,
    rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    screen_plan: Plan = expand(screen_spec, root)
    guard(screen_plan)
    confirm_cfg = pipeline_spec.get("confirm") or {}
    top_k = int(confirm_cfg.get("top_k") or 2)
    repeat = int(confirm_cfg.get("repeat") or 3)
    if repeat < 1:
        raise ExperimentError("confirm.repeat must be >= 1")
    ranked = rank_treatments(rows or [], top_k)
    if not ranked:
        ranked = [str(item["name"]) for item in (screen_spec.get("treatments") or [])[:top_k]]
    overrides = {
        key: confirm_cfg.get(key)
        for key in (
            "agents",
            "models",
            "tasks",
            "datasets",
            "include",
            "exclude",
            "n_concurrent",
            "assemble_sealed",
            "assembled_path",
        )
        if key in confirm_cfg
    }
    confirm = confirm_spec(
        screen_spec,
        ranked,
        repeat=repeat,
        max_trials=confirm_cfg.get("max_trials"),
        overrides=overrides or None,
    )
    confirm_plan = expand(confirm, root)
    guard(confirm_plan)
    return {
        "name": str(pipeline_spec.get("name") or "pipeline"),
        "screen": {
            "n_trials": screen_plan.n_trials,
            "n_cells": screen_plan.n_cells,
            "estimated_usd": screen_plan.estimated_usd,
        },
        "ranked_treatments": ranked,
        "confirm": {
            "n_trials": confirm_plan.n_trials,
            "n_cells": confirm_plan.n_cells,
            "repeat": confirm_plan.repeat,
            "estimated_usd": confirm_plan.estimated_usd,
            "spec": confirm,
        },
        "note": (
            "Screen ranks treatments by success_rate (infra excluded) so the "
            "confirm phase can spend repeats on a shortlist. The rank is a "
            "filter, not a published score."
        ),
    }


def format_pipeline(payload: dict[str, Any]) -> str:
    screen = payload["screen"]
    confirm = payload["confirm"]
    lines = [
        f"pipeline: {payload['name']}",
        f"screen.trials: {screen['n_trials']}",
        f"screen.estimated_usd: {screen['estimated_usd']}",
        f"ranked_treatments: {', '.join(payload['ranked_treatments']) or '(none)'}",
        f"confirm.repeat: {confirm['repeat']}",
        f"confirm.cells: {confirm['n_cells']}",
        f"confirm.trials: {confirm['n_trials']}",
        f"confirm.estimated_usd: {confirm['estimated_usd']}",
        payload["note"],
    ]
    if payload.get("executed"):
        lines.append(f"screen.job: {screen.get('job_dir') or '(skipped)'}")
        lines.append(f"confirm.job: {confirm.get('job_dir')}")
    return "\n".join(lines)


RunFn = Callable[[Path], Path | None]
RowsFn = Callable[[Path], list[dict[str, Any]]]


def _default_run(config: Path) -> Path | None:
    from agent_skill_bench.run import run_job

    return run_job(config)


def _default_rows(job_dir: Path) -> list[dict[str, Any]]:
    from agent_skill_bench.constants import repo_root
    from agent_skill_bench.summarize import summarize_job

    out = repo_root() / "results" / job_dir.name
    summarize_job(job_dir, out)
    payload = json.loads((out / "results.json").read_text())
    return list(payload.get("rows") or [])


def run_pipeline(
    pipeline_spec: dict[str, Any],
    screen_spec: dict[str, Any],
    root: Path,
    *,
    screen_path: Path | None = None,
    rows: list[dict[str, Any]] | None = None,
    dry_run: bool = False,
    run_fn: RunFn | None = None,
    rows_fn: RowsFn | None = None,
) -> dict[str, Any]:
    """Plan, then actually run screen → rank → confirm unless dry_run."""
    payload = plan_pipeline(pipeline_spec, screen_spec, root, rows)
    payload["executed"] = False
    payload["screen"]["job_dir"] = None
    payload["confirm"]["job_dir"] = None
    payload["confirm"]["spec_path"] = None
    if dry_run:
        return payload

    runner = run_fn or _default_run
    load_rows = rows_fn or _default_rows
    generated = root / "jobs" / ".generated"
    generated.mkdir(parents=True, exist_ok=True)

    screen_job_dir: Path | None = None
    screen_rows = list(rows or [])
    if not screen_rows:
        if screen_path is None:
            raise ExperimentError("pipeline run needs screen.experiment path")
        screen_job = runner(screen_path)
        if screen_job is None:
            raise ExperimentError("screen run produced no job directory")
        screen_job_dir = screen_job
        screen_rows = load_rows(screen_job)

    payload = plan_pipeline(pipeline_spec, screen_spec, root, screen_rows)
    payload["executed"] = True
    payload["screen"]["job_dir"] = str(screen_job_dir) if screen_job_dir else None

    confirm_path = generated / f"{payload['name']}-confirm.yaml"
    confirm_path.write_text(yaml.safe_dump(payload["confirm"]["spec"], sort_keys=False))
    payload["confirm"]["spec_path"] = str(confirm_path)
    confirm_job = runner(confirm_path)
    if confirm_job is None:
        raise ExperimentError("confirm run produced no job directory")
    payload["confirm"]["job_dir"] = str(confirm_job)
    load_rows(confirm_job)
    return payload
