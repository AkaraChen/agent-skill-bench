"""Stage 5 methodology package: slices, taxonomy, playbook, regression baseline."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from agent_skill_bench.profiles import (
    STAGE5_REVISION,
    failure_taxonomy,
    normalize_model,
    profile_manifest,
)

# Re-export for CLI.
__all__ = ["STAGE5_REVISION", "write_study_package"]
from agent_skill_bench.stats import bootstrap_ci, is_success, paired_comparison, slice_table

DISCLAIMER = (
    "Track A fixed-harness study using deterministic capability profiles. "
    "Conclusions apply only to this harness revision unless re-confirmed on Track B "
    "native agents. Numbers are per-slice with CIs — not a leaderboard."
)


def _load_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text())
    if isinstance(payload, dict):
        return list(payload.get("rows") or [])
    if isinstance(payload, list):
        return payload
    return []


def collect_rows(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if path.is_dir():
            candidate = path / "results.json"
            if candidate.exists():
                rows.extend(_load_rows(candidate))
            continue
        if path.name == "results.json":
            rows.extend(_load_rows(path))
    return rows


def _slice_key(row: dict[str, Any], fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(row.get(field) or "") for field in fields)


def task_slice(row: dict[str, Any]) -> str:
    task = str(row.get("task") or "")
    if "private" in task or task.startswith("clamp") or "/" not in task and task in {
        "clamp-range",
        "unique-lines",
        "csv-threshold",
        "word-freq",
        "path-jail",
        "redact-tokens",
    }:
        return "private"
    if any(name in task for name in ("clamp-range", "unique-lines", "word-freq", "path-jail", "redact-tokens", "csv-threshold")):
        return "private"
    return "public"


def enrich(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        item = dict(row)
        item["model_profile"] = normalize_model(str(row.get("model") or ""))
        item["task_slice"] = task_slice(row)
        item["config_revision"] = STAGE5_REVISION
        out.append(item)
    return out


def research_questions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Answer Stage 5 research questions with paired/slice evidence."""
    questions: dict[str, Any] = {}

    # Prompt gain: baseline vs plan, by agent.
    prompt_by_agent = []
    for agent in sorted({str(r.get("agent") or "") for r in rows}):
        subset = [r for r in rows if r.get("agent") == agent]
        try:
            paired = paired_comparison(subset, "baseline", "plan")
        except Exception:
            paired = {"error": "insufficient pairs", "agent": agent}
        prompt_by_agent.append({"agent": agent, "paired": paired})
    questions["prompt_gain_across_agents"] = {
        "question": "Is prompt (plan) gain stable across agents?",
        "by_agent": prompt_by_agent,
        "bound_to": {"treatments": ["baseline", "plan"], "revision": STAGE5_REVISION},
    }

    # Skill gain dependence.
    skill_slices = slice_table(rows, ("model_profile", "agent", "treatment"))
    questions["skill_gain_dependence"] = {
        "question": "Does skill/bundle gain depend on model, agent, and task slice?",
        "slices": [s for s in skill_slices if s.get("treatment") in {"skill", "bundle", "baseline"}],
        "task_slices": slice_table(rows, ("task_slice", "treatment")),
        "bound_to": {"revision": STAGE5_REVISION, "track": "A"},
    }

    # Complement / conflict: bundle vs plan and skill.
    combo = {}
    for left, right in (("plan", "bundle"), ("skill", "bundle"), ("baseline", "bundle")):
        try:
            combo[f"{left}_vs_{right}"] = paired_comparison(rows, left, right)
        except Exception as exc:
            combo[f"{left}_vs_{right}"] = {"error": str(exc)}
    questions["complement_conflict"] = {
        "question": "Do prompt+skill bundles complement or conflict?",
        "pairs": combo,
        "bound_to": {"revision": STAGE5_REVISION},
    }

    # Cost vs benefit
    cost_rows = []
    for treatment in sorted({str(r.get("treatment") or "") for r in rows}):
        items = [r for r in rows if r.get("treatment") == treatment]
        successes = [1.0 if is_success(r) else 0.0 for r in items if is_success(r) is not None]
        costs = [float(r["cost_usd"]) for r in items if r.get("cost_usd") is not None]
        cost_rows.append(
            {
                "treatment": treatment,
                "success_ci": bootstrap_ci(successes, seed=26),
                "cost_ci": bootstrap_ci(costs, seed=26),
                "n": len(items),
            }
        )
    questions["cost_latency_worth"] = {
        "question": "Is the success gain worth cost/latency?",
        "by_treatment": cost_rows,
        "bound_to": {"revision": STAGE5_REVISION, "cost_model": "profile-fixture"},
    }
    return questions


