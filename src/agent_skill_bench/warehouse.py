"""Result warehouse: every row points at its manifest and raw artifacts.

Patches are stored per trial_dir. The same config fingerprint in two jobs
never shares a patch URI.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_skill_bench.fingerprint import sha256_file, sha256_tree
from agent_skill_bench.constants import repo_root
from agent_skill_bench.ledger import load_ledger
from agent_skill_bench.policy import network_audit, redact_mapping

TRAJECTORY_NAMES = (
    "trajectory.json",
    "trajectory.jsonl",
    "atif.json",
    "trace.json",
)


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _first_file(directory: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def _patch_digest(trial_dir: Path) -> str:
    artifacts = trial_dir / "artifacts"
    if artifacts.is_dir():
        digest = sha256_tree(artifacts)
        if digest:
            return digest
    workspace = trial_dir / "agent" / "workspace.json"
    if workspace.is_file():
        return sha256_file(workspace)
    return ""


def _tool_calls(result: dict[str, Any], trial_dir: Path) -> int | None:
    agent = result.get("agent_result") or {}
    metadata = agent.get("metadata") or {}
    for key in ("n_tool_calls", "tool_calls", "n_actions"):
        value = metadata.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, list):
            return len(value)
    agent_dir = trial_dir / "agent"
    if not agent_dir.is_dir():
        return None
    total = 0
    found = False
    for path in agent_dir.rglob("*"):
        if not path.is_file() or path.suffix not in {".json", ".jsonl"}:
            continue
        text = path.read_text(errors="replace")
        if "tool_call" in text or "toolCall" in text:
            found = True
            total += text.count("tool_call") + text.count("toolCall")
    return total if found else None


def trial_artifacts(trial_dir: Path, root: Path | None = None) -> dict[str, Any]:
    base = root or repo_root()
    result_path = trial_dir / "result.json"
    if not result_path.exists():
        result_path = trial_dir / "results.json"
    config_path = trial_dir / "config.json"
    lock_path = trial_dir / "lock.json"
    manifest_path = trial_dir / "asb_manifest.json"
    artifacts_dir = trial_dir / "artifacts"
    verifier_dir = trial_dir / "verifier"
    agent_dir = trial_dir / "agent"
    trajectory = None
    if agent_dir.is_dir():
        trajectory = _first_file(agent_dir, TRAJECTORY_NAMES)
        if trajectory is None:
            matches = list(agent_dir.rglob("trajectory.json*"))
            trajectory = matches[0] if matches else None
    test_stdout = verifier_dir / "test-stdout.txt"
    artifact_manifest = artifacts_dir / "manifest.json"
    return {
        "trial_dir": _rel(base, trial_dir),
        "result": _rel(base, result_path) if result_path.exists() else "",
        "config": _rel(base, config_path) if config_path.exists() else "",
        "lock": _rel(base, lock_path) if lock_path.exists() else "",
        "manifest": _rel(base, manifest_path) if manifest_path.exists() else "",
        "artifacts_dir": _rel(base, artifacts_dir) if artifacts_dir.is_dir() else "",
        "artifact_manifest": _rel(base, artifact_manifest) if artifact_manifest.exists() else "",
        "tests": _rel(base, test_stdout) if test_stdout.exists() else "",
        "trajectory": _rel(base, trajectory) if trajectory else "",
        "patch_digest": _patch_digest(trial_dir),
        "test_digest": sha256_file(test_stdout) if test_stdout.exists() else "",
    }


def index_job(job_dir: Path, root: Path | None = None) -> dict[str, Any]:
    base = root or repo_root()
    ledger = load_ledger(job_dir)
    experiment = None
    experiment_path = job_dir / "asb_experiment.json"
    if experiment_path.exists():
        experiment = json.loads(experiment_path.read_text())
        experiment = redact_mapping(experiment)
    trials: list[dict[str, Any]] = []
    for trial_dir in sorted(path for path in job_dir.iterdir() if path.is_dir()):
        result_path = trial_dir / "result.json"
        if not result_path.exists():
            result_path = trial_dir / "results.json"
        if not result_path.exists():
            continue
        result = json.loads(result_path.read_text())
        config = json.loads((trial_dir / "config.json").read_text()) if (trial_dir / "config.json").exists() else {}
        lock = json.loads((trial_dir / "lock.json").read_text()) if (trial_dir / "lock.json").exists() else {}
        manifest = {}
        manifest_path = trial_dir / "asb_manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
        trial_id = str(result.get("id") or trial_dir.name)
        artifacts = trial_artifacts(trial_dir, base)
        kwargs = ((config.get("agent") or {}).get("kwargs")) or {}
        trials.append(
            {
                "trial_id": trial_id,
                "trial_name": result.get("trial_name") or trial_dir.name,
                "job": job_dir.name,
                "task": result.get("task_name"),
                "agent": ((result.get("agent_info") or {}).get("name")) or ((config.get("agent") or {}).get("name")),
                "model": (config.get("agent") or {}).get("model_name"),
                "treatment": kwargs.get("asb_treatment"),
                "prompt": kwargs.get("prompt_name"),
                "config_fingerprint": manifest.get("fingerprint") or "",
                "already_billed": trial_id in (ledger.get("entries") or {}),
                "n_tool_calls": _tool_calls(result, trial_dir),
                "network": network_audit(lock, config),
                "artifacts": artifacts,
            }
        )
    return {
        "job": job_dir.name,
        "job_dir": _rel(base, job_dir),
        "experiment": experiment,
        "ledger": {
            "billed_usd": ledger.get("billed_usd") or 0,
            "n_scored": ledger.get("n_scored") or 0,
            "n_entries": len(ledger.get("entries") or {}),
        },
        "n_trials": len(trials),
        "trials": trials,
    }


def index_jobs(jobs_dir: Path | None = None, root: Path | None = None) -> dict[str, Any]:
    base = root or repo_root()
    directory = jobs_dir or (base / "jobs")
    jobs: list[dict[str, Any]] = []
    if directory.exists():
        for path in sorted(directory.iterdir()):
            if not path.is_dir() or path.name.startswith("."):
                continue
            if not any((path / name).exists() for name in ("job.log", "asb_experiment.json", "config.json")):
                continue
            jobs.append(index_job(path, base))
    # Fingerprint → trial_ids, never fingerprint → patch.
    by_fingerprint: dict[str, list[str]] = {}
    for job in jobs:
        for trial in job["trials"]:
            fingerprint = trial.get("config_fingerprint") or ""
            if not fingerprint:
                continue
            by_fingerprint.setdefault(fingerprint, []).append(trial["trial_id"])
    return {
        "n_jobs": len(jobs),
        "n_trials": sum(job["n_trials"] for job in jobs),
        "jobs": jobs,
        "config_fingerprint_index": by_fingerprint,
        "note": (
            "Locate a trial by trial_id → artifacts.manifest / artifacts.result. "
            "The same config fingerprint in two jobs has distinct trial_dirs and patches."
        ),
    }


def write_warehouse(payload: dict[str, Any], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "index.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def locate(payload: dict[str, Any], trial_id: str) -> dict[str, Any] | None:
    for job in payload.get("jobs") or []:
        for trial in job.get("trials") or []:
            if trial.get("trial_id") == trial_id:
                return trial
    return None
