from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from agent_skill_bench.constants import repo_root


def run_smoke(config_path: Path | None = None, n_concurrent: int = 2) -> Path:
    root = repo_root()
    config = config_path or (root / "configs" / "harbor_smoke_2x2.yaml")
    if not config.exists():
        raise FileNotFoundError(f"Harbor job config not found: {config}")

    job_name = datetime.now(timezone.utc).strftime("smoke-2x2-%Y%m%dT%H%M%SZ")
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
    subprocess.run(cmd, cwd=root, check=True)
    return jobs_dir / job_name