def per_model_playbook(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cards = []
    for profile in ("alpha", "beta", "gamma"):
        subset = [r for r in rows if normalize_model(str(r.get("model") or "")) == profile]
        if not subset:
            cards.append(
                {
                    "model_profile": profile,
                    "status": "no_rows",
                    "revision": STAGE5_REVISION,
                }
            )
            continue
        agent_table = slice_table(subset, ("agent",))
        treatment_table = slice_table(subset, ("treatment",))
        agent_x_treatment = slice_table(subset, ("agent", "treatment"))
        task_table = slice_table(subset, ("task_slice", "treatment"))

        def best(rows_in: list[dict[str, Any]], key: str) -> str | None:
            scored = [r for r in rows_in if r.get("success_rate") is not None]
            if not scored:
                return None
            scored.sort(key=lambda r: (-float(r["success_rate"]), -float(r.get("n_scored") or 0)))
            return str(scored[0].get(key) or scored[0].get("treatment") or "")

        recommended_agent = best(agent_table, "agent")
        recommended_treatment = best(treatment_table, "treatment")
        risky = [
            f"{r.get('agent')}/{r.get('treatment')}"
            for r in agent_x_treatment
            if (r.get("success_rate") is not None and float(r["success_rate"]) < 0.35)
        ]
        cards.append(
            {
                "model_profile": profile,
                "model_snapshots": [f"deterministic/{profile}@2026-08-26"],
                "recommended_agent": recommended_agent,
                "recommended_prompt_skill_bundle": recommended_treatment,
                "suitable_task_slices": task_table,
                "banned_or_risky_combos": risky,
                "agent_slices": agent_table,
                "treatment_slices": treatment_table,
                "cost_reliability": slice_table(subset, ("treatment",)),
                "applicability": "Track A fixed harness only",
                "revision": STAGE5_REVISION,
                "confidence_note": "Use per-slice CIs from stats; do not average away task/agent structure.",
            }
        )
    return cards


def taxonomy_from_rows(rows: list[dict[str, Any]], jobs_dir: Path | None = None) -> dict[str, Any]:
    catalog = failure_taxonomy()
    counts: dict[str, int] = defaultdict(int)
    samples: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        mode = None
        # Prefer profile decision artifacts when present in summary extras.
        mode = row.get("failure_mode") or row.get("profile_failure_mode")
        if not mode and row.get("failure_class") and row.get("failure_class") != "ok":
            mode = str(row.get("failure_class"))
        if is_success(row) is True:
            mode = mode or "success"
        if not mode:
            mode = "unknown"
        counts[str(mode)] += 1
        if len(samples[str(mode)]) < 3:
            samples[str(mode)].append(
                {
                    "trial_id": row.get("trial_id"),
                    "task": row.get("task"),
                    "agent": row.get("agent"),
                    "model": row.get("model"),
                    "treatment": row.get("treatment"),
                    "failure_class": row.get("failure_class"),
                }
            )

    # Optional trajectory audit hooks from job dirs.
    audited = 0
    if jobs_dir and jobs_dir.exists():
        for path in jobs_dir.rglob("profile_decision.json"):
            audited += 1
            try:
                payload = json.loads(path.read_text())
                mode = str(payload.get("failure_mode") or ("success" if payload.get("solve") else "deliberate_wrong"))
                counts[mode] += 0  # already counted via rows; keep file presence signal
            except json.JSONDecodeError:
                continue

    return {
        "revision": STAGE5_REVISION,
        "catalog": catalog,
        "counts": dict(counts),
        "samples_for_blind_review": dict(samples),
        "trajectory_decision_files": audited,
        "blind_review_protocol": [
            "Sample up to 3 trials per failure mode from samples_for_blind_review.",
            "Hide model/agent/treatment labels before human rubric scoring.",
            "Score: instruction_follow, security, maintainability (1-5).",
            "Do not use LLM-as-judge as primary evidence.",
        ],
    }


def regression_baseline(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "revision": STAGE5_REVISION,
        "n_rows": len(rows),
        "slices": {
            "treatment": slice_table(rows, ("treatment",)),
            "agent_x_treatment": slice_table(rows, ("agent", "treatment")),
            "model_x_treatment": slice_table(rows, ("model_profile", "treatment")),
            "task_slice_x_treatment": slice_table(rows, ("task_slice", "treatment")),
        },
        "reuse": (
            "Add a model/agent/prompt/skill, run configs/experiments/stage5-regression-baseline.yaml "
            "(or extend it), then diff new slice tables against this file. Keep the same seed and task pins."
        ),
    }


def write_score_tables(rows: list[dict[str, Any]], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "score_tables.csv"
    fields = [
        "trial_id",
        "task",
        "task_slice",
        "agent",
        "model",
        "model_profile",
        "treatment",
        "reward",
        "failure_class",
        "failure_mode",
        "profile_reason",
        "cost_usd",
        "duration_sec",
        "config_revision",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def render_playbook(
    *,
    cards: list[dict[str, Any]],
    questions: dict[str, Any],
    taxonomy: dict[str, Any],
    stats: dict[str, Any] | None = None,
) -> str:
    lines = [
        "# Model programming playbook (Track A)",
        "",
        DISCLAIMER,
        "",
        f"- Config revision: `{STAGE5_REVISION}`",
        f"- Dataset holdout revision: `2026.08.25.r3`",
        "- Applicability: **fixed Harbor harness (Track A)** with deterministic profiles.",
        "- Not applicable to: hosted LLM product rankings; Track B native agents until re-run.",
        "",
        "## How to read evidence",
        "",
        "- Prefer paired task-level bootstrap CIs and McNemar over totals.",
        "- Every claim below is bound to a task slice, treatment, and this revision.",
        "- Infra errors are excluded from success rates.",
        "",
        "## Per-model cards",
        "",
    ]
    for card in cards:
        lines.append(f"### {card.get('model_profile')}")
        if card.get("status") == "no_rows":
            lines.append("- No rows in this package.")
            lines.append("")
            continue
        lines.extend(
            [
                f"- Recommended agent: `{card.get('recommended_agent')}`",
                f"- Recommended prompt/skill bundle: `{card.get('recommended_prompt_skill_bundle')}`",
                f"- Risky combos: {', '.join(card.get('banned_or_risky_combos') or []) or '(none flagged <0.35)'}",
                f"- Applicability: {card.get('applicability')}",
                "",
            ]
        )
        lines.append("| treatment | success_rate | n_scored | cost_mean |")
        lines.append("|---|---:|---:|---:|")
        for row in card.get("treatment_slices") or []:
            lines.append(
                f"| {row.get('treatment')} | {row.get('success_rate')} | {row.get('n_scored')} | {row.get('cost_usd_mean')} |"
            )
        lines.append("")

    lines.extend(["## Research questions", ""])
    for key, payload in questions.items():
        lines.append(f"### {key}")
        lines.append(str(payload.get("question") or key))
        lines.append(f"- Bound to: `{json.dumps(payload.get('bound_to') or {}, sort_keys=True)}`")
        lines.append("- See `research_questions.json` for paired CIs / slices.")
        lines.append("")

    lines.extend(
        [
            "## Failure taxonomy",
            "",
            "Counts (from trials; use samples_for_blind_review for human audit):",
            "",
        ]
    )
    for mode, count in sorted((taxonomy.get("counts") or {}).items()):
        desc = (taxonomy.get("catalog") or {}).get(mode, "")
        lines.append(f"- `{mode}` ({count}): {desc}")
    lines.extend(
        [
            "",
            "## Incremental regression",
            "",
            "1. Keep `configs/experiments/stage5-regression-baseline.yaml` task/seed pins.",
            "2. Add only the new model/agent/prompt/skill under test.",
            "3. Run `asb run --config configs/experiments/stage5-regression-baseline.yaml`.",
            "4. Diff new slices against `regression_baseline.json`.",
            "",
            "## Repro",
            "",
            "```bash",
            "uv sync --extra dev",
            "uv run asb fetch-sealed && uv run asb assemble",
            "uv run asb pipeline --config configs/experiments/stage5-pipeline.yaml",
            "uv run asb study --results results/<screen-job> --results results/<confirm-job>",
            "```",
            "",
        ]
    )
    if stats:
        paired = stats.get("paired") or {}
        ci = paired.get("ci") or {}
        lines.extend(
            [
                "## Attached stats snapshot",
                "",
                f"- Paired mean diff: {ci.get('mean')} CI [{ci.get('low')}, {ci.get('high')}]",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def write_study_package(
    result_dirs: list[Path],
    out_dir: Path,
    *,
    jobs_dir: Path | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = enrich(collect_rows(result_dirs))
    questions = research_questions(rows)
    cards = per_model_playbook(rows)
    taxonomy = taxonomy_from_rows(rows, jobs_dir=jobs_dir)
    baseline = regression_baseline(rows)
    write_score_tables(rows, out_dir)

    (out_dir / "profile_manifest.json").write_text(json.dumps(profile_manifest(), indent=2) + "\n")
    (out_dir / "research_questions.json").write_text(json.dumps(questions, indent=2) + "\n")
    (out_dir / "model_cards.json").write_text(json.dumps(cards, indent=2) + "\n")
    (out_dir / "failure_taxonomy.json").write_text(json.dumps(taxonomy, indent=2) + "\n")
    (out_dir / "regression_baseline.json").write_text(json.dumps(baseline, indent=2) + "\n")
    playbook = render_playbook(cards=cards, questions=questions, taxonomy=taxonomy)
    (out_dir / "playbook.md").write_text(playbook)

    # Compact machine-readable index for the reproducible experiment pack.
    pack = {
        "revision": STAGE5_REVISION,
        "disclaimer": DISCLAIMER,
        "n_rows": len(rows),
        "result_dirs": [str(path) for path in result_dirs],
        "artifacts": [
            "playbook.md",
            "score_tables.csv",
            "research_questions.json",
            "model_cards.json",
            "failure_taxonomy.json",
            "regression_baseline.json",
            "profile_manifest.json",
        ],
    }
    (out_dir / "experiment_pack.json").write_text(json.dumps(pack, indent=2) + "\n")
    return out_dir / "playbook.md"
