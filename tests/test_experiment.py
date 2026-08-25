from pathlib import Path

import pytest
import yaml

from agent_skill_bench.constants import repo_root
from agent_skill_bench.cli import main
from agent_skill_bench.experiment import (
    ExperimentError,
    compile_harbor_job,
    expand,
    format_dry_run,
    guard,
    load_yaml,
    pairing_for,
    resolved_manifest,
)
from agent_skill_bench.fingerprint import sha256_tree


def _smoke_spec() -> dict:
    return load_yaml(repo_root() / "configs/experiments/smoke-2x2.yaml")


def test_smoke_expands_to_twenty_paired_trials() -> None:
    plan = expand(_smoke_spec(), repo_root())
    assert plan.track == "A"
    assert plan.n_cells == 4
    assert plan.n_trials == 20
    assert plan.pairs == [("baseline", "candidate")]
    agents = {(cell.agent, cell.treatment) for cell in plan.cells}
    assert agents == {
        ("naive-solver", "baseline"),
        ("naive-solver", "candidate"),
        ("skill-solver", "baseline"),
        ("skill-solver", "candidate"),
    }
    assert any(item["name"] == "test-first" and item["digest"].startswith("sha256:") for item in plan.skill_hashes)
    guard(plan)
    text = format_dry_run(plan)
    assert "trials: 20" in text
    assert "estimated_usd: unknown" in text


def test_max_trials_blocks_cartesian_explosion() -> None:
    spec = _smoke_spec()
    spec["max_trials"] = 5
    plan = expand(spec, repo_root())
    with pytest.raises(ExperimentError, match="Refusing to run 20 trials"):
        guard(plan)


def test_budget_blocks_when_usd_known() -> None:
    spec = _smoke_spec()
    spec["usd_per_trial"] = 1.5
    spec["budget_usd"] = 10
    plan = expand(spec, repo_root())
    with pytest.raises(ExperimentError, match="over budget_usd"):
        guard(plan)


def test_exclude_and_include() -> None:
    spec = _smoke_spec()
    spec["exclude"] = [{"agent": "naive-solver"}]
    plan = expand(spec, repo_root())
    assert plan.n_cells == 2
    assert {cell.agent for cell in plan.cells} == {"skill-solver"}
    assert {cell.treatment for cell in plan.cells} == {"baseline", "candidate"}

    spec["include"] = [{"treatment": "baseline"}]
    spec["exclude"] = []
    spec["pairs"] = []
    plan = expand(spec, repo_root())
    assert plan.n_cells == 2
    assert {cell.treatment for cell in plan.cells} == {"baseline"}


def test_explicit_cells_skip_cartesian() -> None:
    spec = _smoke_spec()
    spec["pairs"] = []
    spec["cells"] = [
        {"agent": "skill-solver", "treatment": "candidate"},
        {"agent": "naive-solver", "treatment": "baseline"},
    ]
    plan = expand(spec, repo_root())
    assert [(cell.agent, cell.treatment) for cell in plan.cells] == [
        ("skill-solver", "candidate"),
        ("naive-solver", "baseline"),
    ]
    assert plan.n_trials == 10


def test_sample_is_seed_stable() -> None:
    spec = _smoke_spec()
    spec["pairs"] = []
    spec["sample"] = 2
    a = [ (c.agent, c.treatment) for c in expand(spec, repo_root()).cells ]
    b = [ (c.agent, c.treatment) for c in expand(spec, repo_root()).cells ]
    assert a == b
    assert len(a) == 2


def test_unknown_agent_rejected() -> None:
    spec = _smoke_spec()
    spec["agents"] = [{"name": "not-a-real-agent"}]
    with pytest.raises(ExperimentError, match="Unknown agent"):
        expand(spec, repo_root())


def test_harbor_builtin_and_acp_do_not_need_import_path() -> None:
    spec = _smoke_spec()
    spec["track"] = "B"
    spec["agents"] = [{"name": "codex"}, {"name": "acp:pi"}]
    spec["treatments"] = spec["treatments"][:1]
    spec["pairs"] = []
    plan = expand(spec, repo_root())
    kinds = {cell.agent: cell.kind for cell in plan.cells}
    assert kinds == {"codex": "harbor", "acp:pi": "acp"}
    job = compile_harbor_job(plan, "B-test")
    names = [agent["name"] for agent in job["agents"]]
    assert names == ["codex", "acp:pi"]
    assert "import_path" not in job["agents"][0]
    assert job["agents"][0]["kwargs"]["asb_track"] == "B"


