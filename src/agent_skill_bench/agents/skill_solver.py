from agent_skill_bench.agents.base_solver import DeterministicSolver


class SkillSolver(DeterministicSolver):
    """Skill-aware agent. Loads injected SKILL.md files and records hashes."""

    @staticmethod
    def name() -> str:
        return "skill-solver"

    def uses_skills(self) -> bool:
        return True
