from agent_skill_bench.constants import repo_root
from agent_skill_bench.dataset import revision_payload
from agent_skill_bench.experiment import compile_harbor_job, expand, guard, load_yaml
from agent_skill_bench.holdout import KINDS, LANGUAGES, load_manifest
from agent_skill_bench.retry_policy import harbor_retry


def test_private_manifest_is_stratified() -> None:
    tasks = load_manifest()["tasks"]
    assert 20 <= len(tasks) <= 40
    kinds = {item["kind"] for item in tasks}
    langs = {item["language"] for item in tasks}
    assert kinds == set(KINDS)
    assert langs == set(LANGUAGES)
    assert {item["difficulty"] for item in tasks} == {"easy", "medium", "hard"}
    assert {item["size"] for item in tasks} == {"tiny", "small"}
    for item in tasks:
        for key in (
            "instruction_digest",
            "environment_digest",
            "tests_digest",
            "gold_digest",
            "alt_digest",
            "negative_digest",
        ):
            assert item[key].startswith("sha256:")


def test_revision_is_traceable() -> None:
    payload = revision_payload()
    assert payload["dataset_revision"] == "2026.08.25"
    assert payload["n_private_tasks"] == 24
    assert payload["scorer_version"]
    assert payload["image"].startswith("python:3.12.11-slim-bookworm@sha256:")
    assert "authored" in payload["cutoff_policy"] or "2026" in payload["authored_at"]
    on_disk = (repo_root() / "datasets" / "revision.toml").read_text()
    assert payload["dataset_revision"] in on_disk


def test_retry_policy_is_infra_only() -> None:
    policy = harbor_retry()
    assert "SandboxBuildFailedError" in policy["include_exceptions"]
    assert "AgentTimeoutError" in policy["exclude_exceptions"]
    assert "AgentSetupError" in policy["exclude_exceptions"]


def test_holdout_experiment_expands() -> None:
    spec = load_yaml(repo_root() / "configs/experiments/stage3-holdout.yaml")
    plan = expand(spec, repo_root())
    guard(plan)
    assert plan.n_task_units == 24
    assert plan.n_trials == 24
    assert plan.retry["max_retries"] == 2
    job = compile_harbor_job(plan, "A-holdout")
    assert job["agents"][0]["name"] == "oracle"
    assert job["datasets"][0]["path"] == "tasks/private"
    assert "SandboxBuildFailedError" in job["retry"]["include_exceptions"]


def test_public_subset_dry_run_is_bounded() -> None:
    spec = load_yaml(repo_root() / "configs/experiments/stage3-public-subset.yaml")
    plan = expand(spec, repo_root())
    guard(plan)
    assert plan.n_task_units == 9
    assert plan.n_trials == 9
    names = [item.name for item in plan.datasets]
    assert names == ["harbor/hello-world", "terminal-bench/terminal-bench-2"]
    tb = plan.datasets[1]
    assert tb.ref and tb.ref.startswith("sha256:")
    assert len(tb.task_names) == 8
    assert "terminal-bench/make-mips-interpreter" in tb.task_names
    job = compile_harbor_job(plan, "A-public")
    assert job["datasets"][1]["ref"].startswith("sha256:")
    assert job["datasets"][1]["task_names"] == list(tb.task_names)
