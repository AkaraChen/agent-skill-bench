"""Task-level paired stats. No composite score.

Implements:
- percentile CI via bootstrap
- McNemar exact test on paired binary outcomes
- task-clustered (hierarchical) bootstrap for treatment × factor interactions
- slice tables (success, reliability, cost, speed, failure class)

ponytail: clustered bootstrap instead of a mixed-effects fitter. Same
question — is the treatment gap stable across tasks/agents — without lme4.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Any, Iterable

DEFAULT_BOOTSTRAP = 2000
DISCLAIMER = (
    "These numbers are per-slice evidence, not a ranking and not a single score. "
    "Infra errors are excluded from success rate and paired tests."
)


def is_success(row: dict[str, Any]) -> bool | None:
    if row.get("infra_error") or row.get("failure_class") == "infra":
        return None
    if row.get("failure_class") == "ok":
        return True
    reward = row.get("reward")
    try:
        return float(reward) >= 1
    except (TypeError, ValueError):
        return False


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        raise ValueError("percentile of empty sample")
    if len(sorted_values) == 1:
        return sorted_values[0]
    index = (len(sorted_values) - 1) * p
    lo = math.floor(index)
    hi = math.ceil(index)
    if lo == hi:
        return sorted_values[lo]
    weight = index - lo
    return sorted_values[lo] * (1 - weight) + sorted_values[hi] * weight


def bootstrap_ci(
    values: list[float],
    *,
    n: int = DEFAULT_BOOTSTRAP,
    seed: int = 42,
    alpha: float = 0.05,
) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "low": None, "high": None, "n": 0}
    rng = random.Random(seed)
    samples: list[float] = []
    size = len(values)
    for _ in range(n):
        draw = [values[rng.randrange(size)] for _ in range(size)]
        samples.append(sum(draw) / size)
    samples.sort()
    return {
        "mean": sum(values) / size,
        "low": percentile(samples, alpha / 2),
        "high": percentile(samples, 1 - alpha / 2),
        "n": size,
        "n_boot": n,
        "alpha": alpha,
    }


def mcnemar_exact(n01: int, n10: int) -> dict[str, float | int]:
    """Exact McNemar two-sided p-value. n01 = left fail/right pass, n10 = left pass/right fail."""
    discordant = n01 + n10
    if discordant == 0:
        return {"n01": n01, "n10": n10, "n_discordant": 0, "p_value": 1.0, "test": "mcnemar-exact"}
    k = min(n01, n10)
    tail = sum(math.comb(discordant, i) for i in range(k + 1))
    p_value = min(1.0, 2 * tail / (2**discordant))
    return {
        "n01": n01,
        "n10": n10,
        "n_discordant": discordant,
        "p_value": p_value,
        "test": "mcnemar-exact",
    }


def _pair_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("task") or ""),
        str(row.get("agent") or ""),
        str(row.get("model") or ""),
    )


def _rate(outcomes: list[bool]) -> float:
    return sum(outcomes) / len(outcomes)


def paired_outcomes(
    rows: Iterable[dict[str, Any]],
    left: str,
    right: str,
) -> list[dict[str, Any]]:
    """One record per (task, agent, model) with both treatments.

    Repeats of the same arm are averaged so input order cannot change the
    paired diff. McNemar uses mean>=0.5 as the binary call; bootstrap uses
    the rate difference.
    """
    buckets: dict[tuple[str, str, str], dict[str, list[bool]]] = defaultdict(
        lambda: defaultdict(list)
    )
    pairing = ""
    for row in rows:
        outcome = is_success(row)
        if outcome is None:
            continue
        treatment = str(row.get("treatment") or "")
        if treatment not in (left, right):
            continue
        buckets[_pair_key(row)][treatment].append(outcome)
        if row.get("pair_id"):
            pairing = str(row["pair_id"])
    pairs: list[dict[str, Any]] = []
    for (task, agent, model), arms in buckets.items():
        if left not in arms or right not in arms:
            continue
        left_rate = _rate(arms[left])
        right_rate = _rate(arms[right])
        pairs.append(
            {
                "task": task,
                "agent": agent,
                "model": model,
                "pair_id": pairing or f"{left}__{right}",
                "left": left,
                "right": right,
                "n_left": len(arms[left]),
                "n_right": len(arms[right]),
                "left_rate": left_rate,
                "right_rate": right_rate,
                "left_pass": left_rate >= 0.5,
                "right_pass": right_rate >= 0.5,
                "diff": right_rate - left_rate,
            }
        )
    pairs.sort(key=lambda item: (item["task"], item["agent"], item["model"]))
    return pairs


def _cluster_by_task(pairs: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in pairs:
        clusters[str(item.get("task") or "")].append(item)
    return dict(clusters)


def _task_summary(cells: list[dict[str, Any]]) -> dict[str, Any]:
    left_rate = _mean([float(cell["left_rate"]) for cell in cells])
    right_rate = _mean([float(cell["right_rate"]) for cell in cells])
    diff = _mean([float(cell["diff"]) for cell in cells])
    return {
        "n_cells": len(cells),
        "left_rate": left_rate,
        "right_rate": right_rate,
        "left_pass": (left_rate or 0) >= 0.5 if left_rate is not None else False,
        "right_pass": (right_rate or 0) >= 0.5 if right_rate is not None else False,
        "diff": diff,
        "cells": cells,
    }


def paired_bootstrap(
    pairs: list[dict[str, Any]],
    *,
    n: int = DEFAULT_BOOTSTRAP,
    seed: int = 42,
) -> dict[str, Any]:
    """Task-clustered paired bootstrap.

    Resample task IDs with replacement and keep every agent/model cell inside
    a drawn task. The replicate statistic is the unweighted mean of per-task
    diffs so a task with more cells does not get more weight. McNemar uses
    the same task-level binary calls.
    """
    clusters = _cluster_by_task(pairs)
    tasks = sorted(clusters)
    summaries = {task: _task_summary(clusters[task]) for task in tasks}
    task_diffs = [float(summaries[task]["diff"] or 0) for task in tasks]
    ci = bootstrap_ci(task_diffs, n=n, seed=seed)
    rng = random.Random(seed)
    samples: list[float] = []
    n_tasks = len(tasks)
    if n_tasks:
        for _ in range(n):
            drawn = [tasks[rng.randrange(n_tasks)] for _ in range(n_tasks)]
            # Keep all agent/model observations of each drawn task (multiplicity
            # from resampling), then reduce to one diff per drawn task.
            retained = [cell for task in drawn for cell in clusters[task]]
            if not retained:
                continue
            samples.append(
                sum(float(summaries[task]["diff"] or 0) for task in drawn) / n_tasks
            )
        samples.sort()
        if samples:
            ci = {
                "mean": sum(task_diffs) / n_tasks,
                "low": percentile(samples, 0.025),
                "high": percentile(samples, 0.975),
                "n": n_tasks,
                "n_boot": n,
                "alpha": 0.05,
            }
    n01 = sum(1 for task in tasks if not summaries[task]["left_pass"] and summaries[task]["right_pass"])
    n10 = sum(1 for task in tasks if summaries[task]["left_pass"] and not summaries[task]["right_pass"])
    n11 = sum(1 for task in tasks if summaries[task]["left_pass"] and summaries[task]["right_pass"])
    n00 = sum(1 for task in tasks if not summaries[task]["left_pass"] and not summaries[task]["right_pass"])
    left_rate = _mean([1.0 if summaries[task]["left_pass"] else 0.0 for task in tasks])
    right_rate = _mean([1.0 if summaries[task]["right_pass"] else 0.0 for task in tasks])
    return {
        "n_pairs": n_tasks,
        "n_cells": len(pairs),
        "n_tasks": n_tasks,
        "left_success": left_rate,
        "right_success": right_rate,
        "mean_diff": ci["mean"],
        "ci": ci,
        "table": {"n11": n11, "n00": n00, "n01": n01, "n10": n10},
        "mcnemar": {**mcnemar_exact(n01, n10), "n11": n11, "n00": n00, "unit": "task"},
        "unit": "task",
        "method": "task-clustered-bootstrap",
    }


def pass_at_k(rows: Iterable[dict[str, Any]], k: int = 1) -> dict[str, Any]:
    """Reliability: share of groups whose first k repeats all succeed. Infra dropped."""
    groups: dict[tuple[str, str, str, str], list[bool]] = defaultdict(list)
    for row in rows:
        outcome = is_success(row)
        if outcome is None:
            continue
        key = (
            str(row.get("task") or ""),
            str(row.get("agent") or ""),
            str(row.get("model") or ""),
            str(row.get("treatment") or ""),
        )
        groups[key].append(outcome)
    eligible = [outcomes for outcomes in groups.values() if len(outcomes) >= k]
    if not eligible:
        return {"k": k, "n": 0, "pass_hat_k": None}
    wins = sum(1 for outcomes in eligible if all(outcomes[:k]))
    return {"k": k, "n": len(eligible), "pass_hat_k": wins / len(eligible)}


def slice_table(
    rows: Iterable[dict[str, Any]],
    keys: tuple[str, ...],
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(str(row.get(key) or "") for key in keys)].append(row)
    table: list[dict[str, Any]] = []
    for identity, items in sorted(groups.items()):
        counted = [item for item in items if is_success(item) is not None]
        successes = [item for item in counted if is_success(item)]
        infra = sum(1 for item in items if item.get("failure_class") == "infra")
        costs = [float(item["cost_usd"]) for item in items if item.get("cost_usd") is not None]
        durations = [
            float(item["duration_sec"])
            for item in items
            if item.get("duration_sec") is not None
        ]
        failures: dict[str, int] = {}
        for item in items:
            cls = str(item.get("failure_class") or "unknown")
            failures[cls] = failures.get(cls, 0) + 1
        row: dict[str, Any] = {key: value for key, value in zip(keys, identity)}
        row.update(
            {
                "n": len(items),
                "n_scored": len(counted),
                "n_infra": infra,
                "success_rate": (len(successes) / len(counted)) if counted else None,
                "cost_usd_mean": _mean(costs),
                "duration_sec_mean": _mean(durations),
                "failures": failures,
            }
        )
        table.append(row)
    return table


def interaction_bootstrap(
    rows: list[dict[str, Any]],
    *,
    treatment_left: str,
    treatment_right: str,
    factor: str = "agent",
    n: int = DEFAULT_BOOTSTRAP,
    seed: int = 42,
) -> dict[str, Any]:
    """Task-clustered bootstrap of (right-left) success gap per factor level, plus the contrast.

    Hierarchical: resample tasks, keep all (agent, treatment) observations of
    that task. This is the mixed-effects question (does the treatment gap
    depend on the factor?) without fitting a random-effects model.
    """
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    levels: set[str] = set()
    for row in rows:
        if is_success(row) is None:
            continue
        treatment = str(row.get("treatment") or "")
        if treatment not in (treatment_left, treatment_right):
            continue
        by_task[str(row.get("task") or "")].append(row)
        levels.add(str(row.get(factor) or ""))
    tasks = sorted(by_task)
    ordered_levels = sorted(levels)
    if len(tasks) < 1 or len(ordered_levels) < 2:
        return {
            "factor": factor,
            "levels": ordered_levels,
            "n_tasks": len(tasks),
            "gaps": {},
            "contrast": None,
            "note": "need ≥1 task and ≥2 factor levels",
        }

    def gaps_for(task_names: list[str]) -> dict[str, float]:
        tallies: dict[tuple[str, str], list[int]] = defaultdict(list)
        for name in task_names:
            for row in by_task[name]:
                outcome = is_success(row)
                if outcome is None:
                    continue
                key = (str(row.get(factor) or ""), str(row.get("treatment") or ""))
                tallies[key].append(int(outcome))
        out: dict[str, float] = {}
        for level in ordered_levels:
            left = tallies.get((level, treatment_left)) or []
            right = tallies.get((level, treatment_right)) or []
            if not left or not right:
                continue
            out[level] = (sum(right) / len(right)) - (sum(left) / len(left))
        return out

    observed = gaps_for(tasks)
    rng = random.Random(seed)
    samples: dict[str, list[float]] = defaultdict(list)
    contrasts: list[float] = []
    size = len(tasks)
    for _ in range(n):
        draw = [tasks[rng.randrange(size)] for _ in range(size)]
        gaps = gaps_for(draw)
        for level, value in gaps.items():
            samples[level].append(value)
        if len(ordered_levels) >= 2 and ordered_levels[0] in gaps and ordered_levels[1] in gaps:
            contrasts.append(gaps[ordered_levels[1]] - gaps[ordered_levels[0]])

    gap_ci = {
        level: {
            "mean": observed.get(level),
            "low": percentile(sorted(samples[level]), 0.025) if samples[level] else None,
            "high": percentile(sorted(samples[level]), 0.975) if samples[level] else None,
            "n_boot": len(samples[level]),
        }
        for level in ordered_levels
    }
    contrast = None
    if contrasts:
        ordered = sorted(contrasts)
        contrast = {
            "levels": [ordered_levels[0], ordered_levels[1]],
            "mean": _mean(contrasts),
            "low": percentile(ordered, 0.025),
            "high": percentile(ordered, 0.975),
            "n_boot": len(contrasts),
            "interpretation": (
                f"({treatment_right}-{treatment_left}) at {ordered_levels[1]} "
                f"minus the same gap at {ordered_levels[0]}"
            ),
        }
    return {
        "factor": factor,
        "left": treatment_left,
        "right": treatment_right,
        "n_tasks": len(tasks),
        "gaps": gap_ci,
        "contrast": contrast,
        "method": "task-clustered-bootstrap",
    }


def report(
    rows: list[dict[str, Any]],
    *,
    left: str | None = None,
    right: str | None = None,
    seed: int = 42,
    n_boot: int = DEFAULT_BOOTSTRAP,
) -> dict[str, Any]:
    treatments = sorted({str(row.get("treatment") or "") for row in rows if row.get("treatment")})
    pair_left = left or (treatments[0] if treatments else "")
    pair_right = right or (treatments[1] if len(treatments) > 1 else "")
    pairs = paired_outcomes(rows, pair_left, pair_right) if pair_left and pair_right else []
    payload: dict[str, Any] = {
        "disclaimer": DISCLAIMER,
        "n_rows": len(rows),
        "slices": {
            "model": slice_table(rows, ("model",)),
            "agent": slice_table(rows, ("agent",)),
            "prompt": slice_table(rows, ("prompt",)),
            "skill": slice_table(rows, ("treatment",)),
            "task": slice_table(rows, ("task",)),
            "agent_x_treatment": slice_table(rows, ("agent", "treatment")),
        },
        "reliability": {
            "pass_hat_1": pass_at_k(rows, 1),
            "pass_hat_3": pass_at_k(rows, 3),
        },
        "overall_cost": bootstrap_ci(
            [float(row["cost_usd"]) for row in rows if row.get("cost_usd") is not None],
            n=n_boot,
            seed=seed,
        ),
        "overall_duration": bootstrap_ci(
            [float(row["duration_sec"]) for row in rows if row.get("duration_sec") is not None],
            n=n_boot,
            seed=seed,
        ),
    }
    if pairs:
        payload["paired"] = paired_bootstrap(pairs, n=n_boot, seed=seed)
        payload["paired"]["left"] = pair_left
        payload["paired"]["right"] = pair_right
        payload["interaction"] = {
            "agent": interaction_bootstrap(
                rows,
                treatment_left=pair_left,
                treatment_right=pair_right,
                factor="agent",
                n=n_boot,
                seed=seed,
            ),
            "model": interaction_bootstrap(
                rows,
                treatment_left=pair_left,
                treatment_right=pair_right,
                factor="model",
                n=n_boot,
                seed=seed,
            ),
        }
    return payload
