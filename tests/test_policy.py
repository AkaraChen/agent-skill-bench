import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agent_skill_bench.cli import main
from agent_skill_bench.constants import repo_root
from agent_skill_bench.experiment import (
    ExperimentError,
    compile_harbor_job,
    expand,
    load_yaml,
    resolved_manifest,
)
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


def test_compile_injects_allowlisted_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAYTONA_API_KEY", "daytona-secret")
    spec = load_yaml(repo_root() / "configs/experiments/stage4-cloud.example.yaml")
    plan = expand(spec, repo_root())
    job = compile_harbor_job(plan, "A-cloud")
    assert job["environment"]["env"]["DAYTONA_API_KEY"] == "daytona-secret"
    assert "daytona-secret" not in str(resolved_manifest(plan))


def test_compile_omits_missing_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DAYTONA_API_KEY", raising=False)
    spec = load_yaml(repo_root() / "configs/experiments/stage4-cloud.example.yaml")
    plan = expand(spec, repo_root())
    job = compile_harbor_job(plan, "A-cloud")
    env = (job["environment"] or {}).get("env") or {}
    assert "DAYTONA_API_KEY" not in env


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


def test_resume_records_pid_so_cancel_can_signal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import signal
    import subprocess

    from agent_skill_bench import run as run_mod

    job = tmp_path / "jobs" / "A-resume"
    job.mkdir(parents=True)
    (job / "asb_experiment.json").write_text('{"secret_allowlist": []}\n')
    monkeypatch.setattr(run_mod, "repo_root", lambda: tmp_path)
    pid_path = tmp_path / "jobs" / ".generated" / "A-resume.pid"
    seen: dict[str, str] = {}

    class FakeProc:
        pid = 4242

        def wait(self) -> int:
            seen["pid"] = pid_path.read_text()
            return 0

    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: FakeProc())
    run_mod.resume_job(job)
    assert seen["pid"] == "4242"
    assert not pid_path.exists()

    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text("4242")
    killed: list[tuple[int, int]] = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: killed.append((pid, sig)))
    run_mod.cancel_job(job)
    assert killed == [(4242, signal.SIGINT)]
