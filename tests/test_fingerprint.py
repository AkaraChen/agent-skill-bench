from agent_skill_bench.fingerprint import build_fingerprint


def test_fingerprint_is_stable_and_unique() -> None:
    common = dict(
        task_name="asb/reverse-string",
        task_checksum="sha256:aaa",
        agent_name="naive-solver",
        agent_version="0.1.0",
        treatment="baseline",
        prompt_name="baseline",
        prompt_sha256="sha256:bbb",
        skill_bundle=[],
        harness_commit="abc",
        network_mode="no-network",
        agent_timeout_sec=60,
        verifier_timeout_sec=60,
    )
    a = build_fingerprint(trial_id="t1", **common)
    b = build_fingerprint(trial_id="t2", **common)
    assert a["fingerprint"] == b["fingerprint"]
    assert a["trial_id"] != b["trial_id"]

    changed = dict(common)
    changed["treatment"] = "candidate"
    changed["skill_bundle"] = [{"order": "0", "name": "test-first", "digest": "sha256:ccc"}]
    c = build_fingerprint(trial_id="t3", **changed)
    assert c["fingerprint"] != a["fingerprint"]
