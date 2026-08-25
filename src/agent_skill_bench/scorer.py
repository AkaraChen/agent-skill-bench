"""Execution scorer: tests are primary; infra is excluded from model failure.

Human rubric packets are blinded (no agent/model/treatment). An LLM judge,
if present, is auxiliary only and never the source of reward.
"""

from __future__ import annotations

from typing import Any

from agent_skill_bench.classify import FailureClass, classify_trial
from agent_skill_bench.constants import SCORER_VERSION
from agent_skill_bench.stage7 import STAGE7_RUBRIC_AXES

RUBRIC_AXES = (
    {"id": "maintainability", "scale": "1-5", "prompt": "How easy is this change to maintain?"},
    {"id": "security", "scale": "1-5", "prompt": "Does the change introduce or leave security issues?"},
    {"id": "clarity", "scale": "1-5", "prompt": "Is the resulting code readable and named honestly?"},
)


def score_trial(result: dict[str, Any]) -> dict[str, Any]:
    failure = classify_trial(result)
    verifier = result.get("verifier_result") or {}
    rewards = verifier.get("rewards") or {}
    agent = result.get("agent_result") or {}
    reward = rewards.get("reward")
    infra = failure is FailureClass.INFRA
    return {
        "scorer_version": SCORER_VERSION,
        "failure_class": failure.value,
        "reward": reward,
        "execution_pass": failure is FailureClass.OK,
        "infra_error": infra,
        "counted_as_model_failure": failure is FailureClass.MODEL,
        "counted_as_test_failure": failure is FailureClass.TEST,
        "counted_as_agent_failure": failure is FailureClass.AGENT,
        "cost_usd": agent.get("cost_usd"),
        "n_input_tokens": agent.get("n_input_tokens"),
        "n_output_tokens": agent.get("n_output_tokens"),
        "llm_judge_auxiliary": True,
        "llm_judge": None,
        "primary_signal": "hidden_tests",
    }


def rubric_packet(*, instruction: str, files: dict[str, str], task_id: str = "") -> dict[str, Any]:
    """Blinded packet: no agent, model, treatment, or reward."""
    return {
        "schema": "asb.rubric.v1",
        "scorer_version": SCORER_VERSION,
        "task_id": task_id,
        "instruction": instruction,
        "files": files,
        "axes": list(RUBRIC_AXES),
        "llm_judge_auxiliary": True,
        "note": "Fill scores without seeing model, agent, prompt, or skill identity.",
    }


def stage7_rubric_packet(*, instruction: str, files: dict[str, str], task_id: str = "") -> dict[str, Any]:
    """Blinded Stage 7 packet. Axes include UI/visual/review/cost; still no identity."""
    packet = rubric_packet(instruction=instruction, files=files, task_id=task_id)
    packet["schema"] = "asb.rubric.stage7.v1"
    packet["axes"] = list(STAGE7_RUBRIC_AXES)
    packet["no_composite_total"] = True
    return packet


def llm_judge_auxiliary(_packet: dict[str, Any]) -> None:
    """Intentionally unused. Hidden tests own the reward."""
    return None
