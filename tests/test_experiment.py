from pathlib import Path

import pytest
import yaml

from agent_skill_bench.constants import repo_root
from agent_skill_bench.experiment import (
    ExperimentError,
    compile_harbor_job,
    expand,
    format_dry_run,
    guard,
    load_yaml,
)


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

    spec["include"] = [{"treatment": "baseline"}]
    spec["exclude"] = []
    plan = expand(spec, repo_root())
    assert plan.n_cells == 2
    assert {cell.treatment for cell in plan.cells} == {"baseline"}


def test_explicit_cells_skip_cartesian() -> None:
    spec = _smoke_spec()
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


def test_track_b_example_stays_under_cap() -> None:
    spec = load_yaml(repo_root() / "configs/experiments/track-b.example.yaml")
    plan = expand(spec, repo_root())
    guard(plan)
    assert plan.track == "B"
    assert plan.n_trials <= plan.max_trials
    assert {cell.agent for cell in plan.cells} == {"codex", "claude-code"}
