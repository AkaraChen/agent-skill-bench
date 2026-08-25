from agent_skill_bench.stats import (
    interaction_bootstrap,
    mcnemar_exact,
    paired_bootstrap,
    paired_outcomes,
    pass_at_k,
    report,
    slice_table,
)


def test_mcnemar_symmetric_is_one() -> None:
    result = mcnemar_exact(0, 0)
    assert result["p_value"] == 1.0
    assert mcnemar_exact(3, 3)["p_value"] == 1.0


def test_mcnemar_detects_one_sided_shift() -> None:
    result = mcnemar_exact(8, 0)
    assert result["p_value"] < 0.01
    assert result["n01"] == 8


def _rows() -> list[dict]:
    rows = []
    # 4 tasks, two agents. Candidate wins on naive, ties on skill.
    for task in ("a", "b", "c", "d"):
        for agent, baseline, candidate in (
            ("naive-solver", False, True),
            ("skill-solver", True, True),
        ):
            for treatment, ok in (("baseline", baseline), ("candidate", candidate)):
                rows.append(
                    {
                        "task": task,
                        "agent": agent,
                        "model": "snap",
                        "treatment": treatment,
                        "prompt": treatment,
                        "pair_id": "baseline__candidate",
                        "reward": 1.0 if ok else 0.0,
                        "failure_class": "ok" if ok else "model",
                        "infra_error": False,
                        "cost_usd": 0.2 if treatment == "candidate" else 0.1,
                        "duration_sec": 10.0,
                    }
                )
    return rows


def test_paired_bootstrap_and_mcnemar() -> None:
    pairs = paired_outcomes(_rows(), "baseline", "candidate")
    assert len(pairs) == 8
    stats = paired_bootstrap(pairs, n=200, seed=1)
    assert stats["mean_diff"] == 0.5
    assert stats["ci"]["low"] is not None
    assert stats["mcnemar"]["n01"] == 4
    assert stats["mcnemar"]["n10"] == 0
    # 4 discordant pairs (4-0) → exact two-sided p = 2/16 = 0.125
    assert stats["mcnemar"]["p_value"] == 0.125


def test_infra_is_dropped_from_success() -> None:
    rows = _rows()
    rows.append(
        {
            "task": "a",
            "agent": "naive-solver",
            "model": "snap",
            "treatment": "baseline",
            "failure_class": "infra",
            "infra_error": True,
            "reward": 0,
        }
    )
    pairs = paired_outcomes(rows, "baseline", "candidate")
    assert len(pairs) == 8


def test_slices_have_no_composite_score() -> None:
    table = slice_table(_rows(), ("agent", "treatment"))
    assert {row["agent"] for row in table} == {"naive-solver", "skill-solver"}
    for row in table:
        assert "score" not in row
        assert "success_rate" in row
        assert "cost_usd_mean" in row
        assert "failures" in row


def test_interaction_bootstrap_finds_agent_contrast() -> None:
    result = interaction_bootstrap(
        _rows(),
        treatment_left="baseline",
        treatment_right="candidate",
        factor="agent",
        n=200,
        seed=1,
    )
    assert result["gaps"]["naive-solver"]["mean"] == 1.0
    assert result["gaps"]["skill-solver"]["mean"] == 0.0
    contrast = result["contrast"]
    assert contrast is not None
    assert contrast["mean"] != 0


def test_pass_hat_k_needs_repeats() -> None:
    once = pass_at_k(_rows(), 1)
    assert once["n"] == 16
    assert once["pass_hat_k"] == 0.75
    assert pass_at_k(_rows(), 3)["n"] == 0


def test_report_keeps_disclaimer() -> None:
    payload = report(_rows(), n_boot=50, seed=0)
    assert "not a single score" in payload["disclaimer"]
    assert "paired" in payload
    assert "interaction" in payload
    assert payload["slices"]["task"]


def test_paired_outcomes_repeat_order_invariant() -> None:
    def row(treatment: str, ok: bool) -> dict:
        return {
            "task": "t",
            "agent": "a",
            "model": "m",
            "treatment": treatment,
            "pair_id": "baseline__candidate",
            "reward": 1.0 if ok else 0.0,
            "failure_class": "ok" if ok else "model",
            "infra_error": False,
        }

    # Last-wins would be baseline=False, candidate=True, diff=1.
    # Reversed last-wins would be diff=-1. Mean of repeats is 0.5 vs 0.5.
    forward = [
        row("baseline", True),
        row("baseline", False),
        row("candidate", False),
        row("candidate", True),
    ]
    backward = list(reversed(forward))
    a = paired_outcomes(forward, "baseline", "candidate")
    b = paired_outcomes(backward, "baseline", "candidate")
    assert len(a) == 1 and len(b) == 1
    assert a[0]["diff"] == 0.0
    assert a[0]["diff"] == b[0]["diff"]
    assert a[0]["left_rate"] == b[0]["left_rate"] == 0.5
    assert a[0]["right_rate"] == b[0]["right_rate"] == 0.5
    assert a[0]["left_pass"] == b[0]["left_pass"]
    assert a[0]["n_left"] == 2
    assert paired_bootstrap(a, n=50, seed=0)["mean_diff"] == 0.0
