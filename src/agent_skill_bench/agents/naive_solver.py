from agent_skill_bench.agents.base_solver import DeterministicSolver


class NaiveSolver(DeterministicSolver):
    """Instruction-only agent. Ignores injected skills even when present."""

    @staticmethod
    def name() -> str:
        return "naive-solver"

    def uses_skills(self) -> bool:
        return False
