from __future__ import annotations

import csv
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_skill_bench.classify import FailureClass, classify_trial
from agent_skill_bench.constants import MODEL_SNAPSHOT, SCORER_VERSION, SEED, repo_root
from agent_skill_bench.fingerprint import build_fingerprint, sha256_file
from agent_skill_bench.ledger import LedgerEntry, load_ledger, record_trial, save_ledger
from agent_skill_bench.policy import network_audit, secret_leaks
from agent_skill_bench.scorer import rubric_packet, score_trial
from agent_skill_bench.warehouse import _tool_calls, trial_artifacts

DISCLAIMER = (
    "This table is a loop / matrix smoke of the experiment machinery. "
    "It is not a ranking, not a capability claim, and not a generalization "
    "about models, agents, prompts, or skills."
)


def _git_commit(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def _latest_job(jobs_dir: Path) -> Path:
    jobs = [
        path
        for path in jobs_dir.iterdir()
        if path.is_dir() and (path / "job.log").exists()
    ]
    if not jobs:
        raise FileNotFoundError(f"No Harbor jobs with job.log in {jobs_dir}")
    return max(jobs, key=lambda path: path.stat().st_mtime)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _user_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in kwargs.items() if not str(key).startswith("asb_")}


def _treatment_from_agent(config: dict[str, Any]) -> tuple[str, str, str]:
    agent = (config.get("agent") or {})
    kwargs = agent.get("kwargs") or {}
    prompt_name = kwargs.get("prompt_name") or "unknown"
    treatment = kwargs.get("asb_treatment")
    if not treatment:
        skills = agent.get("skills") or []
        treatment = "candidate" if skills else "baseline"
    track = kwargs.get("asb_track") or "A"
    return str(treatment), str(prompt_name), str(track)


def _skill_bundle(lock: dict[str, Any], skills_log: dict[str, Any] | None) -> list[dict[str, str]]:
    bundle: list[dict[str, str]] = []
    for index, skill in enumerate(lock.get("skills") or []):
        bundle.append(
            {
                "order": str(index),
                "name": skill.get("name") or "",
                "digest": skill.get("digest") or "",
            }
        )
    if not bundle and skills_log:
        for index, item in enumerate(skills_log.get("loaded") or skills_log.get("found") or []):
            digest = item.get("sha256") or item.get("digest") or ""
            if digest and not digest.startswith("sha256:"):
                digest = f"sha256:{digest}"
            bundle.append(
                {
                    "order": str(index),
                    "name": item.get("name") or "",
                    "digest": digest,
                }
            )
    return bundle


