from __future__ import annotations

from enum import Enum
from typing import Any


class FailureClass(str, Enum):
    OK = "ok"
    AGENT = "agent"
    MODEL = "model"
    TEST = "test"
    INFRA = "infra"


INFRA_TYPES = {
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
}

AGENT_TYPES = {
    "AgentTimeoutError",
    "AgentSetupError",
}

MODEL_HINTS = (
    "unsolved",
    "empty output",
    "model",
    "rate limit",
    "authentication",
    "api key",
)


def _exception(result: dict[str, Any]) -> dict[str, Any] | None:
    return result.get("exception_info")


def _reward(result: dict[str, Any]) -> float | None:
    verifier = result.get("verifier_result") or {}
    rewards = verifier.get("rewards") or {}
    if "reward" in rewards:
        try:
            return float(rewards["reward"])
        except (TypeError, ValueError):
            return None
    return None


def classify_trial(result: dict[str, Any]) -> FailureClass:
    """Map a Harbor TrialResult dict onto agent/model/test/infra."""
    exc = _exception(result)
    if exc:
        etype = str(exc.get("exception_type") or "")
        message = str(exc.get("exception_message") or "").lower()
        if etype in AGENT_TYPES or "agent" in etype.lower():
            return FailureClass.AGENT
        if any(hint in message for hint in MODEL_HINTS) and "docker" not in message:
            return FailureClass.MODEL
        if etype in INFRA_TYPES or any(
            token in etype.lower() or token in message
            for token in ("docker", "compose", "sandbox", "image", "network", "infra")
        ):
            return FailureClass.INFRA
        if "verifier" in etype.lower() or "reward" in etype.lower():
            return FailureClass.TEST
        return FailureClass.INFRA

    metadata = ((result.get("agent_result") or {}).get("metadata")) or {}
    if metadata.get("detected_task") == "unknown":
        return FailureClass.MODEL

    reward = _reward(result)
    if reward is None:
        return FailureClass.INFRA
    if reward >= 1:
        return FailureClass.OK
    return FailureClass.TEST
