"""Screen then confirm. Ranking is a filter, not a published score."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

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
) -> dict[str, Any]:
    if not treatments:
        raise ExperimentError("confirm needs at least one treatment from the screen")
    spec = deepcopy(screen_spec)
    spec["name"] = f"{screen_spec.get('name') or 'screen'}-confirm"
    spec["repeat"] = repeat
    spec.pop("sample", None)
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
    confirm = confirm_spec(
        screen_spec,
        ranked,
        repeat=repeat,
        max_trials=confirm_cfg.get("max_trials"),
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
    return "\n".join(lines)
