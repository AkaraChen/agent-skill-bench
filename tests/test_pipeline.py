from agent_skill_bench.cli import main
from agent_skill_bench.constants import repo_root
from agent_skill_bench.experiment import expand, guard, load_yaml
from agent_skill_bench.pipeline import confirm_spec, plan_pipeline, rank_treatments
from agent_skill_bench.policy import guard_policy


def test_screen_stays_under_cap() -> None:
    spec = load_yaml(repo_root() / "configs/experiments/stage4-screen.yaml")
    plan = expand(spec, repo_root())
    guard(plan)
    guard_policy(plan)
    assert plan.n_trials == 10
    assert {cell.treatment for cell in plan.cells} == {"baseline", "candidate"}
    assert len({cell.agent for cell in plan.cells}) == 1


def test_confirm_repeats_only_ranked_treatments() -> None:
    screen = load_yaml(repo_root() / "configs/experiments/stage4-screen.yaml")
    rows = [
        {"treatment": "candidate", "failure_class": "ok", "reward": 1, "infra_error": False},
        {"treatment": "candidate", "failure_class": "ok", "reward": 1, "infra_error": False},
        {"treatment": "baseline", "failure_class": "model", "reward": 0, "infra_error": False},
    ]
    ranked = rank_treatments(rows, 1)
    assert ranked == ["candidate"]
    spec = confirm_spec(screen, ranked, repeat=3, max_trials=60)
    spec.pop("sample", None)
    plan = expand(spec, repo_root())
    guard(plan)
    assert plan.repeat == 3
    assert {cell.treatment for cell in plan.cells} == {"candidate"}
    assert plan.n_trials == 30


def test_pipeline_dry_run_cli() -> None:
    payload = plan_pipeline(
        load_yaml(repo_root() / "configs/experiments/stage4-pipeline.yaml"),
        load_yaml(repo_root() / "configs/experiments/stage4-screen.yaml"),
        repo_root(),
        rows=None,
    )
    assert payload["screen"]["n_trials"] == 10
    assert payload["confirm"]["repeat"] == 3
    assert payload["confirm"]["n_trials"] <= 60
    assert main(
        [
            "pipeline",
            "--config",
            str(repo_root() / "configs/experiments/stage4-pipeline.yaml"),
            "--dry-run",
        ]
    ) == 0
