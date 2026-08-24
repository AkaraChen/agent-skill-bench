from pathlib import Path

HIDDEN_CANARY = "ASB_HIDDEN_CANARY_DO_NOT_LEAK_9f3c"
MODEL_SNAPSHOT = "deterministic/smoke-solver@2026-08-24"
HARBOR_VERSION = "0.22.0"
SEED = 42
AGENT_TIMEOUT_SEC = 60
VERIFIER_TIMEOUT_SEC = 60
DOCKER_IMAGE = "python:3.12.11-slim-bookworm"
DOCKER_DIGEST = "sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7"


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "pyproject.toml").exists() and (parent / "configs").exists():
            return parent
    return Path.cwd()
