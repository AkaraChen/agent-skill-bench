from pathlib import Path

from agent_skill_bench.constants import HIDDEN_CANARY, repo_root

VISIBLE_GLOBS = [
    "tasks/**/instruction.md",
    "tasks/**/environment/**",
    "prompts/*.md",
    "skills/**/*.md",
]


def test_hidden_canary_not_in_agent_visible_files() -> None:
    root = repo_root()
    leaks: list[str] = []
    for pattern in VISIBLE_GLOBS:
        for path in root.glob(pattern):
            if not path.is_file():
                continue
            if HIDDEN_CANARY in path.read_text(errors="ignore"):
                leaks.append(str(path.relative_to(root)))
    assert leaks == []


def test_hidden_canary_lives_in_tests_and_solution() -> None:
    root = repo_root()
    tasks = list(root.glob("tasks/*/task.toml"))
    hidden = list(root.glob("tasks/*/tests/HIDDEN_CANARY.txt"))
    hidden += list(root.glob("tasks/*/solution/HIDDEN_CANARY.txt"))
    assert len(hidden) == 2 * len(tasks)
    assert len(tasks) >= 5
    for path in hidden:
        assert HIDDEN_CANARY in path.read_text()


def test_public_private_tree_does_not_ship_sealed_parts() -> None:
    root = repo_root()
    private = root / "tasks" / "private"
    if not private.exists():
        return
    assert list(private.glob("*/tests/**")) == []
    assert list(private.glob("*/solution/**")) == []
    assert list(private.glob("*/variants/**")) == []
