"""Pre-registered Harbor retry policy.

Infra errors may be retried. Agent, model, and test outcomes are never retried
and never counted as the other class.
"""

from __future__ import annotations

from typing import Any

from agent_skill_bench.constants import (
    INFRA_RETRY_EXCEPTIONS,
    RETRY_EXCLUDE_EXCEPTIONS,
)


DEFAULT_MAX_RETRIES = 2


def harbor_retry(max_retries: int | None = None) -> dict[str, Any]:
    retries = DEFAULT_MAX_RETRIES if max_retries is None else max_retries
    return {
        "max_retries": retries,
        "include_exceptions": list(INFRA_RETRY_EXCEPTIONS),
        "exclude_exceptions": list(RETRY_EXCLUDE_EXCEPTIONS),
        "wait_multiplier": 1.0,
        "min_wait_sec": 1.0,
        "max_wait_sec": 60.0,
    }
