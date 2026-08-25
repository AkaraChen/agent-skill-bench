import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agent_skill_bench.cli import main
from agent_skill_bench.constants import repo_root
from agent_skill_bench.experiment import (
    ExperimentError,
    compile_harbor_job,
    dump_harbor_job,
    expand,
    load_yaml,
    resolved_manifest,
)
from agent_skill_bench.policy import (
    guard_policy,
    inject_secrets,
    list_expired_jobs,
    redact_mapping,
    secret_allowlist_record,
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


SENTINEL = "SENTINEL-SECRET-VALUE"


def test_generated_yaml_does_not_contain_sentinel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAYTONA_API_KEY", SENTINEL)
    spec = load_yaml(repo_root() / "configs/experiments/stage4-cloud.example.yaml")
    plan = expand(spec, repo_root())
    dumped = dump_harbor_job(compile_harbor_job(plan, "A-cloud"))
    assert SENTINEL not in dumped
    env = (compile_harbor_job(plan, "A-cloud").get("environment") or {}).get("env") or {}
    assert "DAYTONA_API_KEY" not in env
    assert inject_secrets(plan.secret_allowlist)["DAYTONA_API_KEY"] == SENTINEL
    record = secret_allowlist_record(plan.secret_allowlist)
    assert record["present"]["DAYTONA_API_KEY"] == "[redacted]"
    assert SENTINEL not in str(record)
    assert SENTINEL not in str(resolved_manifest(plan))


def test_compile_strips_secret_keys_already_in_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAYTONA_API_KEY", SENTINEL)
    spec = load_yaml(repo_root() / "configs/experiments/stage4-cloud.example.yaml")
    spec["environment"]["env"] = {"DAYTONA_API_KEY": SENTINEL, "SAFE_FLAG": "1"}
    plan = expand(spec, repo_root())
    dumped = dump_harbor_job(compile_harbor_job(plan, "A-cloud"))
    assert SENTINEL not in dumped
    env = compile_harbor_job(plan, "A-cloud")["environment"]["env"]
    assert env == {"SAFE_FLAG": "1"}


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


def test_resume_restores_secret_names_without_experiment_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    from agent_skill_bench import run as run_mod

    monkeypatch.setenv("DAYTONA_API_KEY", SENTINEL)
    monkeypatch.setattr(run_mod, "repo_root", lambda: tmp_path)
    job = tmp_path / "jobs" / "A-interrupted"
    job.mkdir(parents=True)
    generated = tmp_path / "jobs" / ".generated"
    generated.mkdir(parents=True)
    (generated / "A-interrupted.manifest.json").write_text(
        '{"secret_allowlist": ["DAYTONA_API_KEY"]}\n'
    )
    captured: dict[str, dict[str, str]] = {}

    class FakeProc:
        pid = 7

        def wait(self) -> int:
            return 0

    def fake_popen(cmd, cwd=None, env=None):
        captured["env"] = env
        return FakeProc()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    run_mod.resume_job(job)
    assert captured["env"]["DAYTONA_API_KEY"] == SENTINEL
    assert (job / "asb_experiment.json").exists() is False


def test_secret_sidecar_is_written_before_harbor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    from agent_skill_bench import run as run_mod

    monkeypatch.setenv("DAYTONA_API_KEY", SENTINEL)
    monkeypatch.setattr(run_mod, "repo_root", lambda: tmp_path)
    spec = load_yaml(repo_root() / "configs/experiments/stage4-cloud.example.yaml")
    (tmp_path / "configs" / "experiments").mkdir(parents=True)
    import yaml

    config = tmp_path / "configs" / "experiments" / "cloud.yaml"
    config.write_text(yaml.safe_dump(spec, sort_keys=False))
    seen: dict[str, str] = {}

    class FakeProc:
        pid = 3

        def wait(self) -> int:
            jobs = tmp_path / "jobs"
            generated = list((jobs / ".generated").glob("*.yaml"))
            assert generated
            seen["yaml"] = generated[0].read_text()
            secrets = list(jobs.glob("*/asb_secrets.json"))
            assert secrets
            seen["secrets"] = secrets[0].read_text()
            experiment = list(jobs.glob("*/asb_experiment.json"))
            assert experiment
            seen["experiment"] = experiment[0].read_text()
            return 0

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: FakeProc())
    monkeypatch.setattr(run_mod, "expand", lambda _spec, _root: expand(spec, repo_root()))
    job_dir = run_mod.run_job(config)
    assert job_dir is not None
    assert SENTINEL not in seen["yaml"]
    assert SENTINEL not in seen["secrets"]
    assert SENTINEL not in seen["experiment"]
    assert "DAYTONA_API_KEY" in seen["secrets"]
