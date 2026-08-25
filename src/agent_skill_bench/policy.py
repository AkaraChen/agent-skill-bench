"""Budget, quota, cache, retention, secret, and network policy.

ponytail: Harbor already isolates sandboxes. We only add the gates Stage 4
asks for — no second scheduler, no secret store.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol

from agent_skill_bench.experiment import ExperimentError

# Isolated workers Harbor already knows. Docker is the local default;
# the rest are cloud sandboxes selected via environment.type.
ISOLATED_ENVIRONMENTS = (
    "docker",
    "daytona",
    "e2b",
    "modal",
    "runloop",
    "ec2",
    "gke",
    "opensandbox",
    "hf-sandbox",
    "cwsandbox",
)

# Values that must never land in manifests, warehouse rows, or dashboard HTML.
SECRET_KEY_RE = re.compile(
    r"(^|[_-])(api[_-]?key|secret|token|password|passwd|authorization|credentials?|private[_-]?key)$",
    re.IGNORECASE,
)

# Cache is image/layer only. Trial patches live under the trial dir and are
# never addressed by config fingerprint.
CACHE_SCOPE_IMAGE = "image"
CACHE_SCOPE_NONE = "none"
FORBIDDEN_CACHE_SCOPES = ("patch", "workspace", "trial")


class PlanLike(Protocol):
    budget_usd: float | None
    usd_per_trial: float
    max_trials: int
    n_concurrent: int
    max_retries: int
    timeout_multiplier: float
    retention_days: int | None
    secret_allowlist: tuple[str, ...]
    cache_scope: str
    durable_artifacts: bool
    environment: dict[str, Any]


@dataclass(frozen=True)
class Policy:
    budget_usd: float | None
    usd_per_trial: float
    max_trials: int
    n_concurrent: int
    max_retries: int
    timeout_multiplier: float
    retention_days: int | None
    secret_allowlist: tuple[str, ...]
    network_mode: str
    cache_scope: str
    environment_type: str
    durable_artifacts: bool


def policy_from_plan(plan: PlanLike) -> Policy:
    environment = plan.environment or {}
    return Policy(
        budget_usd=plan.budget_usd,
        usd_per_trial=plan.usd_per_trial,
        max_trials=plan.max_trials,
        n_concurrent=plan.n_concurrent,
        max_retries=plan.max_retries,
        timeout_multiplier=plan.timeout_multiplier,
        retention_days=plan.retention_days,
        secret_allowlist=plan.secret_allowlist,
        network_mode=str(environment.get("network_mode") or "unknown"),
        cache_scope=plan.cache_scope,
        environment_type=str(environment.get("type") or "docker"),
        durable_artifacts=plan.durable_artifacts,
    )


def guard_policy(plan: PlanLike) -> None:
    """Fail closed on cache, env, and quota mistakes. Budget is experiment.guard."""
    policy = policy_from_plan(plan)
    if policy.cache_scope in FORBIDDEN_CACHE_SCOPES:
        raise ExperimentError(
            f"cache_scope={policy.cache_scope!r} would reuse old patches; "
            "use 'image' (Harbor layer cache) or 'none'"
        )
    if policy.environment_type not in ISOLATED_ENVIRONMENTS:
        raise ExperimentError(
            f"environment.type {policy.environment_type!r} is not an isolated "
            f"worker ({', '.join(ISOLATED_ENVIRONMENTS)})"
        )
    if policy.n_concurrent < 1:
        raise ExperimentError("n_concurrent must be >= 1")
    if policy.timeout_multiplier <= 0:
        raise ExperimentError("timeout_multiplier must be > 0")
    if policy.retention_days is not None and policy.retention_days < 1:
        raise ExperimentError("retention_days must be >= 1")


def redact_mapping(payload: dict[str, Any], allowlist: tuple[str, ...] = ()) -> dict[str, Any]:
    """Drop secret-looking keys. Allowlisted names are recorded as present, not valued."""
    redacted: dict[str, Any] = {}
    allowed = {name.upper() for name in allowlist}
    for key, value in payload.items():
        name = str(key)
        if name.upper() in allowed or SECRET_KEY_RE.search(name):
            redacted[name] = "[redacted]"
        elif isinstance(value, dict):
            redacted[name] = redact_mapping(value, allowlist)
        else:
            redacted[name] = value
    return redacted


def secret_leaks(payload: Any, allowlist: tuple[str, ...] = ()) -> list[str]:
    """Return dotted paths whose keys look like secrets and still hold a value."""
    allowed = {name.upper() for name in allowlist}
    found: list[str] = []

    def walk(node: Any, prefix: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                path = f"{prefix}.{key}" if prefix else str(key)
                if SECRET_KEY_RE.search(str(key)) and str(key).upper() not in allowed:
                    if value not in (None, "", "[redacted]"):
                        found.append(path)
                walk(value, path)
        elif isinstance(node, list):
            for index, item in enumerate(node):
                walk(item, f"{prefix}[{index}]")

    walk(payload, "")
    return found


def network_audit(lock: dict[str, Any] | None, config: dict[str, Any] | None) -> dict[str, Any]:
    environment = (lock or {}).get("environment") or (config or {}).get("environment") or {}
    return {
        "type": environment.get("type") or "unknown",
        "network_mode": environment.get("network_mode") or "unknown",
        "allowed_hosts": list(environment.get("allowed_hosts") or []),
        "delete": environment.get("delete"),
    }


def retention_cutoff(now: datetime | None, days: int) -> datetime:
    stamp = now or datetime.now(timezone.utc)
    return stamp - timedelta(days=days)


def list_expired_jobs(jobs_dir: Path, days: int, now: datetime | None = None) -> list[Path]:
    cutoff = retention_cutoff(now, days)
    expired: list[Path] = []
    if not jobs_dir.exists():
        return expired
    for path in jobs_dir.iterdir():
        if not path.is_dir() or path.name.startswith("."):
            continue
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if mtime < cutoff:
            expired.append(path)
    return sorted(expired)


def inject_secrets(allowlist: tuple[str, ...]) -> dict[str, str]:
    """Copy allowlisted env vars into the Harbor environment map. Values stay in the process env."""
    injected: dict[str, str] = {}
    for name in allowlist:
        if name in os.environ and os.environ[name]:
            injected[name] = os.environ[name]
    return injected
