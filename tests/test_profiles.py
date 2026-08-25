from agent_skill_bench.profiles import decide, detect_task, normalize_model


def test_detect_private_and_public() -> None:
    assert detect_task("Reverse the contents") == "reverse-string"
    assert detect_task("Clamp each integer into the half-open interval") == "clamp-range"
    assert detect_task("Write /app/freq.txt and stopwords") == "word-freq"
    assert detect_task("path.txt and write blocked") == "path-jail"


def test_alpha_ignores_skills_on_easy_but_needs_review_on_security() -> None:
    ok = decide(
        model="deterministic/alpha@2026-08-26",
        agent="naive-solver",
        prompt_name="baseline",
        skills_loaded=[],
        task="reverse-string",
    )
    assert ok.solve is True
    miss = decide(
        model="deterministic/alpha@2026-08-26",
        agent="naive-solver",
        prompt_name="baseline",
        skills_loaded=["review-gate"],
        task="path-jail",
    )
    assert miss.solve is False
    assert miss.failure_mode == "security_miss"
    fixed = decide(
        model="deterministic/alpha@2026-08-26",
        agent="skill-solver",
        prompt_name="baseline",
        skills_loaded=["review-gate"],
        task="path-jail",
    )
    assert fixed.solve is True


def test_beta_needs_plan_and_skill_on_medium() -> None:
    bare = decide(
        model="deterministic/beta@2026-08-26",
        agent="skill-solver",
        prompt_name="baseline",
        skills_loaded=["test-first"],
        task="word-freq",
    )
    assert bare.solve is False
    assert bare.failure_mode == "skill_without_plan"
    both = decide(
        model="deterministic/beta@2026-08-26",
        agent="skill-solver",
        prompt_name="plan",
        skills_loaded=["test-first"],
        task="word-freq",
    )
    assert both.solve is True


def test_gamma_skill_conflict_and_order() -> None:
    conflict = decide(
        model="deterministic/gamma@2026-08-26",
        agent="skill-solver",
        prompt_name="plan",
        skills_loaded=["test-first", "review-gate"],
        task="path-jail",
    )
    assert conflict.solve is False
    assert conflict.failure_mode == "skill_conflict"
    bad_order = decide(
        model="deterministic/gamma@2026-08-26",
        agent="skill-solver",
        prompt_name="plan",
        skills_loaded=["review-gate", "test-first"],
        task="word-freq",
    )
    assert bad_order.solve is False
    assert bad_order.failure_mode == "skill_order_conflict"
    good_order = decide(
        model="deterministic/gamma@2026-08-26",
        agent="skill-solver",
        prompt_name="plan",
        skills_loaded=["test-first", "review-gate"],
        task="word-freq",
    )
    assert good_order.solve is True


def test_normalize_smoke_alias() -> None:
    assert normalize_model("deterministic/smoke-solver@2026-08-24") == "alpha"
