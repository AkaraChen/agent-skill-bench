from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from agent_skill_bench.constants import (
    DOCKER_DIGEST,
    HARBOR_VERSION,
    MODEL_SNAPSHOT,
    SEED,
)


def canonical_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_tree(path: Path) -> str:
    """Hash a file or a directory tree (relative paths + contents, sorted)."""
    if not path.exists():
        return ""
    if path.is_file():
        return sha256_file(path)
    hasher = hashlib.sha256()
    files = sorted(item for item in path.rglob("*") if item.is_file())
    for item in files:
        rel = item.relative_to(path).as_posix().encode()
        hasher.update(rel)
        hasher.update(b"\0")
        hasher.update(item.read_bytes())
        hasher.update(b"\0")
    return "sha256:" + hasher.hexdigest()


def build_fingerprint(
    *,
    trial_id: str,
    task_name: str,
    task_checksum: str,
    agent_name: str,
    agent_version: str,
    treatment: str,
    prompt_name: str,
    prompt_sha256: str,
    skill_bundle: list[dict[str, str]],
    harness_commit: str | None,
    network_mode: str,
    agent_timeout_sec: float | None,
    verifier_timeout_sec: float | None,
    model_snapshot: str = MODEL_SNAPSHOT,
    harbor_version: str = HARBOR_VERSION,
    seed: int = SEED,
    docker_digest: str = DOCKER_DIGEST,
    agent_kwargs: dict[str, Any] | None = None,
    pair_id: str = "",
    pairing_key: str = "",
) -> dict[str, Any]:
    body = {
        "harbor_version": harbor_version,
        "harness_commit": harness_commit,
        "model_snapshot": model_snapshot,
        "reasoning_effort": "none",
        "agent_name": agent_name,
        "agent_version": agent_version,
        "treatment": treatment,
        "prompt_name": prompt_name,
        "prompt_sha256": prompt_sha256,
        "skill_bundle": skill_bundle,
        "task_name": task_name,
        "task_checksum": task_checksum,
        "seed": seed,
        "agent_kwargs": agent_kwargs or {},
        "pair_id": pair_id,
        "pairing_key": pairing_key,
        "budget": {
            "agent_timeout_sec": agent_timeout_sec,
            "verifier_timeout_sec": verifier_timeout_sec,
        },
        "network_mode": network_mode,
        "docker_digest": docker_digest,
    }
    digest = sha256_text(canonical_dumps(body))
    return {
        "trial_id": trial_id,
        "fingerprint": digest,
        **body,
    }
