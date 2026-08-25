from pathlib import Path

from agent_skill_bench.cli import main
from agent_skill_bench.constants import repo_root
from agent_skill_bench.experiment import expand, guard, load_yaml
from agent_skill_bench.pipeline import confirm_spec, plan_pipeline, rank_treatments, run_pipeline
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


def test_confirm_overrides_narrow_models_and_tasks() -> None:
    screen = load_yaml(repo_root() / "configs/experiments/stage5-screen.yaml")
    spec = confirm_spec(
        screen,
        ["baseline", "bundle"],
        repeat=3,
        max_trials=150,
        overrides={
            "models": ["deterministic/beta@2026-08-26", "deterministic/gamma@2026-08-26"],
            "tasks": ["tasks/reverse-string", "tasks/slugify"],
            "datasets": [
                {
                    "path": "cache/asb/assembled/holdout",
                    "task_names": ["clamp-range", "path-jail"],
                }
            ],
        },
    )
    plan = expand(spec, repo_root())
    guard(plan)
    assert plan.repeat == 3
    assert {cell.treatment for cell in plan.cells} == {"baseline", "bundle"}
    assert {cell.model for cell in plan.cells} == {
        "deterministic/beta@2026-08-26",
        "deterministic/gamma@2026-08-26",
    }
    assert plan.n_trials == 144


def test_stage5_screen_under_cap() -> None:
    spec = load_yaml(repo_root() / "configs/experiments/stage5-screen.yaml")
    plan = expand(spec, repo_root())
    guard(plan)
    guard_policy(plan)
    assert plan.n_trials == 96
    assert {cell.treatment for cell in plan.cells} == {"baseline", "plan", "skill", "bundle"}
    assert len({cell.model for cell in plan.cells}) == 3
    assert len({cell.agent for cell in plan.cells}) == 3


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


def test_pipeline_runs_screen_then_confirm(tmp_path: Path) -> None:
    root = repo_root()
    pipeline = load_yaml(root / "configs/experiments/stage4-pipeline.yaml")
    pipeline["confirm"]["top_k"] = 1
    screen = load_yaml(root / "configs/experiments/stage4-screen.yaml")
    screen_path = root / "configs/experiments/stage4-screen.yaml"
    calls: list[Path] = []
    jobs = tmp_path / "jobs"
    jobs.mkdir()

    def run_fn(config: Path) -> Path:
        calls.append(config)
        job = jobs / f"job-{len(calls)}"
        job.mkdir()
        return job

    def rows_fn(job_dir: Path) -> list[dict]:
        if job_dir.name == "job-1":
            return [
                {
                    "treatment": "candidate",
                    "failure_class": "ok",
                    "reward": 1,
                    "infra_error": False,
                },
                {
                    "treatment": "baseline",
                    "failure_class": "model",
                    "reward": 0,
                    "infra_error": False,
                },
            ]
        return []

    payload = run_pipeline(
        pipeline,
        screen,
        tmp_path,
        screen_path=screen_path,
        run_fn=run_fn,
        rows_fn=rows_fn,
    )
    assert payload["executed"] is True
    assert len(calls) == 2
    assert calls[0] == screen_path
    confirm_spec_path = Path(payload["confirm"]["spec_path"])
    assert calls[1] == confirm_spec_path
    confirm = load_yaml(confirm_spec_path)
    assert confirm["repeat"] == 3
    assert {item["name"] for item in confirm["treatments"]} == {"candidate"}
    assert payload["ranked_treatments"] == ["candidate"]
    assert payload["screen"]["job_dir"].endswith("job-1")
    assert payload["confirm"]["job_dir"].endswith("job-2")


def test_pipeline_skips_screen_when_results_given(tmp_path: Path) -> None:
    root = repo_root()
    calls: list[Path] = []

    def run_fn(config: Path) -> Path:
        calls.append(config)
        job = tmp_path / "confirm-job"
        job.mkdir()
        return job

    pipeline = load_yaml(root / "configs/experiments/stage4-pipeline.yaml")
    pipeline["confirm"]["top_k"] = 1
    payload = run_pipeline(
        pipeline,
        load_yaml(root / "configs/experiments/stage4-screen.yaml"),
        tmp_path,
        screen_path=root / "configs/experiments/stage4-screen.yaml",
        rows=[
            {"treatment": "candidate", "failure_class": "ok", "reward": 1, "infra_error": False},
            {"treatment": "baseline", "failure_class": "model", "reward": 0, "infra_error": False},
        ],
        run_fn=run_fn,
        rows_fn=lambda _job: [],
    )
    assert len(calls) == 1
    assert payload["screen"]["job_dir"] is None
    assert payload["executed"] is True
    assert payload["ranked_treatments"] == ["candidate"]
