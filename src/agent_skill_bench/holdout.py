"""Public holdout helpers: generate writes sealed corpus; the catalog is not public.

Agent-visible files (instruction, environment, task.toml) may live in git.
Hidden tests, gold, alternative, and negative live under ASB_SEALED_DIR.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tomllib
from pathlib import Path
from typing import Any

from agent_skill_bench.constants import (
    AUTHORED_AT,
    CUTOFF_POLICY,
    DATASET_ID,
    DATASET_REVISION,
    repo_root,
)
from agent_skill_bench.fingerprint import sha256_file, sha256_tree

SEALED_ENV = "ASB_SEALED_DIR"
KINDS = ("bug", "feature", "refactor", "test", "security")
LANGUAGES = ("python", "bash")
SIZES = ("tiny", "small")
DIFFICULTIES = ("easy", "medium", "hard")


class HoldoutError(RuntimeError):
    pass


def sealed_root(root: Path | None = None) -> Path:
    root = root or repo_root()
    override = os.environ.get(SEALED_ENV)
    if override:
        return Path(override)
    return root / "sealed" / "holdout"


def private_root(root: Path | None = None) -> Path:
    return (root or repo_root()) / "tasks" / "private"


def manifest_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / "datasets" / "private-manifest.toml"


def load_manifest(root: Path | None = None) -> dict[str, Any]:
    path = manifest_path(root)
    if not path.exists():
        raise HoldoutError(f"missing public manifest: {path}")
    return tomllib.loads(path.read_text())


def load_catalog(root: Path | None = None) -> Any:
    path = sealed_root(root) / "catalog.py"
    if not path.exists():
        raise HoldoutError(
            f"sealed catalog missing at {path}; set {SEALED_ENV} to generate"
        )
    spec = importlib.util.spec_from_file_location("asb_sealed_catalog", path)
    if spec is None or spec.loader is None:
        raise HoldoutError(f"cannot load catalog: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_task(spec: Any, public_dir: Path, sealed_dir: Path, catalog: Any) -> None:
    env = public_dir / "environment"
    tests = sealed_dir / "tests"
    solution = sealed_dir / "solution"
    alt = sealed_dir / "variants" / "alt"
    negative = sealed_dir / "variants" / "negative"
    for path in (env, tests, solution, alt, negative):
        path.mkdir(parents=True, exist_ok=True)
    (public_dir / "instruction.md").write_text(spec.instruction.strip() + "\n")
    (public_dir / "task.toml").write_text(catalog._task_toml(spec))
    (env / "Dockerfile").write_text(catalog._dockerfile())
    for rel, content in spec.env_files.items():
        dest = env / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
    if spec.mtimes:
        import time

        now = time.time()
        for rel, offset in spec.mtimes.items():
            os.utime(env / rel, (now + offset, now + offset))
    (tests / "test.sh").write_text(catalog._test_sh())
    (tests / "test.sh").chmod(0o755)
    (tests / "canary.py").write_text(catalog._canary_py())
    (tests / "test_outputs.py").write_text(spec.test_py)
    (tests / "HIDDEN_CANARY.txt").write_text(catalog.HIDDEN_CANARY + "\n")
    (solution / "solve.sh").write_text(catalog._py_script(spec.gold_py))
    (solution / "solve.sh").chmod(0o755)
    (solution / "HIDDEN_CANARY.txt").write_text(catalog.HIDDEN_CANARY + "\n")
    (alt / "solve.sh").write_text(catalog._py_script(spec.alt_py))
    (alt / "solve.sh").chmod(0o755)
    (negative / "solve.sh").write_text(catalog._py_script(spec.negative_py))
    (negative / "solve.sh").chmod(0o755)
    (negative / "REASON.txt").write_text(spec.negative_reason + "\n")


def task_digests(public_dir: Path, sealed_dir: Path) -> dict[str, str]:
    return {
        "instruction_digest": sha256_file(public_dir / "instruction.md"),
        "environment_digest": sha256_tree(public_dir / "environment"),
        "tests_digest": sha256_tree(sealed_dir / "tests"),
        "gold_digest": sha256_tree(sealed_dir / "solution"),
        "alt_digest": sha256_tree(sealed_dir / "variants" / "alt"),
        "negative_digest": sha256_tree(sealed_dir / "variants" / "negative"),
    }


def write_manifest(root: Path, entries: list[dict[str, str]]) -> Path:
    lines = [
        f'dataset_id = "{DATASET_ID}"',
        f'dataset_revision = "{DATASET_REVISION}"',
        f'authored_at = "{AUTHORED_AT}"',
        f'cutoff_policy = "{CUTOFF_POLICY}"',
        f"n_private_tasks = {len(entries)}",
        'sealed_access = "ASB_SEALED_DIR or <repo>/sealed/holdout (gitignored)"',
        "",
    ]
    for entry in entries:
        lines.append("[[tasks]]")
        for key, value in entry.items():
            if key == "slug" or key.endswith("_digest") or key in {"id", "language", "kind", "size", "difficulty"}:
                lines.append(f'{key} = "{value}"')
        lines.append("")
    path = manifest_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))
    return path


def generate(root: Path | None = None) -> Path:
    """Write public agent-visible files, sealed secrets, and the digest manifest.

    Never called by validate.
    """
    root = root or repo_root()
    catalog = load_catalog(root)
    public_base = private_root(root)
    sealed_base = sealed_root(root)
    entries: list[dict[str, str]] = []
    for spec in catalog.TASKS:
        public_dir = public_base / spec.slug
        sealed_dir = sealed_base / spec.slug
        _write_task(spec, public_dir, sealed_dir, catalog)
        entry = {
            "slug": spec.slug,
            "id": f"{DATASET_ID}/{spec.slug}",
            "language": spec.language,
            "kind": spec.kind,
            "size": spec.size,
            "difficulty": spec.difficulty,
            **task_digests(public_dir, sealed_dir),
        }
        entries.append(entry)
    return write_manifest(root, entries)