def _duration_sec(result: dict[str, Any]) -> float | None:
    started = result.get("started_at")
    finished = result.get("finished_at")
    if not started or not finished:
        return None
    try:
        start = datetime.fromisoformat(started.replace("Z", "+00:00"))
        end = datetime.fromisoformat(finished.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (end - start).total_seconds()


def summarize_job(job_dir: Path, out_dir: Path) -> Path:
    root = repo_root()
    harness_commit = _git_commit(root)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    fingerprints: list[str] = []
    trial_ids: list[str] = []
    ledger = load_ledger(job_dir)
    n_new = 0
    n_replay = 0

    experiment = None
    experiment_path = job_dir / "asb_experiment.json"
    if experiment_path.exists():
        experiment = _load_json(experiment_path)
    experiment_seed = SEED
    if experiment and experiment.get("seed") is not None:
        experiment_seed = int(experiment["seed"])

    for trial_dir in sorted(path for path in job_dir.iterdir() if path.is_dir()):
        results_path = trial_dir / "result.json"
        if not results_path.exists():
            results_path = trial_dir / "results.json"
        if not results_path.exists():
            continue
        result = _load_json(results_path)
        config = _load_json(trial_dir / "config.json") if (trial_dir / "config.json").exists() else {}
        lock = _load_json(trial_dir / "lock.json") if (trial_dir / "lock.json").exists() else {}
        skills_log = None
        skills_path = trial_dir / "agent" / "skills.json"
        if skills_path.exists():
            skills_log = _load_json(skills_path)
        prompt_path = trial_dir / "agent" / "prompt.md"
        prompt_sha256 = sha256_file(prompt_path) if prompt_path.exists() else ""
        treatment, prompt_name, track = _treatment_from_agent(config)
        agent_info = result.get("agent_info") or {}
        task_lock = lock.get("task") or {}
        agent_cfg = config.get("agent") or {}
        kwargs = agent_cfg.get("kwargs") or {}
        if kwargs.get("prompt_name"):
            prompt_name = kwargs["prompt_name"]
        model_name = agent_cfg.get("model_name")
        seed = kwargs.get("asb_seed")
        if seed is None:
            seed = experiment_seed
        pair_id = str(kwargs.get("asb_pair_id") or "")
        pairing_key = str(kwargs.get("asb_pairing_key") or "")
        agent_kwargs = _user_kwargs(kwargs)
        agent_kwargs.pop("prompt_name", None)
        agent_kwargs.pop("prompt_path", None)

        trial_id = str(result.get("id") or trial_dir.name)
        fingerprint = build_fingerprint(
            trial_id=trial_id,
            task_name=result.get("task_name") or trial_dir.name,
            task_checksum=result.get("task_checksum") or task_lock.get("digest") or "",
            agent_name=agent_info.get("name") or agent_cfg.get("name") or "unknown",
            agent_version=agent_info.get("version") or "unknown",
            treatment=treatment,
            prompt_name=prompt_name,
            prompt_sha256=prompt_sha256,
            skill_bundle=_skill_bundle(lock, skills_log),
            harness_commit=harness_commit,
            network_mode=((lock.get("environment") or {}).get("network_mode") or "unknown"),
            agent_timeout_sec=(config.get("agent") or {}).get("override_timeout_sec"),
            verifier_timeout_sec=(config.get("verifier") or {}).get("override_timeout_sec"),
            model_snapshot=model_name or MODEL_SNAPSHOT,
            seed=int(seed),
            agent_kwargs=agent_kwargs,
            pair_id=pair_id,
            pairing_key=pairing_key,
        )
        failure = classify_trial(result)
        scored = score_trial(result)
        rewards = ((result.get("verifier_result") or {}).get("rewards")) or {}
        cost = ((result.get("agent_result") or {}).get("cost_usd"))
        tokens_in = ((result.get("agent_result") or {}).get("n_input_tokens"))
        tokens_out = ((result.get("agent_result") or {}).get("n_output_tokens"))
        instruction_text = ""
        instruction_path = trial_dir / "agent" / "instruction.md"
        if instruction_path.exists():
            instruction_text = instruction_path.read_text()
        workspace_files: dict[str, str] = {}
        workspace_path = trial_dir / "agent" / "workspace.json"
        if workspace_path.exists():
            try:
                loaded = json.loads(workspace_path.read_text())
                if isinstance(loaded, dict):
                    workspace_files = {str(k): str(v) for k, v in loaded.items()}
            except json.JSONDecodeError:
                workspace_files = {}
        packet = rubric_packet(
            instruction=instruction_text,
            files=workspace_files,
            task_id=str(result.get("task_name") or ""),
        )
        (trial_dir / "asb_rubric_packet.json").write_text(json.dumps(packet, indent=2) + "\n")
        skill_loaded = bool(
            skills_log
            and skills_log.get("uses_skills")
            and skills_log.get("loaded")
        )
        artifacts = trial_artifacts(trial_dir, root)
        billed = 0.0 if cost is None else float(cost)
        inserted = record_trial(
            ledger,
            LedgerEntry(
                trial_id=trial_id,
                trial_name=str(result.get("trial_name") or trial_dir.name),
                config_fingerprint=str(fingerprint["fingerprint"]),
                billed_usd=billed,
                scored=True,
                job_name=job_dir.name,
                trial_dir=artifacts["trial_dir"],
                patch_digest=artifacts["patch_digest"],
                result_digest=sha256_file(results_path),
            ),
        )
        if inserted:
            n_new += 1
        else:
            n_replay += 1
        row = {
            "trial_id": trial_id,
            "trial_name": result.get("trial_name") or trial_dir.name,
            "task": result.get("task_name"),
            "track": track,
            "agent": fingerprint["agent_name"],
            "model": fingerprint["model_snapshot"],
            "treatment": treatment,
            "pair_id": pair_id,
            "pairing_key": pairing_key,
            "prompt": prompt_name,
            "seed": int(seed),
            "agent_kwargs": agent_kwargs,
            "skill_injected": bool(fingerprint["skill_bundle"]),
            "skill_loaded": skill_loaded,
            "reward": rewards.get("reward"),
            "failure_class": failure.value,
            "infra_error": scored["infra_error"],
            "counted_as_model_failure": scored["counted_as_model_failure"],
            "scorer_version": SCORER_VERSION,
            "duration_sec": _duration_sec(result),
            "cost_usd": cost,
            "n_input_tokens": tokens_in,
            "n_output_tokens": tokens_out,
            "n_tool_calls": _tool_calls(result, trial_dir),
            "fingerprint": fingerprint["fingerprint"],
            "task_checksum": fingerprint["task_checksum"],
            "trial_dir": artifacts["trial_dir"],
            "manifest": artifacts["manifest"] or str(trial_dir / "asb_manifest.json"),
            "result_uri": artifacts["result"],
            "patch_digest": artifacts["patch_digest"],
            "tests": artifacts["tests"],
            "trajectory": artifacts["trajectory"],
            "network": network_audit(lock, config),
            "billed_once": inserted,
        }
        rows.append(row)
        trial_ids.append(trial_id)
        fingerprints.append(fingerprint["fingerprint"])
        leaks = secret_leaks({"manifest": fingerprint, "row": row})
        if leaks:
            raise ValueError(f"secret-looking keys in trial {trial_id}: {leaks}")
        (trial_dir / "asb_manifest.json").write_text(
            json.dumps(
                {
                    **fingerprint,
                    "failure_class": failure.value,
                    "reward": rewards.get("reward"),
                    "score": scored,
                    "skill_log": skills_log,
                    "experiment": experiment,
                },
                indent=2,
            )
            + "\n"
        )

    rows.sort(key=lambda item: (item["task"] or "", item["agent"], item["treatment"]))
    unique_ids = len(set(trial_ids)) == len(trial_ids) and len(trial_ids) > 0
    unique_fps = len(set(fingerprints)) == len(fingerprints) and len(fingerprints) > 0
    save_ledger(job_dir, ledger)

    csv_path = out_dir / "results.csv"
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else ["trial_id"])
        writer.writeheader()
        writer.writerows(rows)

    md_lines = [
        "# Experiment results",
        "",
        DISCLAIMER,
        "",
        f"- Job: `{job_dir.name}`",
        f"- Trials: {len(rows)}",
        f"- Unique trial IDs: {unique_ids}",
        f"- Unique fingerprints: {unique_fps}",
        f"- Newly billed/scored: {n_new}",
        f"- Resume replays (not re-billed): {n_replay}",
        f"- Ledger billed_usd: {ledger.get('billed_usd')}",
        f"- Summarized at: {datetime.now(timezone.utc).isoformat()}",
        "",
        "| track | task | agent | treatment | pair | reward | class | skill loaded | duration_s | fingerprint |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        duration = row["duration_sec"]
        duration_s = f"{duration:.1f}" if isinstance(duration, float) else ""
        fp = (row["fingerprint"] or "")[:16]
        md_lines.append(
            f"| {row['track']} | {row['task']} | {row['agent']} | {row['treatment']} | "
            f"{row['pair_id'] or ''} | "
            f"{row['reward']} | {row['failure_class']} | {row['skill_loaded']} | "
            f"{duration_s} | `{fp}` |"
        )
    md_lines.extend(["", "## Counts by failure class", ""])
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["failure_class"]] = counts.get(row["failure_class"], 0) + 1
    for cls in FailureClass:
        md_lines.append(f"- `{cls.value}`: {counts.get(cls.value, 0)}")
    md_path = out_dir / "results.md"
    md_path.write_text("\n".join(md_lines) + "\n")

    payload = {
        "disclaimer": DISCLAIMER,
        "job_dir": str(job_dir),
        "n_trials": len(rows),
        "unique_trial_ids": unique_ids,
        "unique_fingerprints": unique_fps,
        "counts": counts,
        "experiment": experiment,
        "ledger": {
            "billed_usd": ledger.get("billed_usd") or 0,
            "n_scored": ledger.get("n_scored") or 0,
            "n_new": n_new,
            "n_replay": n_replay,
        },
        "rows": rows,
    }
    (out_dir / "results.json").write_text(json.dumps(payload, indent=2) + "\n")
    return md_path


def summarize_latest(jobs_dir: Path | None = None, out_dir: Path | None = None) -> Path:
    root = repo_root()
    job_dir = _latest_job(jobs_dir or (root / "jobs"))
    destination = out_dir or (root / "results" / job_dir.name)
    return summarize_job(job_dir, destination)
