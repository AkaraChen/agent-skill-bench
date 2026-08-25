"""Emit Stage 7 frozen catalog, task stubs, and dry-run experiment YAML."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

from agent_skill_bench.constants import DOCKER_DIGEST, DOCKER_IMAGE, repo_root
from agent_skill_bench.experiment import expand, format_dry_run, guard
from agent_skill_bench.stage7 import (
    AGENT_TIMEOUT_SEC,
    REVISION,
    STAGE_ISSUES,
    TASKS,
    VERIFIER_TIMEOUT_SEC,
    coverage_rows,
    experiment_spec,
    manifest,
    screen_plan,
)

DOCKERFILE = f"""FROM {DOCKER_IMAGE}@{DOCKER_DIGEST}
WORKDIR /app
COPY . /app
RUN rm -f /app/Dockerfile
"""

TASK_TOML = """schema_version = "1.4"

[task]
name = "asb/stage7/{task_id}"
version = "1.0.0"

[metadata]
difficulty = "{difficulty}"
category = "eric-way"
tags = ["stage7", "{scenario}", "{kind}", "{revision}"]

[verifier]
timeout_sec = {verifier_timeout}.0
network_mode = "no-network"

[agent]
timeout_sec = {agent_timeout}.0
network_mode = "no-network"

[environment]
build_timeout_sec = 300.0
cpus = 2
memory_mb = 2048
storage_mb = 4096
gpus = 0
workdir = "/app"
network_mode = "no-network"

