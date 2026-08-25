from pathlib import Path

import pytest

from agent_skill_bench.constants import repo_root
from agent_skill_bench.experiment import ExperimentError, expand, guard, load_yaml
from agent_skill_bench.fingerprint import sha256_tree
from agent_skill_bench.scorer import stage7_rubric_packet
from agent_skill_bench.stage7 import (
    EXCLUDED_SKILLS,
    INCLUDED_SKILLS,
    MODEL_SNAPSHOT,
    REVISION,
    STAGE_ISSUES,
    TASKS,
    TREATMENTS,
    coverage_rows,
    experiment_spec,
    freeze_skills,
    independent_controls,
    manifest,
    screen_plan,
)


def test_each_included_skill_has_three_tasks_and_a_control() -> None:
    controls = {row["skill"]: row for row in independent_controls()}
    for skill in INCLUDED_SKILLS:
        tasks = [task for task in TASKS if task.primary_skill == skill]
        assert len(tasks) >= 3, skill
        kinds = {task.kind for task in tasks}
        assert kinds, skill
        assert int(controls[skill]["n_tasks"]) >= 3
        assert "baseline vs single-" in controls[skill]["control"]


def test_excluded_collaboration_skills_never_load() -> None:
    assert "eric-github-pr" in EXCLUDED_SKILLS
    for treatment in TREATMENTS.values():
        assert "eric-github-pr" not in treatment.skills
        for name in treatment.skills:
            assert name not in EXCLUDED_SKILLS


def test_every_task_has_oracle_or_rubric() -> None:
    for task in TASKS:
        assert task.oracle in {"hidden_tests", "static_checks", "rubric_blind", "mixed"}
        assert task.oracle_spec.strip()
        assert "baseline" in task.treatment_names
        assert task.single_name in task.treatment_names
        assert task.realistic_name in task.treatment_names


def test_ui_and_design_have_independent_contrast() -> None:
    ui = next(task for task in TASKS if task.id == "ui-disclosure")
    design = next(task for task in TASKS if task.id == "ds-landing-hero")
    assert "contrast-design" in ui.treatment_names
    assert "contrast-ui" in design.treatment_names
    assert TREATMENTS["contrast-design"].skills == ("eric-design",)
    assert TREATMENTS["contrast-ui"].skills == ("eric-ui",)


def test_frozen_skill_trees_match_catalog() -> None:
    root = repo_root()
    rows = freeze_skills(root)
    assert [row["name"] for row in rows] == list(INCLUDED_SKILLS)
    for row in rows:
        path = root / row["path"].lstrip("./")
        assert path.is_dir()
        assert (path / "SKILL.md").is_file()
        assert row["digest"] == sha256_tree(path)
        assert row["digest"].startswith("sha256:")


def test_screen_yaml_dry_run_matches_catalog_and_budget_gate() -> None:
    root = repo_root()
    for stage, meta in STAGE_ISSUES.items():
        spec = load_yaml(root / meta["config"])
        plan = expand(spec, root)
        guard(plan)
        expected = screen_plan(stage)
        assert plan.track == "B"
        assert plan.repeat == 1
        assert {cell.agent for cell in plan.cells} == {"codex"}
        assert {cell.model for cell in plan.cells} == {MODEL_SNAPSHOT}
        assert plan.n_task_units == 1
        assert plan.n_trials == expected.n_trials == plan.n_cells
        assert plan.estimated_usd == expected.estimated_usd
        assert plan.budget_usd == expected.budget_usd
        assert plan.n_trials <= plan.max_trials
        over = dict(spec)
        over["budget_usd"] = 1
        with pytest.raises(ExperimentError, match="over budget_usd"):
            guard(expand(over, root))


def test_no_cartesian_of_all_skills() -> None:
    n_cells = sum(screen_plan(stage).n_trials for stage in ("8A", "8B", "8C", "8D"))
    n_tasks = len(TASKS)
    n_skills = len(INCLUDED_SKILLS)
    assert n_cells < n_tasks * n_skills * 3
    assert n_cells == len(coverage_rows())


def test_stage7_rubric_packet_is_blind() -> None:
    packet = stage7_rubric_packet(instruction="x", files={"a.ts": "a"}, task_id="ui-privacy")
    blob = str(packet)
    assert "codex" not in blob
    assert MODEL_SNAPSHOT not in blob
    assert "baseline" not in blob
    ids = {axis["id"] for axis in packet["axes"]}
    assert {"review_tp", "visual_quality", "overengineering", "cost_usd"} <= ids
    assert packet["no_composite_total"] is True


def test_manifest_revision_and_hard_gates() -> None:
    payload = manifest(repo_root())
    assert payload["revision"] == REVISION
    assert payload["hard_gates"]["do_not_start_without_budget_confirmation"] is True
    assert payload["hard_gates"]["single_agent"] == "codex"
    assert payload["screening"]["n_trials"] == sum(
        screen_plan(stage).n_trials for stage in ("8A", "8B", "8C", "8D")
    )


def test_experiment_spec_binds_real_task_on_each_cell() -> None:
    spec = experiment_spec("8C", repo_root())
    tasks = {cell["kwargs"]["asb_task"] for cell in spec["cells"]}
    assert tasks <= {f"tasks/stage7/{task.id}" for task in TASKS}
    assert spec["tasks"] == ["tasks/stage7/_anchor"]
    assert Path(repo_root() / "tasks/stage7/_anchor/task.toml").is_file()
