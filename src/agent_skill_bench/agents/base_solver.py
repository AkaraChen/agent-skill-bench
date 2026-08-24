from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment, ExecResult
from harbor.models.agent.context import AgentContext

from agent_skill_bench.constants import HIDDEN_CANARY, repo_root

SOLVE_SCRIPT = r'''
from pathlib import Path
import csv
import json
import re
import sys

instruction = Path("/tmp/asb_instruction.txt").read_text()
text = instruction.lower()

def detect():
    if "reverse" in text:
        return "reverse-string"
    if "fizzbuzz" in text or "fizz buzz" in text:
        return "fizzbuzz"
    if "csv" in text or "amount" in text:
        return "csv-sum"
    if "json" in text and "merge" in text:
        return "json-merge"
    if "slug" in text:
        return "slugify"
    return "unknown"

def solve_reverse():
    src = Path("/app/input.txt").read_text()
    Path("/app/output.txt").write_text(src[::-1])

def solve_fizzbuzz():
    n = int(Path("/app/n.txt").read_text().strip())
    lines = []
    for i in range(1, n + 1):
        if i % 15 == 0:
            lines.append("FizzBuzz")
        elif i % 3 == 0:
            lines.append("Fizz")
        elif i % 5 == 0:
            lines.append("Buzz")
        else:
            lines.append(str(i))
    Path("/app/output.txt").write_text("\n".join(lines) + "\n")

def solve_csv_sum():
    total = 0
    with Path("/app/data.csv").open() as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            total += int(row["amount"])
    Path("/app/output.txt").write_text(str(total) + "\n")

def solve_json_merge():
    a = json.loads(Path("/app/a.json").read_text())
    b = json.loads(Path("/app/b.json").read_text())
    merged = {**a, **b}
    Path("/app/merged.json").write_text(
        json.dumps(merged, separators=(",", ":"), sort_keys=True) + "\n"
    )

def solve_slugify():
    raw = Path("/app/title.txt").read_text().strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    Path("/app/slug.txt").write_text(slug + "\n")

SOLVERS = {
    "reverse-string": solve_reverse,
    "fizzbuzz": solve_fizzbuzz,
    "csv-sum": solve_csv_sum,
    "json-merge": solve_json_merge,
    "slugify": solve_slugify,
}

task = detect()
Path("/tmp/asb_detected_task.txt").write_text(task)
if task not in SOLVERS:
    sys.exit(2)
SOLVERS[task]()
'''

LEAKAGE_SCRIPT = r'''
from pathlib import Path
import json

CANARY = "ASB_HIDDEN_CANARY_DO_NOT_LEAK_9f3c"

def exists(path: str) -> bool:
    return Path(path).exists()

def scan(roots):
    hits = []
    for root in roots:
        p = Path(root)
        if not p.exists():
            continue
        files = [p] if p.is_file() else [f for f in p.rglob("*") if f.is_file()]
        for f in files:
            try:
                if CANARY in f.read_text(errors="ignore"):
                    hits.append(str(f))
            except OSError:
                continue
    return hits

probe = {
    "tests_exists": exists("/tests"),
    "solution_exists": exists("/solution"),
    "canary_hits": scan(["/app", "/tests", "/solution", "/instruction.md", "/instructions.md"]),
}
Path("/tmp/asb_leakage_probe.json").write_text(json.dumps(probe, indent=2) + "\n")
print(json.dumps(probe))
'''


