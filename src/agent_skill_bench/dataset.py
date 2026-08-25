"""Dataset revision, public-subset pin, and provenance."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from agent_skill_bench.constants import (
    AUTHORED_AT,
    CUTOFF_POLICY,
    DATASET_ID,
    DATASET_REVISION,
    DOCKER_DIGEST,
    DOCKER_IMAGE,
    HARBOR_VERSION,
    SCORER_VERSION,
    repo_root,
)
from agent_skill_bench.retry_policy import harbor_retry


PUBLIC_SUBSET = {
    "name": "harbor/hello-world",
    "ref": "sha256:d10e96e201d6816b22553504e06e7de0153a26381e808d11404cbca530b9d388",
    "task_names": ["hello-world/hello-world"],
}

PUBLIC_TERMINAL = {
    "name": "terminal-bench/terminal-bench-2",
    "ref": "sha256:c6fc2e2382c1dbae99b2d5ecd2f4f4a60c3c01e0d84642d69b4afd92e99d078b",
    "task_names": [
        "terminal-bench/make-mips-interpreter",
        "terminal-bench/circuit-fibsqrt",
        "terminal-bench/build-pov-ray",
        "terminal-bench/overfull-hbox",
        "terminal-bench/video-processing",
        "terminal-bench/distribution-search",
        "terminal-bench/break-filter-js-from-html",
        "terminal-bench/protein-assembly",
    ],
}


def revision_payload(root: Path | None = None) -> dict[str, Any]:
    root = root or repo_root()
    return {
        "dataset_id": DATASET_ID,
        "dataset_revision": DATASET_REVISION,
        "authored_at": AUTHORED_AT,
        "cutoff_policy": CUTOFF_POLICY,
        "n_private_tasks": 24,
        "scorer_version": SCORER_VERSION,
        "harbor_version": HARBOR_VERSION,
        "image": f"{DOCKER_IMAGE}@{DOCKER_DIGEST}",
        "retry": harbor_retry(),
        "public_subset": [PUBLIC_SUBSET, PUBLIC_TERMINAL],
        "sealed_remote": "datasets/sealed-remote.toml",
        "compromised": "datasets/compromised.toml",
        "leakage_evidence": (
            "revision 2026.08.25.r3; 2026.08.25 and r2 are compromised; "
            "fetch via asb fetch-sealed"
        ),
        "revision_file": str((root / "datasets" / "revision.toml").relative_to(root)),
    }


def read_revision(root: Path | None = None) -> dict[str, Any]:
    root = root or repo_root()
    path = root / "datasets" / "revision.toml"
    return tomllib.loads(path.read_text())