[[artifacts]]
source = "/app"
destination = "workspace"
"""

TEST_SH = """#!/bin/bash
# Stage 7 stub: hidden oracle is specified in oracle.md.
# Stage 8 replaces this with executable checks. Fail closed until then.
echo "stage7 oracle stub; not an executable trial" >&2
echo 0 > /logs/verifier/reward.txt
exit 1
"""


def _dump_yaml(payload: dict) -> str:
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)


def write_task(root: Path, task) -> None:
    path = root / "tasks" / "stage7" / task.id
    env = path / "environment"
    tests = path / "tests"
    env.mkdir(parents=True, exist_ok=True)
    tests.mkdir(parents=True, exist_ok=True)
    (path / "instruction.md").write_text(task.instruction.strip() + "\n")
    (path / "task.toml").write_text(
        TASK_TOML.format(
            task_id=task.id,
            difficulty=task.difficulty,
            scenario=task.scenario,
            kind=task.kind,
            revision=REVISION,
            verifier_timeout=VERIFIER_TIMEOUT_SEC,
            agent_timeout=task.agent_timeout_sec,
        )
    )
    (env / "Dockerfile").write_text(DOCKERFILE)
    (tests / "oracle.md").write_text(task.oracle_spec.strip() + "\n")
    sh = tests / "test.sh"
    sh.write_text(TEST_SH)
    sh.chmod(0o755)


def write_anchor(root: Path) -> None:
    path = root / "tasks" / "stage7" / "_anchor"
    env = path / "environment"
    tests = path / "tests"
    env.mkdir(parents=True, exist_ok=True)
    tests.mkdir(parents=True, exist_ok=True)
    (path / "instruction.md").write_text(
        "Stage 7 dry-run anchor. Do not use this task for billed Codex trials. "
        "The real task path is cell.kwargs.asb_task.\n"
    )
    (path / "task.toml").write_text(
        TASK_TOML.format(
            task_id="_anchor",
            difficulty="easy",
            scenario="anchor",
            kind="implement",
            revision=REVISION,
            verifier_timeout=VERIFIER_TIMEOUT_SEC,
            agent_timeout=AGENT_TIMEOUT_SEC,
        )
    )
    (env / "Dockerfile").write_text(DOCKERFILE)
    (tests / "oracle.md").write_text("Anchor has no oracle. Expand asb_task before running.\n")
    sh = tests / "test.sh"
    sh.write_text(TEST_SH)
    sh.chmod(0o755)


def write_confirm_example(root: Path) -> None:
    spec = experiment_spec("8A", root)
    wanted_tasks = {"be-thin-transport", "js-ni-scripts", "qc-add-gates", "ci-pin-actions"}
    wanted_kinds = {"baseline", "single-backend", "realistic-backend", "overload-backend-kitchen"}
    spec["name"] = "stage9-confirm-placeholder"
    spec["repeat"] = 3
    spec["cells"] = [
        cell
        for cell in spec["cells"]
        if cell["kwargs"]["asb_task"].rsplit("/", 1)[-1] in wanted_tasks
        and cell["treatment"] in wanted_kinds
    ]
    keep = {cell["treatment"] for cell in spec["cells"]}
    spec["treatments"] = [item for item in spec["treatments"] if item["name"] in keep]
    spec["pairs"] = [pair for pair in spec["pairs"] if pair[0] in keep and pair[1] in keep]
    n_trials = len(spec["cells"]) * spec["repeat"]
    spec["max_trials"] = n_trials + 8
    spec["budget_usd"] = round(n_trials * 2.0 * 1.25, 2)
    path = root / "configs" / "experiments" / "stage9-confirm.example.yaml"
    header = (
        "# Stage 9 placeholder. Replace treatments/tasks with screening shortlist.\n"
        "# Do not run billed trials from this file as-is.\n"
    )
    path.write_text(header + _dump_yaml(spec))


def write_coverage_csv(root: Path, dest: Path) -> None:
    rows = coverage_rows()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_docs(root: Path, payload: dict) -> None:
    dest = root / "docs" / "stage7" / "README.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    screens = payload["screening"]["by_stage"]
    lines = [
        f"# Stage 7: Codex × eric-way freeze ({REVISION})",
        "",
        "Design and dry-run only. Do not start billed trials until Akara confirms the budget.",
        "",
        "## Pins",
        "",
        f"- eric-way commit: `{payload['pins']['eric_way_commit']}`",
        f"- agent-skill-bench base: `{payload['pins']['agent_skill_bench_base_commit']}`",
        f"- Harbor: `{payload['pins']['harbor_version']}`",
        f"- Codex CLI: `{payload['pins']['codex_cli_version']}`",
        f"- Model snapshot: `{payload['pins']['model_snapshot']}`",
        f"- Reasoning effort: `{payload['pins']['reasoning_effort']}`",
        f"- Web search: `{payload['pins']['web_search']}`",
        f"- Prompt: `{payload['pins']['system_prompt']}`",
        f"- Network: `{payload['pins']['network_mode']}`",
        f"- Container: `{payload['pins']['docker_image']}@{payload['pins']['docker_digest']}`",
        "",
        "## Screening dry-run",
        "",
        f"- Trials: **{payload['screening']['n_trials']}** (repeat=1)",
        f"- Estimated USD: **${payload['screening']['estimated_usd']:.2f}** at ${payload['pins']['usd_per_trial']}/trial",
        f"- Hard budget (125%): **${payload['screening']['budget_usd']:.2f}**",
        f"- Worst-case wall clock, serial stages: **{payload['screening']['max_wall_hours_serial']} h**",
        f"- Worst-case wall clock, parallel 8A–8D: **{payload['screening']['max_wall_hours_parallel_stages']} h**",
        "",
        "| Stage | Issue | Tasks | Trials | USD | Budget | Config |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for stage, row in screens.items():
        issue = row["issue"]["key"]
        lines.append(
            f"| {stage} | {issue} | {row['n_tasks']} | {row['n_trials']} | "
            f"${row['estimated_usd']:.2f} | ${row['budget_usd']:.2f} | `{row['config']}` |"
        )
    lines += [
        "",
        "## Confirm placeholder (Stage 9, not run)",
        "",
        f"- Placeholder trials: {payload['confirm']['n_trials_placeholder']} (repeat=3)",
        f"- Estimated USD: ${payload['confirm']['estimated_usd']:.2f}",
        f"- Config: `{payload['confirm']['issue']['config']}`",
        "",
        "## Artifact map",
        "",
        "- Skill freeze: `skills/eric-way/`",
        "- Catalog: `datasets/stage7/catalog.json`",
        "- Coverage matrix: `datasets/stage7/coverage-matrix.csv`",
        "- Task stubs: `tasks/stage7/<id>/`",
        "- Dry-run transcripts: `results/" + REVISION + "/`",
        "",
        "`cells[].kwargs.asb_task` is the real task path. `tasks/stage7/_anchor` exists only so the expander counts 1 task unit. Stage 8 must expand those kwargs into per-task Harbor jobs before any billed run.",
        "",
    ]
    dest.write_text("\n".join(lines) + "\n")


def main() -> None:
    root = repo_root()
    write_anchor(root)
    for task in TASKS:
        write_task(root, task)

    for stage in ("8A", "8B", "8C", "8D"):
        spec = experiment_spec(stage, root)
        path = root / STAGE_ISSUES[stage]["config"]
        path.parent.mkdir(parents=True, exist_ok=True)
        header = (
            f"# {REVISION} screening for Stage {stage}. Repeat=1. "
            "Do not billed-run until budget confirmation.\n"
        )
        path.write_text(header + _dump_yaml(spec))

    write_confirm_example(root)

    payload = manifest(root)
    dest_dir = root / "datasets" / "stage7"
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / "catalog.json").write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")
    write_coverage_csv(root, dest_dir / "coverage-matrix.csv")
    (dest_dir / "scoring.md").write_text(
        "\n".join(
            [
                "# Stage 7 scoring",
                "",
                "- Hidden tests own execution reward. Infra errors are not model failure.",
                "- Static checks are a second automatic axis, not a composite total.",
                "- UI/visual/grill/review use blinded human packets (no agent/model/treatment).",
                "- LLM judge is auxiliary only.",
                "- Review scores TP/FP/FN against a gold finding list.",
                "- Cost and duration are reported, never mixed into a single score.",
                "",
                "## Axes",
                "",
                *[f"- `{axis['id']}` ({axis['scale']}): {axis['prompt']}" for axis in payload["scoring"]["axes"]],
                "",
            ]
        )
    )
    (root / "datasets" / "stage7-revision.toml").write_text(
        f"""# Frozen Stage 7 catalog. Bump only with an explicit revision.

