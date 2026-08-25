"""Public holdout helpers: generate writes sealed corpus; the catalog is not public.

Agent-visible files (instruction, environment, task.toml) may live in git.
Hidden tests, gold, alternative, and negative live under ASB_SEALED_DIR.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

from agent_skill_bench.constants import (
    ASSEMBLED_PATH,
    AUTHORED_AT,
    CACHE_DIR,
    COMPROMISED_GOLD_REV,
    CUTOFF_POLICY,
    DATASET_ID,
    DATASET_REVISION,
    SEALED_REF,
    SEALED_REPO,
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


def cache_root(root: Path | None = None) -> Path:
    return ((root or repo_root()) / CACHE_DIR).resolve()


def resolve_cache_target(root: Path, path: Path | str, *, label: str) -> Path:
    """Force dest into cache/asb. Absolute paths and .. escapes are rejected."""
    base = cache_root(root)
    raw = Path(path)
    if raw.is_absolute():
        raise HoldoutError(f"{label} must be relative to the repo, not absolute: {path}")
    if ".." in raw.parts:
        raise HoldoutError(f"{label} must not contain '..': {path}")
    resolved = (root / raw).resolve()
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise HoldoutError(f"{label} must stay inside {CACHE_DIR}: {path}") from exc
    return resolved


def sealed_root(root: Path | None = None) -> Path:
    root = root or repo_root()
    override = os.environ.get(SEALED_ENV)
    if override:
        return resolve_cache_target(root, override, label="ASB_SEALED_DIR")
    return cache_root(root) / "sealed"


def atomic_replace_dir(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    staging = dest.parent / f".{dest.name}.staging-{os.getpid()}"
    backup = dest.parent / f".{dest.name}.prev-{os.getpid()}"
    if staging.exists():
        shutil.rmtree(staging)
    shutil.move(str(src), str(staging))
    replaced = False
    try:
        if dest.exists():
            os.rename(dest, backup)
            replaced = True
        os.rename(staging, dest)
    except Exception:
        if replaced and backup.exists() and not dest.exists():
            os.rename(backup, dest)
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)


def private_root(root: Path | None = None) -> Path:
    return (root or repo_root()) / "tasks" / "private"


def manifest_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / "datasets" / "private-manifest.toml"


def load_manifest(root: Path | None = None) -> dict[str, Any]:
    path = manifest_path(root)
    if not path.exists():
        raise HoldoutError(f"missing public manifest: {path}")
    return tomllib.loads(path.read_text())


def catalog_path(root: Path | None = None) -> Path:
    root = root or repo_root()
    legacy = root / "sealed" / "holdout" / "catalog.py"
    if legacy.exists():
        return legacy
    cached = sealed_root(root) / "catalog.py"
    if cached.exists():
        return cached
    raise HoldoutError(
        f"sealed catalog missing; run `asb fetch-sealed` or place catalog.py under {CACHE_DIR}/sealed"
    )


def load_catalog(root: Path | None = None) -> Any:
    path = catalog_path(root)
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
    rev = DATASET_REVISION
    instruction = (
        spec.instruction.strip()
        + f"\n\nAlso write `{rev}` followed by a newline to `/app/ASB_REVISION`.\n"
    )
    test_py = (
        spec.test_py.rstrip()
        + f"\nassert (APP / 'ASB_REVISION').read_text().strip() == {rev!r}\n"
    )
    stamp = f'\n(app / "ASB_REVISION").write_text({rev!r} + "\\n")\n'
    (public_dir / "instruction.md").write_text(instruction)
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
    (tests / "test_outputs.py").write_text(test_py)
    (tests / "HIDDEN_CANARY.txt").write_text(catalog.HIDDEN_CANARY + "\n")
    (solution / "solve.sh").write_text(catalog._py_script(spec.gold_py + stamp))
    (solution / "solve.sh").chmod(0o755)
    (solution / "HIDDEN_CANARY.txt").write_text(catalog.HIDDEN_CANARY + "\n")
    (alt / "solve.sh").write_text(catalog._py_script(spec.alt_py + stamp))
    (alt / "solve.sh").chmod(0o755)
    (negative / "solve.sh").write_text(catalog._py_script(spec.negative_py))
    (negative / "solve.sh").chmod(0o755)
    (negative / "REASON.txt").write_text(spec.negative_reason + "\n")


def compromised_gold_script(sealed_root_dir: Path, slug: str) -> Path:
    return sealed_root_dir / "compromised" / COMPROMISED_GOLD_REV / slug / "solve.sh"


def compromised_gold_digest(sealed_root_dir: Path, slug: str) -> str:
    path = compromised_gold_script(sealed_root_dir, slug)
    return sha256_file(path) if path.is_file() else ""


def task_digests(public_dir: Path, sealed_dir: Path) -> dict[str, str]:
    return {
        "instruction_digest": sha256_file(public_dir / "instruction.md"),
        "environment_digest": sha256_tree(public_dir / "environment"),
        "tests_digest": sha256_tree(sealed_dir / "tests"),
        "gold_digest": sha256_tree(sealed_dir / "solution"),
        "alt_digest": sha256_tree(sealed_dir / "variants" / "alt"),
        "negative_digest": sha256_tree(sealed_dir / "variants" / "negative"),
        "compromised_gold_digest": compromised_gold_digest(sealed_dir.parent, sealed_dir.name),
    }


def write_manifest(root: Path, entries: list[dict[str, str]]) -> Path:
    lines = [
        f'dataset_id = "{DATASET_ID}"',
        f'dataset_revision = "{DATASET_REVISION}"',
        f'authored_at = "{AUTHORED_AT}"',
        f'cutoff_policy = "{CUTOFF_POLICY}"',
        f"n_private_tasks = {len(entries)}",
        f'sealed_access = "gh repo clone {SEALED_REPO} -- --branch {SEALED_REF}"',
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
    sealed_base.mkdir(parents=True, exist_ok=True)
    src_catalog = catalog_path(root)
    dest_catalog = sealed_base / "catalog.py"
    if src_catalog.resolve() != dest_catalog.resolve():
        shutil.copy2(src_catalog, dest_catalog)
    compromised = getattr(catalog, "COMPROMISED_GOLD", {})
    for slug, body in compromised.items():
        script = compromised_gold_script(sealed_base, slug)
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(catalog._py_script(body))
        script.chmod(0o755)
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


def remote_pin_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / "datasets" / "sealed-remote.toml"


def load_remote_pin(root: Path | None = None) -> dict[str, Any]:
    path = remote_pin_path(root)
    if not path.exists():
        raise HoldoutError(f"missing sealed remote pin: {path}")
    return tomllib.loads(path.read_text())


def verify_sealed(root: Path | None = None, sealed: Path | None = None) -> None:
    root = root or repo_root()
    sealed = sealed or sealed_root(root)
    manifest = load_manifest(root)
    public_base = private_root(root)
    problems: list[str] = []
    tasks = list(manifest.get("tasks") or [])
    expected_slugs = [entry["slug"] for entry in tasks]
    found_slugs = sorted(
        path.parent.name
        for path in (sealed / "compromised" / COMPROMISED_GOLD_REV).glob("*/solve.sh")
    )
    if found_slugs != sorted(expected_slugs):
        problems.append(
            "compromised gold inventory: expected "
            f"{sorted(expected_slugs)}, got {found_slugs}"
        )
    digest_keys = (
        "tests_digest",
        "gold_digest",
        "alt_digest",
        "negative_digest",
        "compromised_gold_digest",
    )
    for entry in tasks:
        slug = entry["slug"]
        got = task_digests(public_base / slug, sealed / slug)
        for key in digest_keys:
            if not entry.get(key):
                problems.append(f"{slug} {key} missing from manifest")
            elif got.get(key) != entry.get(key):
                problems.append(f"{slug} {key}: expected {entry.get(key)}, got {got.get(key)}")
    if problems:
        raise HoldoutError("sealed corpus failed integrity check:\n" + "\n".join(problems))


def fetch_sealed(root: Path | None = None, *, clone_cmd: list[str] | None = None) -> Path:
    """Clone into a temp dir, verify, then atomically replace the cache."""
    import tempfile

    root = root or repo_root()
    pin = load_remote_pin(root)
    dest = sealed_root(root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    repo = str(pin.get("repo") or SEALED_REPO)
    ref = str(pin.get("ref") or SEALED_REF)
    with tempfile.TemporaryDirectory(prefix="asb-fetch-") as tmp:
        tmp_repo = Path(tmp) / "repo"
        cmd = clone_cmd or [
            "gh",
            "repo",
            "clone",
            repo,
            str(tmp_repo),
            "--",
            "--depth",
            "1",
            "--branch",
            ref,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise HoldoutError(
                f"authorized fetch failed for {repo}@{ref}: {result.stderr.strip()}\n"
                "Existing cache was left unchanged. Grant read access and retry "
                "`asb fetch-sealed`."
            )
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=tmp_repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        expected = str(pin.get("commit") or "")
        if expected and sha != expected:
            raise HoldoutError(f"sealed commit mismatch: got {sha}, pin wants {expected}")
        verify_sealed(root, tmp_repo)
        keep = Path(tmp) / "keep"
        shutil.copytree(tmp_repo, keep, ignore=shutil.ignore_patterns(".git"))
        atomic_replace_dir(keep, dest)
    return dest


def assemble_dataset(root: Path | None = None, dest: Path | str | None = None) -> Path:
    """Merge public + sealed into a temp tree, then atomically replace cache."""
    import tempfile

    from agent_skill_bench.validity import assemble

    root = root or repo_root()
    dest = resolve_cache_target(root, dest or ASSEMBLED_PATH, label="assembled_path")
    sealed = sealed_root(root)
    if not sealed.exists():
        raise HoldoutError(
            f"sealed corpus missing at {sealed}; run `asb fetch-sealed` first"
        )
    verify_sealed(root, sealed)
    with tempfile.TemporaryDirectory(prefix="asb-assemble-") as tmp:
        built = Path(tmp) / "assembled"
        built.mkdir()
        for entry in load_manifest(root).get("tasks") or []:
            slug = entry["slug"]
            assemble(private_root(root) / slug, sealed / slug, built / slug)
            if not (built / slug / "tests" / "test.sh").exists():
                raise HoldoutError(f"assembled {slug} missing tests/test.sh")
            if not (built / slug / "solution" / "solve.sh").exists():
                raise HoldoutError(f"assembled {slug} missing solution/solve.sh")
        keep = Path(tmp) / "keep"
        shutil.copytree(built, keep)
        atomic_replace_dir(keep, dest)
    return dest


def write_remote_pin(root: Path, commit: str, ref: str = SEALED_REF) -> Path:
    path = remote_pin_path(root)
    path.write_text(
        "\n".join(
            [
                f'repo = "{SEALED_REPO}"',
                f'ref = "{ref}"',
                f'commit = "{commit}"',
                f'dataset_revision = "{DATASET_REVISION}"',
                "fetch = \"asb fetch-sealed\"",
                "",
            ]
        )
    )
    return path
