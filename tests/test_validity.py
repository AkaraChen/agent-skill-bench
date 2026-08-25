import json
import subprocess
from pathlib import Path

import pytest

from agent_skill_bench.constants import DOCKER_DIGEST, HIDDEN_CANARY, N_PRIVATE_TASKS, repo_root
from agent_skill_bench.holdout import (
    assemble_dataset,
    compromised_gold_script,
    generate,
    load_manifest,
    sealed_root,
    task_digests,
    verify_sealed,
    write_manifest,
)
from agent_skill_bench.validity import ValidityError, assemble, validate_private

MINI_TOML = f"""schema_version = "1.4"

[task]
name = "fixture/echo-n"
version = "1.0.0"

[metadata]
difficulty = "easy"
category = "programming"
language = "python"
kind = "feature"
size = "tiny"

[verifier]
timeout_sec = 60.0
network_mode = "no-network"

[agent]
timeout_sec = 60.0
network_mode = "no-network"

[environment]
build_timeout_sec = 300.0
cpus = 1
memory_mb = 512
storage_mb = 1024
gpus = 0
workdir = "/app"
network_mode = "no-network"
"""

DOCKERFILE = f"""FROM python:3.12.11-slim-bookworm@{DOCKER_DIGEST}
WORKDIR /app
COPY . /app
RUN rm -f /app/Dockerfile
"""

TEST_SH = """#!/bin/bash
set -euo pipefail
export APP="${APP:-/app}"
export TESTS="${TESTS:-/tests}"
python3 "$TESTS/test_outputs.py"
status=$?
if [ "$status" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
exit "$status"
"""


def _script(body: str) -> str:
    return f"""#!/bin/bash
set -euo pipefail
APP="${{APP:-/app}}"
python3 - "$APP" <<'PY'
from pathlib import Path
import sys
app = Path(sys.argv[1])
{body}
PY
"""


def write_mini(root: Path) -> None:
    public = root / "tasks" / "private" / "echo-n"
    sealed = root / "cache" / "asb" / "sealed" / "echo-n"
    env = public / "environment"
    tests = sealed / "tests"
    gold = sealed / "solution"
    alt = sealed / "variants" / "alt"
    negative = sealed / "variants" / "negative"
    for path in (env, tests, gold, alt, negative):
        path.mkdir(parents=True, exist_ok=True)
    (public / "instruction.md").write_text(
        "Read `/app/n.txt` and write that integer plus a newline to `/app/output.txt`.\n"
    )
    (public / "task.toml").write_text(MINI_TOML)
    (env / "Dockerfile").write_text(DOCKERFILE)
    (env / "n.txt").write_text("3\n")
    (tests / "test.sh").write_text(TEST_SH)
    (tests / "test.sh").chmod(0o755)
    (tests / "canary.py").write_text(
        f'CANARY = "{HIDDEN_CANARY}"\ndef assert_no_canary_in_app():\n    return None\n'
    )
    (tests / "test_outputs.py").write_text(
        "import os\nfrom pathlib import Path\n"
        "APP = Path(os.environ.get('APP', '/app'))\n"
        "assert (APP / 'output.txt').read_text() == (APP / 'n.txt').read_text()\n"
    )
    (tests / "HIDDEN_CANARY.txt").write_text(HIDDEN_CANARY + "\n")
    (gold / "solve.sh").write_text(
        _script('(app / "output.txt").write_text((app / "n.txt").read_text())')
    )
    (gold / "solve.sh").chmod(0o755)
    (gold / "HIDDEN_CANARY.txt").write_text(HIDDEN_CANARY + "\n")
    (alt / "solve.sh").write_text(
        _script('n = int((app / "n.txt").read_text()); (app / "output.txt").write_text(str(n) + "\\n")')
    )
    (alt / "solve.sh").chmod(0o755)
    (negative / "solve.sh").write_text(
        _script('(app / "output.txt").write_text("4\\n")')
    )
    (negative / "solve.sh").chmod(0o755)
    (negative / "REASON.txt").write_text("writes 4 instead of n\n")
    leaked = sealed.parent / "compromised" / "2026.08.25" / "echo-n"
    leaked.mkdir(parents=True, exist_ok=True)
    (leaked / "solve.sh").write_text(_script('(app / "output.txt").write_text("0\\n")'))
    (leaked / "solve.sh").chmod(0o755)
    (root / "datasets").mkdir(parents=True, exist_ok=True)
    (root / "datasets" / "quarantine.toml").write_text("# none\n")
    entry = {
        "slug": "echo-n",
        "id": "fixture/echo-n",
        "language": "python",
        "kind": "feature",
        "size": "tiny",
        "difficulty": "easy",
        **task_digests(public, sealed),
    }
    write_manifest(root, [entry])


