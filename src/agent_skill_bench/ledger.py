"""Durable per-job billing and scoring ledger.

Harbor resume skips completed trials. This ledger is the second gate: summarize
and warehouse never double-count cost or reward for a trial_id that already
landed. Patches are addressed by trial_id / trial_dir, never by config
fingerprint — a rerun of the same spec gets a new job dir and new patches.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LEDGER_NAME = "asb_ledger.json"
LEDGER_SCHEMA = 1


@dataclass
class LedgerEntry:
    trial_id: str
    trial_name: str
    config_fingerprint: str
    billed_usd: float
    scored: bool
    job_name: str
    trial_dir: str
    patch_digest: str = ""
    result_digest: str = ""
    recorded_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def ledger_path(job_dir: Path) -> Path:
    return job_dir / LEDGER_NAME


def empty_ledger(job_name: str) -> dict[str, Any]:
    return {
        "schema": LEDGER_SCHEMA,
        "job_name": job_name,
        "entries": {},
        "billed_usd": 0.0,
        "n_scored": 0,
    }


def load_ledger(job_dir: Path) -> dict[str, Any]:
    path = ledger_path(job_dir)
    if not path.exists():
        return empty_ledger(job_dir.name)
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        return empty_ledger(job_dir.name)
    payload.setdefault("entries", {})
    payload.setdefault("billed_usd", 0.0)
    payload.setdefault("n_scored", 0)
    payload.setdefault("job_name", job_dir.name)
    return payload


def save_ledger(job_dir: Path, ledger: dict[str, Any]) -> Path:
    job_dir.mkdir(parents=True, exist_ok=True)
    path = ledger_path(job_dir)
    path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n")
    return path


def already_recorded(ledger: dict[str, Any], trial_id: str) -> bool:
    entries = ledger.get("entries") or {}
    return str(trial_id) in entries


def record_trial(ledger: dict[str, Any], entry: LedgerEntry) -> bool:
    """Insert a trial once. Returns False when trial_id is already billed/scored."""
    if already_recorded(ledger, entry.trial_id):
        return False
    if not entry.recorded_at:
        entry.recorded_at = datetime.now(timezone.utc).isoformat()
    cost = float(entry.billed_usd or 0)
    ledger.setdefault("entries", {})[entry.trial_id] = entry.to_dict()
    ledger["billed_usd"] = float(ledger.get("billed_usd") or 0) + cost
    if entry.scored:
        ledger["n_scored"] = int(ledger.get("n_scored") or 0) + 1
    return True


def billed_total(ledger: dict[str, Any]) -> float:
    return float(ledger.get("billed_usd") or 0)


def scored_ids(ledger: dict[str, Any]) -> set[str]:
    return set((ledger.get("entries") or {}).keys())
