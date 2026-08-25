import json
import subprocess
from pathlib import Path

from agent_skill_bench.constants import DOCKER_DIGEST, HIDDEN_CANARY
from agent_skill_bench.holdout import assemble_dataset, generate, task_digests, write_manifest
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
