import pytest

from agent_skill_bench.holdout import HoldoutError, assemble_dataset, fetch_sealed
from test_validity import write_mini


def test_failed_fetch_keeps_old_cache(tmp_path) -> None:
    write_mini(tmp_path)
    dest = tmp_path / "cache" / "asb" / "sealed"
    marker = dest / "KEEP"
    marker.write_text("stay\n")
    (tmp_path / "datasets" / "sealed-remote.toml").write_text(
        'repo = "example/none"\nref = "v0"\ncommit = "deadbeef"\n'
    )
    with pytest.raises(HoldoutError, match="fetch failed"):
        fetch_sealed(tmp_path, clone_cmd=["bash", "-c", "exit 1"])
    assert marker.read_text() == "stay\n"


def test_absolute_assemble_path_rejected(tmp_path) -> None:
    write_mini(tmp_path)
    evil = tmp_path.parent / "outside-assembled"
    evil.mkdir(exist_ok=True)
    sentinel = evil / "nope"
    sentinel.write_text("keep\n")
    with pytest.raises(HoldoutError, match="absolute"):
        assemble_dataset(tmp_path, str(evil))
    assert sentinel.read_text() == "keep\n"
    assert list(evil.iterdir()) == [sentinel]


def test_dotdot_assemble_path_rejected(tmp_path) -> None:
    write_mini(tmp_path)
    with pytest.raises(HoldoutError, match=r"\.\."):
        assemble_dataset(tmp_path, "../outside")
    assert not (tmp_path.parent / "outside").exists()


def test_absolute_sealed_dir_rejected_without_changes(tmp_path, monkeypatch) -> None:
    write_mini(tmp_path)
    (tmp_path / "datasets" / "sealed-remote.toml").write_text(
        'repo = "example/none"\nref = "v0"\ncommit = "deadbeef"\n'
    )
    evil = tmp_path.parent / "outside-sealed-abs"
    evil.mkdir(exist_ok=True)
    sentinel = evil / "nope"
    sentinel.write_text("keep\n")
    monkeypatch.setenv("ASB_SEALED_DIR", str(evil))
    with pytest.raises(HoldoutError, match="must be relative"):
        fetch_sealed(tmp_path, clone_cmd=["bash", "-c", "echo cloned; exit 0"])
    assert sentinel.read_text() == "keep\n"
    assert list(evil.iterdir()) == [sentinel]


def test_dotdot_sealed_dir_rejected_without_changes(tmp_path, monkeypatch) -> None:
    write_mini(tmp_path)
    (tmp_path / "datasets" / "sealed-remote.toml").write_text(
        'repo = "example/none"\nref = "v0"\ncommit = "deadbeef"\n'
    )
    monkeypatch.setenv("ASB_SEALED_DIR", "../outside-sealed-dotdot")
    with pytest.raises(HoldoutError, match="must not contain"):
        fetch_sealed(tmp_path, clone_cmd=["bash", "-c", "echo cloned; exit 0"])
    assert not (tmp_path.parent / "outside-sealed-dotdot").exists()


def test_old_gold_fails_new_hidden_tests_after_stamp(tmp_path) -> None:
    from agent_skill_bench.constants import DATASET_REVISION
    from agent_skill_bench.validity import assemble, gate_compromised

    write_mini(tmp_path)
    public = tmp_path / "tasks" / "private" / "echo-n"
    sealed = tmp_path / "cache" / "asb" / "sealed" / "echo-n"
    # New hidden contract: output must be 2*n. Old gold wrote n.
    (sealed / "tests" / "test_outputs.py").write_text(
        "import os\nfrom pathlib import Path\n"
        "APP = Path(os.environ.get('APP', '/app'))\n"
        "n = int((APP / 'n.txt').read_text())\n"
        "assert (APP / 'output.txt').read_text() == str(2 * n) + '\\n'\n"
        f"assert (APP / 'ASB_REVISION').read_text().strip() == {DATASET_REVISION!r}\n"
    )
    old = tmp_path / "cache" / "asb" / "sealed" / "compromised" / "2026.08.25" / "echo-n"
    old.mkdir(parents=True, exist_ok=True)
    (old / "solve.sh").write_text(
        "#!/bin/bash\nset -euo pipefail\nAPP=\"${APP:-/app}\"\n"
        "python3 - \"$APP\" <<'PY'\nfrom pathlib import Path\nimport sys\n"
        "app = Path(sys.argv[1])\n"
        "(app / 'output.txt').write_text((app / 'n.txt').read_text())\nPY\n"
    )
    (old / "solve.sh").chmod(0o755)
    assembled = assemble(public, sealed, tmp_path / "cache" / "asb" / "assembled" / "echo-n")
    result = gate_compromised(assembled, sealed)
    assert result.ok is True
    assert result.gate == "compromised-gold"