class DeterministicSolver(BaseAgent):
    """Host-side Harbor agent that solves smoke tasks inside the container."""

    AGENT_VERSION = "0.1.0"

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        prompt_name: str = "baseline",
        prompt_path: str | None = None,
        **kwargs: Any,
    ):
        super().__init__(logs_dir=logs_dir, model_name=model_name, **kwargs)
        self.prompt_name = prompt_name
        self.prompt_path = Path(prompt_path) if prompt_path else None
        self._events: list[dict[str, Any]] = []

    def version(self) -> str:
        return self.AGENT_VERSION

    async def setup(self, environment: BaseEnvironment) -> None:
        return

    def _log(self, event: str, **payload: Any) -> None:
        self._events.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "event": event,
                **payload,
            }
        )

    def _read_prompt(self) -> tuple[str, str]:
        if self.prompt_path is None:
            text = ""
        else:
            path = self.prompt_path
            if not path.is_absolute():
                path = repo_root() / path
            text = path.read_text()
        digest = "sha256:" + hashlib.sha256(text.encode()).hexdigest()
        return text, digest

    def uses_skills(self) -> bool:
        return False

    async def _exec_python(self, environment: BaseEnvironment, code: str) -> ExecResult:
        payload = base64.b64encode(code.encode()).decode()
        return await environment.exec(
            command=(
                "python3 -c "
                f"'import base64; exec(base64.b64decode(\"{payload}\").decode())'"
            )
        )

    async def _probe_leakage(self, environment: BaseEnvironment) -> dict[str, Any]:
        result = await self._exec_python(environment, LEAKAGE_SCRIPT)
        raw = (result.stdout or "").strip()
        try:
            probe = json.loads(raw.splitlines()[-1]) if raw else {}
        except json.JSONDecodeError:
            probe = {
                "parse_error": True,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.return_code,
            }
        (self.logs_dir / "leakage_probe.json").write_text(
            json.dumps(probe, indent=2) + "\n"
        )
        self._log("leakage_probe", **probe)
        return probe

    async def _inspect_skills(self, environment: BaseEnvironment) -> dict[str, Any]:
        skills_dir = self.skills_dir
        record: dict[str, Any] = {
            "agent": self.name(),
            "uses_skills": self.uses_skills(),
            "skills_dir": skills_dir,
            "loaded": [],
            "ignored": not self.uses_skills(),
        }
        if not skills_dir:
            record["present"] = False
            (self.logs_dir / "skills.json").write_text(json.dumps(record, indent=2) + "\n")
            self._log("skills", **record)
            return record

        inspect_script = f"""
from pathlib import Path
import json, hashlib
root = Path({skills_dir!r})
payload = {{
    "exists": root.exists(),
    "items": [],
}}
if root.exists():
    for skill_md in sorted(root.glob("*/SKILL.md")):
        payload["items"].append({{
            "name": skill_md.parent.name,
            "path": str(skill_md),
            "sha256": hashlib.sha256(skill_md.read_bytes()).hexdigest(),
        }})
print(json.dumps(payload))
"""
        listing = await self._exec_python(environment, inspect_script)
        stdout = (listing.stdout or "").strip()
        present = False
        loaded: list[dict[str, Any]] = []
        try:
            payload = json.loads(stdout.splitlines()[-1]) if stdout else {}
            present = bool(payload.get("exists"))
            loaded = list(payload.get("items") or [])
        except json.JSONDecodeError:
            loaded = []
        record["present"] = present
        record["found"] = loaded
        if self.uses_skills():
            record["loaded"] = loaded
            record["ignored"] = False
            if loaded:
                marker = {
                    "skill": loaded[0]["name"],
                    "sha256": loaded[0]["sha256"],
                    "applied": True,
                    "agent": self.name(),
                }
                marker_json = json.dumps(marker)
                await self._exec_python(
                    environment,
                    "from pathlib import Path\n"
                    f"Path('/app/skill_applied.json').write_text({marker_json!r} + chr(10))\n",
                )
                self._log(
                    "skill_loaded",
                    skill=loaded[0]["name"],
                    sha256=loaded[0]["sha256"],
                )
        else:
            self._log(
                "skills_ignored",
                skills_dir=skills_dir,
                found=[item.get("name") for item in loaded],
            )
        (self.logs_dir / "skills.json").write_text(json.dumps(record, indent=2) + "\n")
        self._log("skills", **record)
        return record

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        prompt_text, prompt_digest = self._read_prompt()
        self._log(
            "start",
            agent=self.name(),
            version=self.version(),
            model=self.model_name,
            prompt_name=self.prompt_name,
            prompt_sha256=prompt_digest,
        )
        (self.logs_dir / "prompt.md").write_text(
            f"# {self.prompt_name}\n\n{prompt_text}"
        )
        (self.logs_dir / "instruction.md").write_text(instruction)
        await self._exec_python(
            environment,
            "from pathlib import Path\n"
            f"Path('/tmp/asb_instruction.txt').write_text({instruction!r})\n",
        )

        await self._probe_leakage(environment)
        skills = await self._inspect_skills(environment)

        solve = await self._exec_python(environment, SOLVE_SCRIPT)
        detected = await environment.exec(
            command="cat /tmp/asb_detected_task.txt 2>/dev/null || true"
        )
        task_name = (detected.stdout or "").strip() or "unknown"
        self._log(
            "solve",
            task=task_name,
            return_code=solve.return_code,
            stderr=(solve.stderr or "")[:500],
        )
        if solve.return_code != 0:
            self._log("model_unsolved", task=task_name, return_code=solve.return_code)

        diff = await environment.exec(
            command=(
                "python3 -c "
                "\"import json,pathlib; "
                "files={}; "
                "[files.update({str(p): p.read_text(errors='replace')}) "
                "for p in pathlib.Path('/app').iterdir() if p.is_file()]; "
                "print(json.dumps(files))\""
            )
        )
        (self.logs_dir / "workspace.json").write_text(diff.stdout or "{}")
        self._log("workspace_snapshot", bytes=len(diff.stdout or ""))

        events_path = self.logs_dir / "trajectory.jsonl"
        events_path.write_text(
            "".join(json.dumps(event) + "\n" for event in self._events)
        )

        prompt_tokens = max(1, len(prompt_text + instruction) // 4)
        output_tokens = max(1, len(diff.stdout or "") // 4)
        context.n_input_tokens = prompt_tokens
        context.n_output_tokens = output_tokens
        context.cost_usd = 0.0
        context.metadata = {
            "prompt_name": self.prompt_name,
            "prompt_sha256": prompt_digest,
            "skills": skills,
            "detected_task": task_name,
            "agent": self.name(),
            "agent_version": self.version(),
        }
        self._log("done")
        events_path.write_text(
            "".join(json.dumps(event) + "\n" for event in self._events)
        )