def test_validate_does_not_generate(tmp_path: Path, monkeypatch) -> None:
    write_mini(tmp_path)

    def boom(*_args, **_kwargs):
        raise AssertionError("validate must not generate")

    monkeypatch.setattr("agent_skill_bench.holdout.generate", boom)
    payload = validate_private(tmp_path, execute=False)
    assert payload["n_tasks"] == 1
    assert payload["live_failures"] == []
    assert _compromised_gold_count(payload) == 1


def test_corpus_drift_fails(tmp_path: Path) -> None:
    write_mini(tmp_path)
    instruction = tmp_path / "tasks" / "private" / "echo-n" / "instruction.md"
    instruction.write_text("tampered instruction\n")
    payload = validate_private(tmp_path, execute=False)
    assert payload["live_failures"] == ["fixture/echo-n"]
    digest = next(g for g in payload["reports"][0]["gates"] if g["gate"] == "digest")
    assert digest["ok"] is False
    assert "instruction_digest" in digest["detail"]


def test_missing_sealed_is_fail_closed(tmp_path: Path) -> None:
    write_mini(tmp_path)
    sealed = tmp_path / "cache" / "asb" / "sealed"
    import shutil

    shutil.rmtree(sealed)
    try:
        validate_private(tmp_path, execute=False)
        raised = False
    except ValidityError:
        raised = True
    assert raised


def test_pinned_container_gold_alt_negative(tmp_path: Path) -> None:
    write_mini(tmp_path)
    payload = validate_private(tmp_path, execute=True)
    assert payload["live_failures"] == []
    by_gate = {g["gate"]: g["ok"] for g in payload["reports"][0]["gates"]}
    assert by_gate["oracle"] is True
    assert by_gate["alternative"] is True
    assert by_gate["mutation"] is True
    assert by_gate["digest"] is True
    assert by_gate["compromised-gold"] is True
    assert sum(1 for g in payload["reports"][0]["gates"] if g["gate"] == "compromised-gold") == 1


def test_generate_is_separate_from_validate() -> None:
    import inspect
    from agent_skill_bench import validity

    source = inspect.getsource(validity.validate_private)
    assert "generate(" not in source
    assert "materialize" not in source


def test_assemble_merges_sealed_tests_and_solution(tmp_path: Path) -> None:
    write_mini(tmp_path)
    dest = assemble_dataset(tmp_path, "cache/asb/assembled/holdout")
    task = dest / "echo-n"
    assert (task / "instruction.md").exists()
    assert (task / "environment" / "n.txt").exists()
    assert (task / "tests" / "test.sh").exists()
    assert (task / "solution" / "solve.sh").exists()
    assert not (tmp_path / "tasks" / "private" / "echo-n" / "tests").exists()