def test_compile_smoke_is_valid_harbor_job() -> None:
    plan = expand(_smoke_spec(), repo_root())
    job = compile_harbor_job(plan, "A-smoke-2x2")
    assert job["n_attempts"] == 1
    assert len(job["agents"]) == 4
    assert len(job["tasks"]) == 5
    dumped = yaml.safe_dump(job)
    roundtrip = yaml.safe_load(dumped)
    assert roundtrip["agents"][0]["import_path"].endswith("NaiveSolver")
    assert job["timeout_multiplier"] == 1.0
    assert job["n_concurrent_trials"] == 2


def test_track_b_example_stays_under_cap() -> None:
    spec = load_yaml(repo_root() / "configs/experiments/track-b.example.yaml")
    plan = expand(spec, repo_root())
    guard(plan)
    assert plan.track == "B"
    assert plan.n_trials <= plan.max_trials
    assert {cell.agent for cell in plan.cells} == {"codex", "claude-code"}
    assert {cell.treatment for cell in plan.cells} == {"baseline", "candidate"}


def test_agent_kwargs_are_compiled_into_harbor_job() -> None:
    spec = _smoke_spec()
    spec["agents"][0]["kwargs"] = {"temperature": 0.7, "max_turns": 4}
    plan = expand(spec, repo_root())
    job = compile_harbor_job(plan, "A-kwargs")
    naive = [agent for agent in job["agents"] if agent["name"] == "naive-solver"]
    assert naive
    assert naive[0]["kwargs"]["temperature"] == 0.7
    assert naive[0]["kwargs"]["max_turns"] == 4
    assert naive[0]["kwargs"]["asb_seed"] == 42


def test_broken_pairs_after_filter_are_rejected() -> None:
    spec = _smoke_spec()
    spec["include"] = [{"treatment": "baseline"}]
    with pytest.raises(ExperimentError, match="incomplete"):
        expand(spec, repo_root())


def test_sample_with_pairs_keeps_both_arms() -> None:
    spec = _smoke_spec()
    spec["sample"] = 1
    plan = expand(spec, repo_root())
    assert plan.n_cells == 2
    agents = {cell.agent for cell in plan.cells}
    assert len(agents) == 1
    assert {cell.treatment for cell in plan.cells} == {"baseline", "candidate"}
    keys = {pairing_for(cell, plan.pairs) for cell in plan.cells}
    assert len(keys) == 1
    pair_id, pairing_key = next(iter(keys))
    assert pair_id == "baseline__candidate"
    assert pairing_key.startswith("sha256:")
    job = compile_harbor_job(plan, "A-pairs")
    assert {agent["kwargs"]["asb_pairing_key"] for agent in job["agents"]} == {pairing_key}


def test_resolved_manifest_is_reproducible() -> None:
    plan = expand(_smoke_spec(), repo_root())
    manifest = resolved_manifest(plan)
    assert manifest["seed"] == 42
    assert manifest["repeat"] == 1
    assert manifest["tasks"]
    assert manifest["pairs"] == [{"id": "baseline__candidate", "left": "baseline", "right": "candidate"}]
    assert manifest["n_trials"] == 20
    assert manifest["selection"]["sample"] is None
    assert len(manifest["cells"]) == 4


def test_skill_tree_hash_includes_nested_files(tmp_path: Path) -> None:
    skill = tmp_path / "demo"
    skill.mkdir()
    (skill / "SKILL.md").write_text("# demo\n")
    before = sha256_tree(skill)
    (skill / "scripts").mkdir()
    (skill / "scripts" / "run.sh").write_text("echo hi\n")
    after = sha256_tree(skill)
    assert before != after
    spec = _smoke_spec()
    spec["treatments"][1]["skills"] = [str(skill)]
    plan = expand(spec, repo_root())
    assert any(item["digest"] == after for item in plan.skill_hashes)


def test_budget_unknown_unit_price_is_refused() -> None:
    spec = _smoke_spec()
    spec["budget_usd"] = 10
    spec["usd_per_trial"] = 0
    plan = expand(spec, repo_root())
    with pytest.raises(ExperimentError, match="usd_per_trial is unknown"):
        guard(plan)


def test_resume_dry_run_does_not_start_harbor() -> None:
    assert main(["run", "--resume", "jobs/A-smoke-missing", "--dry-run"]) == 0


def test_stratified_sample_by_treatment() -> None:
    spec = _smoke_spec()
    spec["pairs"] = []
    spec["sample"] = {"n": 1, "by": "treatment"}
    plan = expand(spec, repo_root())
    counts: dict[str, int] = {}
    for cell in plan.cells:
        counts[cell.treatment] = counts.get(cell.treatment, 0) + 1
    assert counts == {"baseline": 1, "candidate": 1}
