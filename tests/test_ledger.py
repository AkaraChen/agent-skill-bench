from pathlib import Path

from agent_skill_bench.ledger import (
    LedgerEntry,
    already_recorded,
    billed_total,
    load_ledger,
    record_trial,
    save_ledger,
)


def _entry(trial_id: str, cost: float, job: str = "job-a", trial_dir: str = "jobs/job-a/t1") -> LedgerEntry:
    return LedgerEntry(
        trial_id=trial_id,
        trial_name=trial_id,
        config_fingerprint="sha256:same-config",
        billed_usd=cost,
        scored=True,
        job_name=job,
        trial_dir=trial_dir,
        patch_digest=f"sha256:patch-{trial_id}",
    )


def test_resume_does_not_double_bill(tmp_path: Path) -> None:
    ledger = load_ledger(tmp_path)
    assert record_trial(ledger, _entry("t1", 1.5)) is True
    assert record_trial(ledger, _entry("t1", 1.5)) is False
    assert billed_total(ledger) == 1.5
    assert already_recorded(ledger, "t1")
    save_ledger(tmp_path, ledger)
    again = load_ledger(tmp_path)
    assert record_trial(again, _entry("t1", 9.0)) is False
    assert billed_total(again) == 1.5


def test_same_config_new_job_is_a_new_bill() -> None:
    first = {}
    second = {}
    assert record_trial(first, _entry("trial-a", 0.4, job="job-1", trial_dir="jobs/job-1/a"))
    assert record_trial(second, _entry("trial-b", 0.4, job="job-2", trial_dir="jobs/job-2/b"))
    assert first["entries"]["trial-a"]["trial_dir"] != second["entries"]["trial-b"]["trial_dir"]
    assert first["entries"]["trial-a"]["patch_digest"] != second["entries"]["trial-b"]["patch_digest"]
    assert first["entries"]["trial-a"]["config_fingerprint"] == second["entries"]["trial-b"]["config_fingerprint"]
