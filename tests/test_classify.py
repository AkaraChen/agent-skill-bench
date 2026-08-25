from agent_skill_bench.classify import FailureClass, classify_trial


def test_ok_when_reward_one() -> None:
    result = {"verifier_result": {"rewards": {"reward": 1}}}
    assert classify_trial(result) is FailureClass.OK


def test_hidden_test_failure_is_model() -> None:
    result = {"verifier_result": {"rewards": {"reward": 0}}}
    assert classify_trial(result) is FailureClass.MODEL


def test_verifier_exception_is_test_not_model() -> None:
    result = {
        "exception_info": {
            "exception_type": "VerifierTimeoutError",
            "exception_message": "verifier exceeded timeout",
        }
    }
    assert classify_trial(result) is FailureClass.TEST


def test_infra_on_docker_exception() -> None:
    result = {
        "exception_info": {
            "exception_type": "SandboxBuildFailedError",
            "exception_message": "docker build failed",
        }
    }
    assert classify_trial(result) is FailureClass.INFRA


def test_agent_on_agent_timeout() -> None:
    result = {
        "exception_info": {
            "exception_type": "AgentTimeoutError",
            "exception_message": "agent exceeded timeout",
        }
    }
    assert classify_trial(result) is FailureClass.AGENT


def test_model_when_task_undetected() -> None:
    result = {
        "agent_result": {"metadata": {"detected_task": "unknown"}},
        "verifier_result": {"rewards": {"reward": 0}},
    }
    assert classify_trial(result) is FailureClass.MODEL
