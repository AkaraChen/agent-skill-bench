"""Fail-closed validity gates on an immutable sealed corpus.

Generate is a separate command. Validate never writes the corpus. Variants
run in the pinned image with no network and the declared resource limits.
Host execution is refused.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from agent_skill_bench.constants import (
    DOCKER_DIGEST,
    DOCKER_IMAGE,
    HIDDEN_CANARY,
    NETWORK_MODE,
    RESOURCE_CPUS,
    RESOURCE_MEMORY_MB,
    RESOURCE_STORAGE_MB,
    repo_root,
)
from agent_skill_bench.holdout import (
    HoldoutError,
    load_manifest,
    private_root,
    sealed_root,
    task_digests,
)


VISIBLE_REL = ("instruction.md", "environment")
NETWORK_FORBIDDEN = ("curl ", "wget ", "apt-get ", "apk add", "pip install", "npm install")
PINNED_IMAGE = f"{DOCKER_IMAGE}@{DOCKER_DIGEST}"


class ValidityError(RuntimeError):
    pass


@dataclass
class GateResult:
    task: str
    gate: str
    ok: bool
    detail: str = ""


@dataclass
class TaskReport:
    task: str
    language: str
    kind: str
    size: str
    difficulty: str
    gates: list[GateResult] = field(default_factory=list)
    quarantined: bool = False

    @property
    def ok(self) -> bool:
        return all(item.ok for item in self.gates)


def load_quarantine(root: Path) -> dict[str, str]:
    path = root / "datasets" / "quarantine.toml"
    if not path.exists():
        return {}
    data = tomllib.loads(path.read_text())
    out: dict[str, str] = {}
    for item in data.get("excluded") or []:
        out[str(item["task"])] = str(item.get("reason") or "")
    return out


def docker_available() -> bool:
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def require_docker() -> None:
    if not docker_available():
        raise ValidityError(
            "docker is required for fail-closed validation; refusing host execution"
        )


def ensure_pinned_image() -> None:
    inspect = subprocess.run(
        ["docker", "image", "inspect", PINNED_IMAGE],
        capture_output=True,
        check=False,
    )
    if inspect.returncode == 0:
        return
    pull = subprocess.run(
        ["docker", "pull", PINNED_IMAGE],
        capture_output=True,
        text=True,
        check=False,
    )
    if pull.returncode != 0:
        raise ValidityError(f"failed to pull pinned image {PINNED_IMAGE}: {pull.stderr}")


def run_variant_container(app: Path, tests: Path, script: Path) -> subprocess.CompletedProcess[str]:
    require_docker()
    ensure_pinned_image()
    cmd = [
        "docker",
        "run",
        "--rm",
        "--network=none",
        f"--cpus={RESOURCE_CPUS}",
        f"--memory={RESOURCE_MEMORY_MB}m",
        f"--memory-swap={RESOURCE_MEMORY_MB}m",
        "-u",
        f"{os.getuid()}:{os.getgid()}",
        "-v",
        f"{app.resolve()}:/app",
        "-v",
        f"{tests.resolve()}:/tests:ro",
        "-v",
        f"{script.resolve()}:/solve.sh:ro",
        "-e",
        "APP=/app",
        "-e",
        "TESTS=/tests",
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        "-w",
        "/app",
        PINNED_IMAGE,
        "bash",
        "-lc",
        "bash /solve.sh && python3 /tests/test_outputs.py",
    ]
    return subprocess.run(cmd, capture_output=True, text=True)


def assemble(public_dir: Path, sealed_dir: Path, dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(public_dir, dest)
    for name in ("tests", "solution", "variants"):
        src = sealed_dir / name
        if not src.exists():
            raise ValidityError(f"sealed part missing: {src}")
        shutil.copytree(src, dest / name)
    return dest


def _copy_env(task_dir: Path, dest: Path) -> None:
    src = task_dir / "environment"
    dest.mkdir(parents=True, exist_ok=True)
    for item in src.rglob("*"):
        if item.is_dir() or item.name == "Dockerfile":
            continue
        target = dest / item.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)


def run_assembled_variant(assembled: Path, script: Path) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory(prefix="asb-gate-", ignore_cleanup_errors=True) as tmp:
        app = Path(tmp) / "app"
        tests = Path(tmp) / "tests"
        _copy_env(assembled, app)
        shutil.copytree(assembled / "tests", tests)
        return run_variant_container(app, tests, script)


def gate_digest(entry: dict[str, str], public_dir: Path, sealed_dir: Path) -> GateResult:
    got = task_digests(public_dir, sealed_dir)
    problems = [
        f"{key}: expected {entry[key]}, got {got[key]}"
        for key in got
        if entry.get(key) != got[key]
    ]
    return GateResult(entry["slug"], "digest", not problems, "; ".join(problems))


def gate_oracle(assembled: Path) -> GateResult:
    result = run_assembled_variant(assembled, assembled / "solution" / "solve.sh")
    ok = result.returncode == 0
    detail = "" if ok else (result.stderr or result.stdout)[-500:]
    return GateResult(assembled.name, "oracle", ok, detail)


def gate_alternative(assembled: Path) -> GateResult:
    result = run_assembled_variant(assembled, assembled / "variants" / "alt" / "solve.sh")
    ok = result.returncode == 0
    detail = "" if ok else (result.stderr or result.stdout)[-500:]
    return GateResult(assembled.name, "alternative", ok, detail)


def strip_revision_asserts(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if "ASB_REVISION" not in line) + "\n"


def _container_bash(app: Path, tests: Path, command: str, extra_mount: tuple[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    require_docker()
    ensure_pinned_image()
    mounts = [
        "-v",
        f"{app.resolve()}:/app",
        "-v",
        f"{tests.resolve()}:/tests:ro",
    ]
    if extra_mount:
        mounts.extend(["-v", f"{extra_mount[0]}:{extra_mount[1]}:ro"])
    cmd = [
        "docker",
        "run",
        "--rm",
        "--network=none",
        f"--cpus={RESOURCE_CPUS}",
        f"--memory={RESOURCE_MEMORY_MB}m",
        f"--memory-swap={RESOURCE_MEMORY_MB}m",
        "-u",
        f"{os.getuid()}:{os.getgid()}",
        *mounts,
        "-e",
        "APP=/app",
        "-e",
        "TESTS=/tests",
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        "-w",
        "/app",
        PINNED_IMAGE,
        "bash",
        "-lc",
        command,
    ]
    return subprocess.run(cmd, capture_output=True, text=True)


def gate_compromised(assembled: Path, sealed_dir: Path) -> GateResult:
    """Leaked gold plus the correct revision stamp must still fail hidden tests."""
    from agent_skill_bench.constants import DATASET_REVISION

    old = sealed_dir.parent / "compromised" / "2026.08.25" / assembled.name / "solve.sh"
    if not old.exists():
        return GateResult(assembled.name, "compromised-gold", False, f"missing {old}")
    with tempfile.TemporaryDirectory(prefix="asb-comp-", ignore_cleanup_errors=True) as tmp:
        tests = Path(tmp) / "tests"
        shutil.copytree(assembled / "tests", tests)
        (tests / "test_outputs.py").write_text(
            strip_revision_asserts((tests / "test_outputs.py").read_text())
        )
        app = Path(tmp) / "app"
        _copy_env(assembled, app)
        apply = _container_bash(
            app,
            tests,
            "bash /oldgold.sh",
            extra_mount=(str(old.resolve()), "/oldgold.sh"),
        )
        if apply.returncode != 0:
            # old gold itself crashed; still stamp and test
            pass
        (app / "ASB_REVISION").write_text(DATASET_REVISION + "\n")
        tested = _container_bash(app, tests, "python3 /tests/test_outputs.py")
        ok = tested.returncode != 0
        detail = "" if ok else "leaked gold + stamp still satisfies hidden tests"
        return GateResult(assembled.name, "compromised-gold", ok, detail)


def gate_negative(assembled: Path) -> GateResult:
    result = run_assembled_variant(assembled, assembled / "variants" / "negative" / "solve.sh")
    ok = result.returncode != 0
    detail = "" if ok else "known-wrong variant unexpectedly passed hidden tests"
    return GateResult(assembled.name, "mutation", ok, detail)


def gate_leakage(public_dir: Path) -> GateResult:
    leaks: list[str] = []
    for rel in VISIBLE_REL:
        path = public_dir / rel
        files = [path] if path.is_file() else list(path.rglob("*"))
        for item in files:
            if item.is_file() and HIDDEN_CANARY in item.read_text(errors="ignore"):
                leaks.append(str(item.relative_to(public_dir)))
    if (public_dir / "tests").exists() or (public_dir / "solution").exists():
        leaks.append("public tree contains tests/ or solution/")
    instruction = (public_dir / "instruction.md").read_text()
    if HIDDEN_CANARY in instruction:
        leaks.append("instruction contains canary")
    return GateResult(public_dir.name, "leakage", not leaks, ", ".join(leaks))


def gate_network(public_dir: Path) -> GateResult:
    problems: list[str] = []
    data = tomllib.loads((public_dir / "task.toml").read_text())
    for section in ("verifier", "agent", "environment"):
        mode = (data.get(section) or {}).get("network_mode")
        if mode != NETWORK_MODE:
            problems.append(f"{section}.network_mode={mode}")
    dockerfile = public_dir / "environment" / "Dockerfile"
    if dockerfile.exists():
        text = dockerfile.read_text()
        if DOCKER_DIGEST not in text:
            problems.append("Dockerfile missing pinned digest")
        lower = text.lower()
        for token in NETWORK_FORBIDDEN:
            if token in lower:
                problems.append(f"Dockerfile uses {token.strip()}")
    return GateResult(public_dir.name, "network", not problems, "; ".join(problems))


def gate_resources(public_dir: Path) -> GateResult:
    env = (tomllib.loads((public_dir / "task.toml").read_text()).get("environment") or {})
    problems = []
    if int(env.get("cpus") or 0) != RESOURCE_CPUS:
        problems.append(f"cpus={env.get('cpus')}")
    if int(env.get("memory_mb") or 0) != RESOURCE_MEMORY_MB:
        problems.append(f"memory_mb={env.get('memory_mb')}")
    if int(env.get("storage_mb") or 0) != RESOURCE_STORAGE_MB:
        problems.append(f"storage_mb={env.get('storage_mb')}")
    return GateResult(public_dir.name, "resources", not problems, "; ".join(problems))


def gate_git_history(public_dir: Path, root: Path) -> GateResult:
    leaks: list[str] = []
    for path in (public_dir / "instruction.md", public_dir / "environment"):
        files = [path] if path.is_file() else [p for p in path.rglob("*") if p.is_file()]
        for item in files:
            if HIDDEN_CANARY in item.read_text(errors="ignore"):
                leaks.append(str(item.relative_to(root)))
    try:
        rels = [
            str((public_dir / "instruction.md").relative_to(root)),
            str((public_dir / "environment").relative_to(root)),
        ]
        result = subprocess.run(
            ["git", "log", "-p", "--", *rels],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if HIDDEN_CANARY in (result.stdout or ""):
            leaks.append("git-history")
    except OSError:
        pass
    return GateResult(public_dir.name, "git-history", not leaks, ", ".join(leaks))


def evaluate_task(
    entry: dict[str, str],
    public_dir: Path,
    sealed_dir: Path,
    root: Path,
    *,
    execute: bool,
) -> TaskReport:
    report = TaskReport(
        task=entry.get("id") or entry["slug"],
        language=str(entry.get("language") or ""),
        kind=str(entry.get("kind") or ""),
        size=str(entry.get("size") or ""),
        difficulty=str(entry.get("difficulty") or ""),
        gates=[
            gate_digest(entry, public_dir, sealed_dir),
            gate_leakage(public_dir),
            gate_network(public_dir),
            gate_resources(public_dir),
            gate_git_history(public_dir, root),
        ],
    )
    if not execute:
        return report
    digest_ok = all(g.ok for g in report.gates if g.gate == "digest")
    if not digest_ok:
        report.gates.append(GateResult(entry["slug"], "oracle", False, "skipped: digest drift"))
        report.gates.append(GateResult(entry["slug"], "alternative", False, "skipped: digest drift"))
        report.gates.append(GateResult(entry["slug"], "mutation", False, "skipped: digest drift"))
        return report
    with tempfile.TemporaryDirectory(prefix="asb-assemble-", ignore_cleanup_errors=True) as tmp:
        assembled = assemble(public_dir, sealed_dir, Path(tmp) / entry["slug"])
        report.gates.extend(
            [
                gate_oracle(assembled),
                gate_alternative(assembled),
                gate_negative(assembled),
            ]
        )
        if (sealed_dir.parent / "compromised" / "2026.08.25" / assembled.name / "solve.sh").exists():
            report.gates.append(gate_compromised(assembled, sealed_dir))
    return report


def validate_private(
    root: Path | None = None,
    *,
    execute: bool = True,
    sealed: Path | None = None,
) -> dict[str, Any]:
    root = root or repo_root()
    sealed_dir = sealed or sealed_root(root)
    if not sealed_dir.exists():
        raise ValidityError(
            f"sealed corpus missing at {sealed_dir}; set ASB_SEALED_DIR. "
            "validate does not generate or overwrite the corpus."
        )
    try:
        manifest = load_manifest(root)
    except HoldoutError as exc:
        raise ValidityError(str(exc)) from exc
    if execute:
        require_docker()
    quarantine = load_quarantine(root)
    public_base = private_root(root)
    reports: list[TaskReport] = []
    for entry in manifest.get("tasks") or []:
        slug = str(entry["slug"])
        report = evaluate_task(
            entry,
            public_base / slug,
            sealed_dir / slug,
            root,
            execute=execute,
        )
        report.quarantined = report.task in quarantine or slug in quarantine
        reports.append(report)
    live_fail = [r for r in reports if not r.ok and not r.quarantined]
    return {
        "n_tasks": len(reports),
        "n_pass": sum(1 for r in reports if r.ok),
        "n_fail": sum(1 for r in reports if not r.ok),
        "n_quarantined": sum(1 for r in reports if r.quarantined),
        "live_failures": [r.task for r in live_fail],
        "stratification": {
            "language": _counts(reports, "language"),
            "kind": _counts(reports, "kind"),
            "size": _counts(reports, "size"),
            "difficulty": _counts(reports, "difficulty"),
        },
        "reports": [
            {
                **{k: v for k, v in asdict(report).items() if k != "gates"},
                "ok": report.ok,
                "gates": [asdict(g) for g in report.gates],
            }
            for report in reports
        ],
    }


def _counts(reports: list[TaskReport], field_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for report in reports:
        key = getattr(report, field_name)
        counts[key] = counts.get(key, 0) + 1
    return counts


def write_validity_report(payload: dict[str, Any], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "validity.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")
    lines = [
        "# Private holdout validity",
        "",
        f"- tasks: {payload['n_tasks']}",
        f"- pass: {payload['n_pass']}",
        f"- fail: {payload['n_fail']}",
        f"- quarantined: {payload['n_quarantined']}",
        f"- live failures: {', '.join(payload['live_failures']) or '(none)'}",
        "",
        "## Stratification",
        "",
    ]
    for dim, counts in payload["stratification"].items():
        pretty = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        lines.append(f"- {dim}: {pretty}")
    lines.extend(["", "## Gates", ""])
    for report in payload["reports"]:
        mark = "PASS" if report["ok"] else "FAIL"
        extra = " (quarantined)" if report["quarantined"] else ""
        lines.append(f"### {report['task']} {mark}{extra}")
        for gate in report["gates"]:
            gmark = "ok" if gate["ok"] else "FAIL"
            detail = f" — {gate['detail']}" if gate["detail"] else ""
            lines.append(f"- `{gate['gate']}`: {gmark}{detail}")
        lines.append("")
    md = out_dir / "validity.md"
    md.write_text("\n".join(lines) + "\n")
    return md
