from agent_skill_bench.agents.base_solver import DeterministicSolver


class PlanSolver(DeterministicSolver):
    """Plan-oriented agent. Uses skills and benefits from plan prompts in profiles."""

    @staticmethod
    def name() -> str:
        return "plan-solver"

    def uses_skills(self) -> bool:
        return True
