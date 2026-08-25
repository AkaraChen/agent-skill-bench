from agent_skill_bench.classify import FailureClass
from agent_skill_bench.constants import SCORER_VERSION
from agent_skill_bench.scorer import llm_judge_auxiliary, rubric_packet, score_trial


def test_infra_is_not_model_failure() -> None:
    scored = score_trial(
        {
            "exception_info": {
                "exception_type": "SandboxBuildFailedError",
                "exception_message": "docker build failed",
            }
        }
    )
    assert scored["failure_class"] == FailureClass.INFRA.value
    assert scored["infra_error"] is True
    assert scored["counted_as_model_failure"] is False
    assert scored["scorer_version"] == SCORER_VERSION
    assert scored["primary_signal"] == "hidden_tests"


def test_wrong_implementation_counts_as_model_failure() -> None:
    scored = score_trial({"verifier_result": {"rewards": {"reward": 0}}})
    assert scored["counted_as_model_failure"] is True
    assert scored["counted_as_test_failure"] is False
    assert scored["infra_error"] is False


def test_verifier_exception_is_not_model_failure() -> None:
    scored = score_trial(
        {
            "exception_info": {
                "exception_type": "RewardFileNotFoundError",
                "exception_message": "missing reward file",
            }
        }
    )
    assert scored["failure_class"] == FailureClass.TEST.value
    assert scored["counted_as_model_failure"] is False
    assert scored["counted_as_test_failure"] is True


def test_rubric_packet_is_blinded() -> None:
    packet = rubric_packet(
        instruction="do a thing",
        files={"output.txt": "1\n"},
        task_id="asb-private-holdout/clamp-range",
    )
    blob = str(packet)
    assert "agent" not in packet
    assert "model" not in packet
    assert "treatment" not in packet
    assert "reward" not in packet
    assert packet["llm_judge_auxiliary"] is True
    assert "naive-solver" not in blob
    assert llm_judge_auxiliary(packet) is None
