from pathlib import Path

HIDDEN_CANARY = "ASB_HIDDEN_CANARY_DO_NOT_LEAK_9f3c"
MODEL_SNAPSHOT = "deterministic/smoke-solver@2026-08-24"
HARBOR_VERSION = "0.22.0"
SEED = 42
AGENT_TIMEOUT_SEC = 60
VERIFIER_TIMEOUT_SEC = 60
DOCKER_IMAGE = "python:3.12.11-slim-bookworm"
DOCKER_DIGEST = "sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7"
SCORER_VERSION = "1.0.0"
DATASET_ID = "asb-private-holdout"
DATASET_REVISION = "2026.08.25"
AUTHORED_AT = "2026-08-25"
CUTOFF_POLICY = "authored-after-2026-08-01"
RESOURCE_CPUS = 1
RESOURCE_MEMORY_MB = 512
RESOURCE_STORAGE_MB = 1024
NETWORK_MODE = "no-network"

# Harbor exceptions that are infrastructure, not model failure.
# Pre-registered: retries apply only to this set.
INFRA_RETRY_EXCEPTIONS = (
    "SandboxBuildFailedError",
    "HealthcheckError",
    "DockerException",
    "APIError",
    "ImageNotFound",
    "NotFound",
    "ConnectionError",
    "TimeoutError",
    "EnvironmentError",
    "AddTestsDirError",
    "DownloadVerifierDirError",
)

# Never retry these; they are agent/model/test outcomes.
RETRY_EXCLUDE_EXCEPTIONS = (
    "AgentTimeoutError",
    "VerifierTimeoutError",
    "RewardFileNotFoundError",
    "RewardFileEmptyError",
    "VerifierOutputParseError",
    "ApiUsageLimitError",
    "AgentSafetyRefusalError",
    "AgentAuthenticationError",
    "ModelNotFoundError",
    "AgentSetupError",
)


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "pyproject.toml").exists() and (parent / "configs").exists():
            return parent
    return Path.cwd()
