import json
from pathlib import Path

from agent_skill_bench.summarize import summarize_job
from agent_skill_bench.warehouse import index_jobs, locate, trial_artifacts


def _trial(job: Path, name: str, trial_id: str, treatment: str, patch: str) -> Path:
    trial = job / name
    trial.mkdir(parents=True)
    (trial / "artifacts").mkdir()
    (trial / "artifacts" / "solve.py").write_text(patch)
    (trial / "verifier").mkdir()
    (trial / "verifier" / "test-stdout.txt").write_text("ok\n")
    (trial / "agent").mkdir()
    (trial / "agent" / "trajectory.json").write_text('{"tool_call": 1}\n')
    (trial / "config.json").write_text(
        json.dumps(
            {
                "agent": {
                    "name": "naive-solver",
                    "model_name": "snap",
                    "kwargs": {"asb_treatment": treatment, "prompt_name": treatment, "asb_track": "A"},
                }
            }
        )
    )
    (trial / "lock.json").write_text(json.dumps({"environment": {"type": "docker", "network_mode": "none"}}))
    (trial / "result.json").write_text(
        json.dumps(
            {
                "id": trial_id,
                "trial_name": name,
                "task_name": "asb/echo",
                "task_checksum": "abc",
                "agent_info": {"name": "naive-solver", "version": "0"},
                "agent_result": {"cost_usd": 0.5, "n_input_tokens": 3, "n_output_tokens": 1},
                "verifier_result": {"rewards": {"reward": 1}},
                "started_at": "2026-08-25T00:00:00+00:00",
                "finished_at": "2026-08-25T00:00:10+00:00",
            }
        )
    )
    return trial


def test_same_config_does_not_share_patches(tmp_path: Path) -> None:
    jobs = tmp_path / "jobs"
    job1 = jobs / "run-1"
    job2 = jobs / "run-2"
    job1.mkdir(parents=True)
    job2.mkdir(parents=True)
    (job1 / "job.log").write_text("ok\n")
    (job2 / "job.log").write_text("ok\n")
    _trial(job1, "echo__aaa", "id-1", "baseline", "print(1)\n")
    _trial(job2, "echo__bbb", "id-2", "baseline", "print(2)\n")
    warehouse = index_jobs(jobs, tmp_path)
    one = locate(warehouse, "id-1")
    two = locate(warehouse, "id-2")
    assert one is not None and two is not None
    assert one["artifacts"]["trial_dir"] != two["artifacts"]["trial_dir"]
    assert one["artifacts"]["patch_digest"] != two["artifacts"]["patch_digest"]
    assert one["artifacts"]["manifest"] == "" or "asb_manifest" in (one["artifacts"]["manifest"] or "")


def test_summarize_resume_is_idempotent(tmp_path: Path) -> None:
    job = tmp_path / "jobs" / "run"
    job.mkdir(parents=True)
    (job / "job.log").write_text("ok\n")
    _trial(job, "echo__aaa", "id-1", "baseline", "print(1)\n")
    out = tmp_path / "results" / "run"
    summarize_job(job, out)
    first = json.loads((out / "results.json").read_text())
    summarize_job(job, out)
    second = json.loads((out / "results.json").read_text())
    assert first["ledger"]["billed_usd"] == 0.5
    assert second["ledger"]["billed_usd"] == 0.5
    assert second["ledger"]["n_replay"] == 1
    assert second["rows"][0]["result_uri"]
    artifacts = trial_artifacts(job / "echo__aaa", tmp_path)
    assert artifacts["tests"]
    assert artifacts["trajectory"]
    assert artifacts["patch_digest"].startswith("sha256:")
