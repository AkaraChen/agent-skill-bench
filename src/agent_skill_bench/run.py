from __future__ import annotations

import json
import os
import signal
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from agent_skill_bench.constants import repo_root
from agent_skill_bench.experiment import (
    ExperimentError,
    compile_harbor_job,
    dump_harbor_job,
    expand,
    format_dry_run,
    guard,
    is_experiment,
    load_yaml,
    passthrough_trial_count,
    resolved_manifest,
)
from agent_skill_bench.ledger import load_ledger, save_ledger
from agent_skill_bench.policy import guard_policy, redact_mapping


DEFAULT_EXPERIMENT = Path("configs/experiments/smoke-2x2.yaml")


def _pid_path(root: Path, job_name: str) -> Path:
    generated = root / "jobs" / ".generated"
    generated.mkdir(parents=True, exist_ok=True)
    return generated / f"{job_name}.pid"


def _harbor_run(config: Path, n_concurrent: int, job_name: str) -> Path:
    root = repo_root()
    jobs_dir = root / "jobs"
    jobs_dir.mkdir(exist_ok=True)
    cmd = [
        "harbor",
        "run",
        "-c",
        str(config),
        "-o",
        str(jobs_dir),
        "--job-name",
        job_name,
        "-n",
        str(n_concurrent),
        "--yes",
    ]
    proc = subprocess.Popen(cmd, cwd=root)
    pid_path = _pid_path(root, job_name)
    pid_path.write_text(str(proc.pid))
    try:
        code = proc.wait()
    finally:
        if pid_path.exists():
            pid_path.unlink()
    if code != 0:
        raise subprocess.CalledProcessError(code, cmd)
    return jobs_dir / job_name


def resume_job(job_path: Path) -> Path:
    path = job_path if job_path.is_absolute() else repo_root() / job_path
    if not path.exists():
        raise FileNotFoundError(f"Job directory not found: {path}")
    # Harbor skips completed trials. Ledger keeps billed/scored trial_ids so
    # a later summarize cannot double-count them.
    save_ledger(path, load_ledger(path))
    subprocess.run(["harbor", "job", "resume", "-p", str(path)], check=True)
    return path


def cancel_job(job_path: Path) -> Path:
    root = repo_root()
    path = job_path if job_path.is_absolute() else root / job_path
    path.mkdir(parents=True, exist_ok=True)
    marker = {
        "cancelled_at": datetime.now(timezone.utc).isoformat(),
        "job": path.name,
    }
    (path / "asb_cancelled.json").write_text(json.dumps(marker, indent=2) + "\n")
    pid_path = _pid_path(root, path.name)
    if pid_path.exists():
        try:
            pid = int(pid_path.read_text().strip())
        except ValueError:
            pid = None
        if pid:
            try:
                os.kill(pid, signal.SIGINT)
            except OSError:
                pass
    return path


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def run_job(
    config_path: Path | None = None,
    n_concurrent: int | None = None,
    dry_run: bool = False,
    resume: Path | None = None,
) -> Path | None:
    root = repo_root()
    if resume is not None:
        if dry_run:
            print(f"resume: {resume}")
            return None
        return resume_job(resume)

    config = config_path or (root / DEFAULT_EXPERIMENT)
    if not config.exists():
        raise FileNotFoundError(f"Job config not found: {config}")

    spec = load_yaml(config)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if is_experiment(spec):
        plan = expand(spec, root)
        print(format_dry_run(plan))
        guard(plan)
        guard_policy(plan)
        concurrent = n_concurrent or plan.n_concurrent
        if dry_run:
            return None
        if plan.assemble_sealed:
            from agent_skill_bench.holdout import assemble_dataset

            assemble_dataset(root, plan.assembled_path)
        job_name = f"{plan.track}-{plan.name}-{stamp}"
        generated_dir = root / "jobs" / ".generated"
        generated_dir.mkdir(parents=True, exist_ok=True)
        generated = generated_dir / f"{job_name}.yaml"
        manifest = redact_mapping(resolved_manifest(plan), plan.secret_allowlist)
        generated.write_text(dump_harbor_job(compile_harbor_job(plan, job_name)))
        _write_json(generated_dir / f"{job_name}.manifest.json", manifest)
        job_dir = _harbor_run(generated, concurrent, job_name)
        _write_json(job_dir / "asb_experiment.json", manifest)
        save_ledger(job_dir, load_ledger(job_dir))
        return job_dir

    n_trials = passthrough_trial_count(spec)
    print(f"passthrough Harbor job: {config}")
    print(f"trials: {n_trials} (agents × tasks × n_attempts)")
    if dry_run:
        return None
    job_name = spec.get("job_name") or f"job-{stamp}"
    concurrent = n_concurrent or int(spec.get("n_concurrent_trials") or 2)
    return _harbor_run(config, concurrent, job_name)


def run_smoke(config_path: Path | None = None, n_concurrent: int = 2) -> Path:
    job_dir = run_job(config_path, n_concurrent=n_concurrent, dry_run=False)
    if job_dir is None:
        raise ExperimentError("run_smoke produced no job directory")
    return job_dir
