import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agent_skill_bench.cli import main
from agent_skill_bench.constants import repo_root
from agent_skill_bench.experiment import ExperimentError, expand, load_yaml
from agent_skill_bench.policy import (
    guard_policy,
    list_expired_jobs,
    redact_mapping,
    secret_leaks,
)
from agent_skill_bench.run import cancel_job


def test_patch_cache_is_rejected() -> None:
    spec = load_yaml(repo_root() / "configs/experiments/smoke-2x2.yaml")
    spec["policy"] = {"cache_scope": "patch"}
    plan = expand(spec, repo_root())
    with pytest.raises(ExperimentError, match="reuse old patches"):
        guard_policy(plan)


def test_unknown_environment_is_rejected() -> None:
    spec = load_yaml(repo_root() / "configs/experiments/smoke-2x2.yaml")
    spec["environment"] = {"type": "shared-host"}
    plan = expand(spec, repo_root())
    with pytest.raises(ExperimentError, match="isolated"):
        guard_policy(plan)


def test_cloud_example_is_an_isolated_worker() -> None:
    spec = load_yaml(repo_root() / "configs/experiments/stage4-cloud.example.yaml")
    plan = expand(spec, repo_root())
    guard_policy(plan)
    assert plan.environment["type"] == "daytona"
    assert plan.secret_allowlist == ("DAYTONA_API_KEY",)
    assert plan.n_concurrent == 4


def test_secrets_are_redacted_not_stored() -> None:
    payload = {"OPENAI_API_KEY": "sk-live", "model": "snap", "secret_allowlist": ["OPENAI_API_KEY"]}
    redacted = redact_mapping(payload, ("OPENAI_API_KEY",))
    assert redacted["OPENAI_API_KEY"] == "[redacted]"
    assert redacted["secret_allowlist"] == ["OPENAI_API_KEY"]
    assert secret_leaks({"agent": {"api_key": "sk-live"}}) == ["agent.api_key"]
    assert secret_leaks(redacted, ("OPENAI_API_KEY",)) == []


def test_retention_lists_old_jobs(tmp_path: Path) -> None:
    old = tmp_path / "old-job"
    new = tmp_path / "new-job"
    old.mkdir()
    new.mkdir()
    cutoff = datetime.now(timezone.utc)
    old_mtime = (cutoff - timedelta(days=40)).timestamp()
    (old / "marker").write_text("x")
    (new / "marker").write_text("x")
    os.utime(old, (old_mtime, old_mtime))
    expired = list_expired_jobs(tmp_path, 30, now=cutoff)
    assert old in expired
    assert new not in expired


def test_cancel_writes_marker(tmp_path: Path) -> None:
    job = tmp_path / "jobs" / "running"
    marker = cancel_job(job)
    assert (marker / "asb_cancelled.json").exists()
    assert main(["cancel", str(job)]) == 0