[stage7]
revision = "{REVISION}"
eric_way_commit = "{payload['pins']['eric_way_commit']}"
bench_base_commit = "{payload['pins']['agent_skill_bench_base_commit']}"
model_snapshot = "{payload['pins']['model_snapshot']}"
codex_cli_version = "{payload['pins']['codex_cli_version']}"
reasoning_effort = "{payload['pins']['reasoning_effort']}"
n_tasks = {payload['n_tasks']}
screening_trials = {payload['screening']['n_trials']}
"""
    )
    write_docs(root, payload)

    results = root / "results" / REVISION
    results.mkdir(parents=True, exist_ok=True)
    transcripts = []
    for stage in ("8A", "8B", "8C", "8D"):
        spec = experiment_spec(stage, root)
        plan = expand(spec, root)
        guard(plan)
        expected = screen_plan(stage)
        if plan.n_trials != expected.n_trials:
            raise SystemExit(
                f"{stage} dry-run trials {plan.n_trials} != catalog {expected.n_trials}"
            )
        text = format_dry_run(plan)
        (results / f"{stage.lower()}-dry-run.txt").write_text(text + "\n")
        transcripts.append(
            {
                "stage": stage,
                "n_trials": plan.n_trials,
                "estimated_usd": plan.estimated_usd,
                "budget_usd": plan.budget_usd,
                "max_trials": plan.max_trials,
                "n_cells": plan.n_cells,
                "n_task_units": plan.n_task_units,
            }
        )
    (results / "dry-run-summary.json").write_text(json.dumps({"revision": REVISION, "stages": transcripts, "manifest": payload}, indent=2) + "\n")
    print(json.dumps({"revision": REVISION, "stages": transcripts}, indent=2))


if __name__ == "__main__":
    main()