def test_harbor_oracle_verifier_e2e(tmp_path: Path) -> None:
    write_mini(tmp_path)
    public = tmp_path / "tasks" / "private" / "echo-n"
    sealed = tmp_path / "cache" / "asb" / "sealed" / "echo-n"
    assembled = assemble(public, sealed, tmp_path / "assembled" / "echo-n")
    jobs = tmp_path / "jobs"
    result = subprocess.run(
        [
            "harbor",
            "run",
            "-p",
            str(assembled),
            "-a",
            "oracle",
            "-o",
            str(jobs),
            "--job-name",
            "e2e-oracle",
            "-n",
            "1",
            "--yes",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    rewards = []
    for path in jobs.rglob("result.json"):
        payload = json.loads(path.read_text())
        reward = ((payload.get("verifier_result") or {}).get("rewards") or {}).get("reward")
        rewards.append(reward)
    for path in jobs.rglob("results.json"):
        payload = json.loads(path.read_text())
        if isinstance(payload, dict) and "verifier_result" in payload:
            reward = ((payload.get("verifier_result") or {}).get("rewards") or {}).get("reward")
            rewards.append(reward)
    assert 1 in rewards or 1.0 in rewards, f"no oracle reward=1 in {list(jobs.rglob('*'))}"


def _compromised_gold_count(payload: dict) -> int:
    return sum(
        1
        for report in payload["reports"]
        for gate in report["gates"]
        if gate["gate"] == "compromised-gold"
    )


def test_missing_compromised_gold_fails_and_keeps_gate(tmp_path: Path) -> None:
    write_mini(tmp_path)
    compromised_gold_script(tmp_path / "cache" / "asb" / "sealed", "echo-n").unlink()
    payload = validate_private(tmp_path, execute=False)
    assert payload["live_failures"] == ["fixture/echo-n"]
    assert _compromised_gold_count(payload) == 1
    gate = next(g for g in payload["reports"][0]["gates"] if g["gate"] == "compromised-gold")
    assert gate["ok"] is False
    assert "missing" in gate["detail"]


def test_tampered_compromised_gold_fails_closed(tmp_path: Path) -> None:
    write_mini(tmp_path)
    script = compromised_gold_script(tmp_path / "cache" / "asb" / "sealed", "echo-n")
    script.write_text("#!/bin/bash\nexit 1\n")
    payload = validate_private(tmp_path, execute=False)
    assert payload["live_failures"] == ["fixture/echo-n"]
    assert _compromised_gold_count(payload) == 1
    gate = next(g for g in payload["reports"][0]["gates"] if g["gate"] == "compromised-gold")
    assert gate["ok"] is False
    assert "drift" in gate["detail"] or "missing" in gate["detail"]


def test_crashing_compromised_gold_does_not_pass_gate(tmp_path: Path) -> None:
    write_mini(tmp_path)
    sealed = tmp_path / "cache" / "asb" / "sealed"
    public = tmp_path / "tasks" / "private" / "echo-n"
    script = compromised_gold_script(sealed, "echo-n")
    script.write_text("#!/bin/bash\nexit 1\n")
    script.chmod(0o755)
    entry = {
        "slug": "echo-n",
        "id": "fixture/echo-n",
        "language": "python",
        "kind": "feature",
        "size": "tiny",
        "difficulty": "easy",
        **task_digests(public, sealed / "echo-n"),
    }
    write_manifest(tmp_path, [entry])
    payload = validate_private(tmp_path, execute=True)
    assert payload["live_failures"] == ["fixture/echo-n"]
    assert _compromised_gold_count(payload) == 1
    gate = next(g for g in payload["reports"][0]["gates"] if g["gate"] == "compromised-gold")
    assert gate["ok"] is False
    assert "did not apply" in gate["detail"]


def test_full_holdout_report_has_24_compromised_gold_gates() -> None:
    root = repo_root()
    if not sealed_root(root).exists():
        pytest.skip("sealed holdout not fetched")
    tasks = load_manifest(root)["tasks"]
    assert len(tasks) == N_PRIVATE_TASKS
    assert all(item.get("compromised_gold_digest", "").startswith("sha256:") for item in tasks)
    verify_sealed(root)
    payload = validate_private(root, execute=False)
    assert payload["n_tasks"] == N_PRIVATE_TASKS
    assert _compromised_gold_count(payload) == N_PRIVATE_TASKS
    assert all(
        gate["ok"]
        for report in payload["reports"]
        for gate in report["gates"]
        if gate["gate"] == "compromised-gold"
    )
