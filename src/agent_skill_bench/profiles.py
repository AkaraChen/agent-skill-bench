"""Deterministic model capability profiles for Track A research fixtures.

These are not claims about hosted LLMs. They encode controllable interactions
so Stage 5 can exercise screening → confirmation → playbook generation under
a fixed harness (Track A). Applicability: harness-only unless re-run on Track B.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Revision pin for Stage 5 methodology package.
STAGE5_REVISION = "stage5-method-2026.08.26.r1"

PUBLIC_TASKS = {
    "reverse-string",
    "fizzbuzz",
    "csv-sum",
    "json-merge",
    "slugify",
}

PRIVATE_TASKS = {
    "clamp-range",
    "unique-lines",
    "csv-threshold",
    "word-freq",
    "path-jail",
    "redact-tokens",
}

EASY = {
    "reverse-string",
    "fizzbuzz",
    "csv-sum",
    "slugify",
    "clamp-range",
    "unique-lines",
    "csv-threshold",
    "redact-tokens",
}
MEDIUM = {"json-merge", "word-freq", "path-jail"}
SECURITY = {"path-jail", "redact-tokens"}


@dataclass(frozen=True)
class Decision:
    solve: bool
    failure_mode: str | None
    cost_usd: float
    reason: str


def normalize_model(model: str | None) -> str:
    raw = (model or "").strip()
    if raw in {"deterministic/smoke-solver@2026-08-24", "deterministic/smoke-solver"}:
        return "alpha"
    for name in ("alpha", "beta", "gamma"):
        if name in raw:
            return name
    return "alpha"


def detect_task(instruction: str) -> str:
    text = instruction.lower()
    if "reverse" in text:
        return "reverse-string"
    if "fizzbuzz" in text or "fizz buzz" in text:
        return "fizzbuzz"
    if "threshold" in text and ("output.csv" in text or "tsv" in text):
        return "csv-threshold"
    if "stopwords" in text or "freq.txt" in text:
        return "word-freq"
    if "clamp" in text or "half-open" in text:
        return "clamp-range"
    if "unique lines" in text or "last-seen" in text:
        return "unique-lines"
    if "path.txt" in text or "blocked" in text:
        return "path-jail"
    if "ak_" in text or "sk-" in text or "redact" in text:
        return "redact-tokens"
    if "slug" in text:
        return "slugify"
    if "json" in text and "merge" in text:
        return "json-merge"
    if "csv" in text or "amount" in text:
        return "csv-sum"
    return "unknown"


def decide(
    *,
    model: str | None,
    agent: str,
    prompt_name: str,
    skills_loaded: list[str],
    task: str,
) -> Decision:
    """Return whether this cell should solve, with a failure taxonomy label."""
    profile = normalize_model(model)
    uses_skills = agent in {"skill-solver", "plan-solver"}
    skill_names = skills_loaded if uses_skills else []
    has_test_first = "test-first" in skill_names
    has_review = "review-gate" in skill_names
    is_plan = prompt_name in {"plan", "candidate"} or "plan" in prompt_name
    plan_agent = agent == "plan-solver"

    # Cost: gamma expensive, skills/plan add latency tax.
    cost = {"alpha": 0.002, "beta": 0.008, "gamma": 0.02}.get(profile, 0.005)
    if is_plan:
        cost *= 1.25
    if skill_names:
        cost *= 1.15 + 0.05 * len(skill_names)
    if plan_agent:
        cost *= 1.1

    if task == "unknown":
        return Decision(False, "unknown_task", cost, "instruction not mapped")

    # Alpha: strong easy baseline; skills ignored (even if loaded); medium security needs review.
    if profile == "alpha":
        if task in EASY and task not in SECURITY:
            return Decision(True, None, cost, "alpha easy baseline")
        if task in SECURITY:
            if uses_skills and has_review:
                return Decision(True, None, cost * 1.05, "alpha security via review-gate")
            return Decision(False, "security_miss", cost, "alpha security without review skill")
        if task in MEDIUM:
            if is_plan or plan_agent:
                return Decision(True, None, cost, "alpha medium with plan cue")
            return Decision(False, "incomplete_medium", cost, "alpha medium without plan")
        return Decision(False, "unsupported", cost, "alpha unsupported")

    # Beta: scaffolding-dependent. Prompt gain mostly stable; skills help only skill-aware agents.
    if profile == "beta":
        if task in EASY and task not in SECURITY:
            if is_plan or has_test_first or plan_agent:
                return Decision(True, None, cost, "beta easy with scaffold")
            return Decision(False, "no_scaffold", cost, "beta easy needs plan or test-first")
        if task in SECURITY:
            if uses_skills and has_test_first and has_review:
                return Decision(True, None, cost, "beta security with both skills")
            if uses_skills and has_test_first:
                return Decision(False, "security_partial", cost, "beta security incomplete skill bundle")
            return Decision(False, "security_miss", cost, "beta security without skills")
        if task in MEDIUM:
            if (is_plan or plan_agent) and uses_skills and has_test_first:
                return Decision(True, None, cost, "beta medium complementary plan+skill")
            if is_plan and not has_test_first:
                return Decision(False, "plan_without_skill", cost, "beta medium plan alone insufficient")
            if has_test_first and uses_skills and not is_plan:
                return Decision(False, "skill_without_plan", cost, "beta medium skill alone insufficient")
            return Decision(False, "no_scaffold", cost, "beta medium needs plan+skill")
        return Decision(False, "unsupported", cost, "beta unsupported")

    # Gamma: brittle; plan helps easy; plan+skill conflicts on security; order matters when both skills.
    if profile == "gamma":
        if task in SECURITY:
            if uses_skills and has_test_first and has_review:
                # Conflict: loading both skills makes gamma over-refuse / corrupt output.
                return Decision(False, "skill_conflict", cost, "gamma plan/skill conflict on security")
            if uses_skills and has_review and not has_test_first:
                return Decision(True, None, cost, "gamma security review-only")
            return Decision(False, "security_miss", cost, "gamma security miss")
        if task in EASY:
            if is_plan or plan_agent or (uses_skills and has_test_first):
                return Decision(True, None, cost, "gamma easy with cue")
            return Decision(False, "brittle_baseline", cost, "gamma fails bare baseline")
        if task in MEDIUM:
            if uses_skills and has_test_first and has_review:
                # Order effect encoded via skill list order from caller.
                if skill_names and skill_names[0] == "review-gate":
                    return Decision(False, "skill_order_conflict", cost, "gamma review-first order fails medium")
                return Decision(True, None, cost, "gamma medium test-first then review")
            if is_plan and plan_agent:
                return Decision(True, None, cost, "gamma medium plan-solver")
            return Decision(False, "brittle_medium", cost, "gamma medium miss")
        return Decision(False, "unsupported", cost, "gamma unsupported")

    return Decision(False, "unknown_profile", cost, f"no profile for {profile}")


def failure_taxonomy() -> dict[str, str]:
    return {
        "unknown_task": "Instruction did not map to a known task family.",
        "security_miss": "Security task failed without an appropriate skill.",
        "security_partial": "Partial skill bundle on security task.",
        "incomplete_medium": "Medium task incomplete without planning cue.",
        "no_scaffold": "Model needs prompt or skill scaffolding.",
        "plan_without_skill": "Plan prompt alone insufficient for task slice.",
        "skill_without_plan": "Skill alone insufficient for task slice.",
        "skill_conflict": "Combined skills conflict for this model/task.",
        "skill_order_conflict": "Skill load order caused failure.",
        "brittle_baseline": "Bare baseline prompt failed on a brittle model.",
        "brittle_medium": "Medium task failed on brittle model.",
        "unsupported": "Task outside profile support.",
        "unknown_profile": "Model snapshot has no profile.",
        "deliberate_wrong": "Solved path skipped; wrong/empty artifact written.",
    }


def profile_manifest() -> dict[str, Any]:
    return {
        "revision": STAGE5_REVISION,
        "track": "A",
        "applicability": "fixed-harness-only",
        "models": [
            "deterministic/alpha@2026-08-26",
            "deterministic/beta@2026-08-26",
            "deterministic/gamma@2026-08-26",
        ],
        "failure_taxonomy": failure_taxonomy(),
        "note": (
            "Profiles are research fixtures for methodology delivery. "
            "Do not treat outcomes as evidence about hosted LLM products."
        ),
    }
