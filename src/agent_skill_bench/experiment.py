"""Expand a versioned experiment YAML into a Harbor job config.

ponytail: treatments are the factorial unit. Sample ints with pairs draw
(agent, model) groups so paired arms stay together. Resume is Harbor's
`job resume`, not a second runner.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml
from harbor.agents.installed.acp_registry import is_acp_registry_shorthand
from harbor.models.agent.name import AgentName

from agent_skill_bench.fingerprint import canonical_dumps, sha256_text, sha256_tree
from agent_skill_bench.retry_policy import harbor_retry

SCHEMA_VERSION = 1
ASB_RESERVED_KWARGS = {
    "prompt_name",
    "prompt_path",
    "asb_treatment",
    "asb_track",
    "asb_skill_bundle",
    "asb_seed",
    "asb_pair_id",
    "asb_pairing_key",
}


class ExperimentError(ValueError):
    """Invalid experiment spec or a dry-run limit that would explode."""


@dataclass(frozen=True)
class Cell:
    agent: str
    import_path: str | None
    model: str
    treatment: str
    prompt_name: str
    prompt_path: str | None
    skill_bundle: str
    skills: tuple[str, ...]
    kind: str  # harbor | acp | import
    agent_kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DatasetRef:
    name: str | None = None
    path: str | None = None
    version: str | None = None
    ref: str | None = None
    n_tasks: int | None = None
    task_names: tuple[str, ...] = ()
    exclude_task_names: tuple[str, ...] = ()
    resolved_n_tasks: int = 0

    def to_harbor(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.name:
            payload["name"] = self.name
        if self.path:
            payload["path"] = self.path
        if self.version:
            payload["version"] = self.version
        if self.ref:
            payload["ref"] = self.ref
        if self.n_tasks is not None:
            payload["n_tasks"] = self.n_tasks
        if self.task_names:
            payload["task_names"] = list(self.task_names)
        if self.exclude_task_names:
            payload["exclude_task_names"] = list(self.exclude_task_names)
        return payload


@dataclass
class Plan:
    name: str
    track: str
    seed: int
    repeat: int
    max_trials: int
    n_concurrent: int
    max_retries: int
    usd_per_trial: float
    budget_usd: float | None
    environment: dict[str, Any]
    tasks: list[str]
    cells: list[Cell]
    pairs: list[tuple[str, str]]
    selection: dict[str, Any] = field(default_factory=dict)
    skill_hashes: list[dict[str, str]] = field(default_factory=list)
    datasets: list[DatasetRef] = field(default_factory=list)
    retry: dict[str, Any] = field(default_factory=dict)
    assemble_sealed: bool = False
    assembled_path: str = "jobs/.assembled/holdout"

    @property
    def n_cells(self) -> int:
        return len(self.cells)

    @property
    def n_task_units(self) -> int:
        return len(self.tasks) + sum(item.resolved_n_tasks for item in self.datasets)

    @property
    def n_trials(self) -> int:
        return self.n_cells * self.n_task_units * self.repeat

    @property
    def estimated_usd(self) -> float | None:
        if self.usd_per_trial <= 0:
            return None
        return self.n_trials * self.usd_per_trial


def is_experiment(data: dict[str, Any]) -> bool:
    return "schema_version" in data


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text())
    if not isinstance(payload, dict):
        raise ExperimentError(f"YAML root must be a mapping: {path}")
    return payload


def _require(spec: dict[str, Any], key: str) -> Any:
    if key not in spec:
        raise ExperimentError(f"Missing required field: {key}")
    return spec[key]


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _agent_kind(name: str, import_path: str | None) -> str:
    if import_path:
        return "import"
    if is_acp_registry_shorthand(name):
        return "acp"
    if name in AgentName.values():
        return "harbor"
    raise ExperimentError(
        f"Unknown agent {name!r}. Use a Harbor built-in name "
        f"({sorted(AgentName.values())}), an acp:<registry-id> shorthand, "
        "or set import_path."
    )


def _match(cell: Cell, filt: dict[str, Any]) -> bool:
    mapping = {
        "agent": cell.agent,
        "model": cell.model,
        "treatment": cell.treatment,
        "prompt": cell.prompt_name,
        "skill_bundle": cell.skill_bundle,
    }
    for key, expected in filt.items():
        if key not in mapping:
            raise ExperimentError(f"Unknown include/exclude key: {key}")
        if mapping[key] != expected:
            return False
    return True


def _bundle_name(skills: list[str], explicit: str | None) -> str:
    if explicit:
        return explicit
    if not skills:
        return "none"
    return "+".join(Path(item).name for item in skills)


def _prompts(spec: dict[str, Any]) -> dict[str, str]:
    raw = spec.get("prompts") or {}
    if isinstance(raw, dict):
        return {str(name): str(path) for name, path in raw.items()}
    prompts: dict[str, str] = {}
    for item in _as_list(raw):
        if not isinstance(item, dict) or "name" not in item or "path" not in item:
            raise ExperimentError("prompts list items need name and path")
        prompts[str(item["name"])] = str(item["path"])
    return prompts


def _treatments(spec: dict[str, Any], prompts: dict[str, str]) -> list[dict[str, Any]]:
    treatments = spec.get("treatments")
    if treatments:
        parsed: list[dict[str, Any]] = []
        for item in treatments:
            if not isinstance(item, dict) or "name" not in item:
                raise ExperimentError("each treatment needs a name")
            prompt_name = str(item.get("prompt") or item["name"])
            if prompt_name not in prompts:
                raise ExperimentError(f"treatment {item['name']!r} prompt {prompt_name!r} is not in prompts")
            skills = [str(s) for s in _as_list(item.get("skills"))]
            parsed.append(
                {
                    "name": str(item["name"]),
                    "prompt": prompt_name,
                    "prompt_path": prompts[prompt_name],
                    "skills": skills,
                    "skill_bundle": _bundle_name(skills, item.get("skill_bundle")),
                }
            )
        return parsed

    bundles_raw = spec.get("skill_bundles")
    if not prompts:
        raise ExperimentError("Need treatments or prompts")
    bundles: list[tuple[str, list[str]]]
    if not bundles_raw:
        bundles = [("none", [])]
    elif isinstance(bundles_raw, dict):
        bundles = [(str(name), [str(s) for s in _as_list(skills)]) for name, skills in bundles_raw.items()]
    else:
        bundles = []
        for item in bundles_raw:
            if isinstance(item, dict):
                name = str(item.get("name") or _bundle_name(_as_list(item.get("skills")), None))
                bundles.append((name, [str(s) for s in _as_list(item.get("skills"))]))
            else:
                raise ExperimentError("skill_bundles list items must be mappings")
    parsed = []
    for prompt_name, prompt_path in prompts.items():
        for bundle_name, skills in bundles:
            parsed.append(
                {
                    "name": f"{prompt_name}+{bundle_name}",
                    "prompt": prompt_name,
                    "prompt_path": prompt_path,
                    "skills": skills,
                    "skill_bundle": bundle_name,
                }
            )
    return parsed


def _count_local_tasks(root: Path, rel: str) -> int:
    path = Path(rel)
    if not path.is_absolute():
        path = root / path
    if not path.exists():
        raise ExperimentError(f"dataset path not found: {rel}")
    return sum(1 for child in path.iterdir() if child.is_dir() and (child / "task.toml").exists())


def _datasets(spec: dict[str, Any], root: Path) -> list[DatasetRef]:
    parsed: list[DatasetRef] = []
    for item in _as_list(spec.get("datasets")):
        if not isinstance(item, dict):
            raise ExperimentError("each dataset must be a mapping")
        name = str(item["name"]) if item.get("name") else None
        path = str(item["path"]) if item.get("path") else None
        if bool(name) == bool(path):
            raise ExperimentError("each dataset needs exactly one of name or path")
        n_tasks = item.get("n_tasks")
        n_tasks_int = None if n_tasks is None else int(n_tasks)
        task_names = tuple(str(part) for part in _as_list(item.get("task_names")))
        exclude = tuple(str(part) for part in _as_list(item.get("exclude_task_names")))
        if path:
            local = _count_local_tasks(root, path)
            if task_names:
                local = min(local, len(task_names))
            resolved = local if n_tasks_int is None else min(local, n_tasks_int)
        else:
            if n_tasks_int is None and not task_names:
                raise ExperimentError(
                    f"remote dataset {name!r} needs n_tasks or task_names "
                    "so dry-run can bound trial count without a registry fetch"
                )
            resolved = len(task_names) if n_tasks_int is None else n_tasks_int
            if task_names:
                resolved = min(resolved, len(task_names))
        parsed.append(
            DatasetRef(
                name=name,
                path=path,
                version=str(item["version"]) if item.get("version") else None,
                ref=str(item["ref"]) if item.get("ref") else None,
                n_tasks=n_tasks_int,
                task_names=task_names,
                exclude_task_names=exclude,
                resolved_n_tasks=resolved,
            )
        )
    return parsed


def _agents(spec: dict[str, Any]) -> list[dict[str, Any]]:
    agents = _require(spec, "agents")
    parsed: list[dict[str, Any]] = []
    for item in _as_list(agents):
        if isinstance(item, str):
            item = {"name": item}
        if not isinstance(item, dict) or "name" not in item:
            raise ExperimentError("each agent needs a name")
        name = str(item["name"])
        import_path = item.get("import_path")
        parsed.append(
            {
                "name": name,
                "import_path": str(import_path) if import_path else None,
                "kind": _agent_kind(name, import_path),
                "kwargs": dict(item.get("kwargs") or {}),
            }
        )
    return parsed


def _make_cell(
    agent: dict[str, Any],
    model: str,
    treatment: dict[str, Any],
    extra_kwargs: dict[str, Any] | None = None,
) -> Cell:
    kwargs = dict(agent.get("kwargs") or {})
    if extra_kwargs:
        kwargs.update(extra_kwargs)
    return Cell(
        agent=agent["name"],
        import_path=agent["import_path"],
        model=model,
        treatment=treatment["name"],
        prompt_name=treatment["prompt"],
        prompt_path=treatment["prompt_path"],
        skill_bundle=treatment["skill_bundle"],
        skills=tuple(treatment["skills"]),
        kind=agent["kind"],
        agent_kwargs=kwargs,
    )


def _explicit_cells(
    spec: dict[str, Any],
    agents: list[dict[str, Any]],
    models: list[str],
    treatments: list[dict[str, Any]],
) -> list[Cell] | None:
    raw = spec.get("cells")
    if not raw:
        return None
    agent_by_name = {item["name"]: item for item in agents}
    treatment_by_name = {item["name"]: item for item in treatments}
    cells: list[Cell] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ExperimentError("cells must be mappings")
        agent_name = str(item.get("agent") or "")
        treatment_name = str(item.get("treatment") or "")
        if agent_name not in agent_by_name:
            raise ExperimentError(f"cell agent {agent_name!r} is not in agents")
        if treatment_name not in treatment_by_name:
            raise ExperimentError(f"cell treatment {treatment_name!r} is not in treatments")
        agent = agent_by_name[agent_name]
        treatment = treatment_by_name[treatment_name]
        model = str(item.get("model") or (models[0] if len(models) == 1 else ""))
        if not model:
            raise ExperimentError("explicit cell needs model when more than one model is listed")
        extra = item.get("kwargs") if isinstance(item.get("kwargs"), dict) else None
        cells.append(_make_cell(agent, model, treatment, extra))
    return cells


def _cartesian(agents: list[dict[str, Any]], models: list[str], treatments: list[dict[str, Any]]) -> list[Cell]:
    cells: list[Cell] = []
    for agent in agents:
        for model in models:
            for treatment in treatments:
                cells.append(_make_cell(agent, model, treatment))
    return cells


def _skill_hashes(root: Path, cells: list[Cell]) -> list[dict[str, str]]:
    seen: list[dict[str, str]] = []
    fingerprints: set[tuple[str, str]] = set()
    for cell in cells:
        for index, skill in enumerate(cell.skills):
            path = Path(skill)
            if not path.is_absolute():
                path = root / path
            digest = sha256_tree(path)
            key = (str(skill), digest)
            if key in fingerprints:
                continue
            fingerprints.add(key)
            seen.append(
                {
                    "order": str(index),
                    "name": path.name,
                    "path": str(skill),
                    "digest": digest,
                }
            )
    return seen


def _pair_id(left: str, right: str) -> str:
    return f"{left}__{right}"


def pairing_for(cell: Cell, pairs: list[tuple[str, str]]) -> tuple[str, str]:
    matched = [_pair_id(left, right) for left, right in pairs if cell.treatment in (left, right)]
    if not matched:
        return "", ""
    pair_id = matched[0] if len(matched) == 1 else ",".join(matched)
    pairing_key = sha256_text(
        canonical_dumps({"agent": cell.agent, "model": cell.model, "pair_id": pair_id})
    )
    return pair_id, pairing_key


def _assert_pairs_complete(cells: list[Cell], pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    remaining = {cell.treatment for cell in cells}
    live: list[tuple[str, str]] = []
    groups: dict[tuple[str, str], set[str]] = {}
    for cell in cells:
        groups.setdefault((cell.agent, cell.model), set()).add(cell.treatment)
    for left, right in pairs:
        has_left = left in remaining
        has_right = right in remaining
        if has_left ^ has_right:
            raise ExperimentError(
                f"pair {left} vs {right} is incomplete after include/exclude/sample"
            )
        if not (has_left and has_right):
            continue
        for (agent, model), treatments in groups.items():
            if left in treatments or right in treatments:
                if not (left in treatments and right in treatments):
                    raise ExperimentError(
                        f"pair {left} vs {right} is incomplete for {agent} / {model} "
                        "after include/exclude/sample"
                    )
        live.append((left, right))
    return live


def _sample_cells(
    cells: list[Cell],
    sample: Any,
    seed: int,
    pairs: list[tuple[str, str]],
) -> list[Cell]:
    if sample is None:
        return cells
    by: str | None
    if isinstance(sample, int):
        n = sample
        by = "pairing" if pairs else None
    elif isinstance(sample, dict):
        n = int(sample.get("n") if sample.get("n") is not None else 0)
        by = sample.get("by")
        if by is not None:
            by = str(by)
    else:
        raise ExperimentError("sample must be an int or {n, by}")
    if n < 0:
        raise ExperimentError("sample must be >= 0")
    rng = random.Random(seed)
    if by in (None, "cell"):
        if n >= len(cells):
            return cells
        return rng.sample(cells, n)
    if by == "pairing":
        groups: dict[tuple[str, str], list[Cell]] = {}
        order: list[tuple[str, str]] = []
        for cell in cells:
            key = (cell.agent, cell.model)
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(cell)
        if n >= len(order):
            return cells
        chosen = rng.sample(order, n)
        return [cell for key in chosen for cell in groups[key]]
    field_of = {
        "agent": lambda cell: cell.agent,
        "model": lambda cell: cell.model,
        "treatment": lambda cell: cell.treatment,
        "skill_bundle": lambda cell: cell.skill_bundle,
    }
    if by not in field_of:
        raise ExperimentError(f"unknown sample.by {by!r}")
    grouped: dict[str, list[Cell]] = {}
    for cell in cells:
        grouped.setdefault(field_of[by](cell), []).append(cell)
    sampled: list[Cell] = []
    for key in sorted(grouped):
        bucket = grouped[key]
        if n >= len(bucket):
            sampled.extend(bucket)
        else:
            sampled.extend(rng.sample(bucket, n))
    return sampled


def expand(spec: dict[str, Any], root: Path) -> Plan:
    version = spec.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ExperimentError(f"Unsupported schema_version {version!r}; expected {SCHEMA_VERSION}")
    track = str(_require(spec, "track"))
    if track not in {"A", "B"}:
        raise ExperimentError("track must be A (fixed harness) or B (native agents)")
    name = str(_require(spec, "name"))
    seed = int(spec.get("seed") or 42)
    repeat = int(spec.get("repeat") or 1)
    if repeat < 1:
        raise ExperimentError("repeat must be >= 1")
    max_trials = int(spec.get("max_trials") or 40)
    if max_trials < 1:
        raise ExperimentError("max_trials must be >= 1")
    models = [str(item) for item in _as_list(_require(spec, "models"))]
    if not models:
        raise ExperimentError("models must not be empty")
    tasks = [str(item) for item in _as_list(spec.get("tasks"))]
    datasets = _datasets(spec, root)
    if not tasks and not datasets:
        raise ExperimentError("Need tasks or datasets")
    prompts = _prompts(spec)
    treatments = _treatments(spec, prompts)
    agents = _agents(spec)
    pairs_raw = spec.get("pairs") or []
    pairs: list[tuple[str, str]] = []
    treatment_names = {item["name"] for item in treatments}
    for pair in pairs_raw:
        items = [str(part) for part in _as_list(pair)]
        if len(items) != 2:
            raise ExperimentError("each pair must have exactly two treatment names")
        if items[0] not in treatment_names or items[1] not in treatment_names:
            raise ExperimentError(f"pair {items} references unknown treatments")
        pairs.append((items[0], items[1]))

    explicit = spec.get("cells")
    cells = _explicit_cells(spec, agents, models, treatments)
    if cells is None:
        cells = _cartesian(agents, models, treatments)

    include = [item for item in _as_list(spec.get("include")) if item]
    exclude = [item for item in _as_list(spec.get("exclude")) if item]
    if include:
        cells = [cell for cell in cells if any(_match(cell, filt) for filt in include)]
    if exclude:
        cells = [cell for cell in cells if not any(_match(cell, filt) for filt in exclude)]

    sample = spec.get("sample")
    cells = _sample_cells(cells, sample, seed, pairs)
    pairs = _assert_pairs_complete(cells, pairs)

    environment = dict(spec.get("environment") or {"type": "docker", "delete": True})
    budget = spec.get("budget_usd")
    return Plan(
        name=name,
        track=track,
        seed=seed,
        repeat=repeat,
        max_trials=max_trials,
        n_concurrent=int(spec.get("n_concurrent") or 2),
        max_retries=int(spec.get("max_retries") or 0),
        usd_per_trial=float(spec.get("usd_per_trial") or 0),
        budget_usd=None if budget is None else float(budget),
        environment=environment,
        tasks=tasks,
        cells=cells,
        pairs=pairs,
        selection={
            "include": include,
            "exclude": exclude,
            "sample": sample,
            "explicit_cells": bool(explicit),
        },
        skill_hashes=_skill_hashes(root, cells),
        datasets=datasets,
        retry=harbor_retry(int(spec.get("max_retries") or 0)),
        assemble_sealed=bool(spec.get("assemble_sealed")),
        assembled_path=str(spec.get("assembled_path") or "jobs/.assembled/holdout"),
    )


def guard(plan: Plan) -> None:
    if plan.n_trials > plan.max_trials:
        raise ExperimentError(
            f"Refusing to run {plan.n_trials} trials (cells={plan.n_cells} "
            f"× tasks={plan.n_task_units} × repeat={plan.repeat}); "
            f"max_trials={plan.max_trials}. Narrow treatments, add exclude, "
            f"set sample, or raise max_trials."
        )
    if plan.budget_usd is not None and plan.usd_per_trial <= 0:
        raise ExperimentError(
            "budget_usd is set but usd_per_trial is unknown; "
            "set usd_per_trial or omit budget_usd"
        )
    estimated = plan.estimated_usd
    if plan.budget_usd is not None and estimated is not None and estimated > plan.budget_usd:
        raise ExperimentError(
            f"Refusing estimated cost ${estimated:.2f} over budget_usd=${plan.budget_usd:.2f}"
        )


def format_dry_run(plan: Plan) -> str:
    estimated = plan.estimated_usd
    cost = f"${estimated:.2f}" if estimated is not None else f"unknown (usd_per_trial={plan.usd_per_trial})"
    lines = [
        f"track: {plan.track}",
        f"experiment: {plan.name}",
        f"seed: {plan.seed}",
        f"cells: {plan.n_cells}",
        f"tasks: {plan.n_task_units}",
        f"repeat: {plan.repeat}",
        f"trials: {plan.n_trials}",
        f"max_trials: {plan.max_trials}",
        f"estimated_usd: {cost}",
        f"pairs: {', '.join(f'{a} vs {b}' for a, b in plan.pairs) or '(none)'}",
        f"retry.max_retries: {plan.retry.get('max_retries')}",
        f"assemble_sealed: {plan.assemble_sealed}",
        "datasets:",
    ]
    if plan.datasets:
        for item in plan.datasets:
            ref = item.name or item.path
            extra = f" n={item.resolved_n_tasks}"
            if item.version:
                extra += f" version={item.version}"
            if item.ref:
                extra += f" ref={item.ref}"
            lines.append(f"  - {ref}{extra}")
    else:
        lines.append("  - (none)")
    lines.append("skill_hashes:")
    if plan.skill_hashes:
        for item in plan.skill_hashes:
            lines.append(f"  - {item['order']} {item['name']} {item['digest']}")
    else:
        lines.append("  - (none)")
    lines.append("cells:")
    for cell in plan.cells:
        skills = "+".join(Path(s).name for s in cell.skills) or "none"
        pair_id, _ = pairing_for(cell, plan.pairs)
        kwargs = ",".join(f"{k}={cell.agent_kwargs[k]!r}" for k in sorted(cell.agent_kwargs)) or "none"
        lines.append(
            f"  - {cell.kind}:{cell.agent} | {cell.model} | {cell.treatment} | "
            f"prompt={cell.prompt_name} | skills={skills} | pair={pair_id or 'none'} | kwargs={kwargs}"
        )
    return "\n".join(lines)


def resolved_manifest(plan: Plan) -> dict[str, Any]:
    cells = []
    for cell in plan.cells:
        pair_id, pairing_key = pairing_for(cell, plan.pairs)
        payload = asdict(cell)
        payload["skills"] = list(cell.skills)
        payload["pair_id"] = pair_id
        payload["pairing_key"] = pairing_key
        cells.append(payload)
    return {
        "schema_version": SCHEMA_VERSION,
        "name": plan.name,
        "track": plan.track,
        "seed": plan.seed,
        "repeat": plan.repeat,
        "max_trials": plan.max_trials,
        "n_concurrent": plan.n_concurrent,
        "max_retries": plan.max_retries,
        "usd_per_trial": plan.usd_per_trial,
        "budget_usd": plan.budget_usd,
        "environment": plan.environment,
        "tasks": list(plan.tasks),
        "datasets": [item.to_harbor() | {"resolved_n_tasks": item.resolved_n_tasks} for item in plan.datasets],
        "retry": plan.retry,
        "assemble_sealed": plan.assemble_sealed,
        "assembled_path": plan.assembled_path,
        "n_task_units": plan.n_task_units,
        "pairs": [{"id": _pair_id(left, right), "left": left, "right": right} for left, right in plan.pairs],
        "selection": plan.selection,
        "skill_hashes": plan.skill_hashes,
        "cells": cells,
        "n_cells": plan.n_cells,
        "n_trials": plan.n_trials,
    }


def compile_harbor_job(plan: Plan, job_name: str) -> dict[str, Any]:
    agents: list[dict[str, Any]] = []
    for cell in plan.cells:
        pair_id, pairing_key = pairing_for(cell, plan.pairs)
        kwargs: dict[str, Any] = {
            key: value
            for key, value in cell.agent_kwargs.items()
            if key not in ASB_RESERVED_KWARGS
        }
        kwargs.update(
            {
                "prompt_name": cell.prompt_name,
                "asb_treatment": cell.treatment,
                "asb_track": plan.track,
                "asb_skill_bundle": cell.skill_bundle,
                "asb_seed": plan.seed,
                "asb_pair_id": pair_id,
                "asb_pairing_key": pairing_key,
            }
        )
        if cell.prompt_path:
            kwargs["prompt_path"] = cell.prompt_path
        entry: dict[str, Any] = {
            "name": cell.agent,
            "model_name": cell.model,
            "kwargs": kwargs,
        }
        if cell.import_path:
            entry["import_path"] = cell.import_path
        if cell.skills:
            entry["skills"] = list(cell.skills)
        agents.append(entry)
    return {
        "job_name": job_name,
        "jobs_dir": "jobs",
        "n_attempts": plan.repeat,
        "n_concurrent_trials": plan.n_concurrent,
        "quiet": False,
        "timeout_multiplier": 1.0,
        "retry": plan.retry,
        "environment": plan.environment,
        "agents": agents,
        "tasks": [{"path": path} for path in plan.tasks],
        "datasets": [_harbor_dataset(item, plan) for item in plan.datasets],
    }


def _harbor_dataset(item: DatasetRef, plan: Plan) -> dict[str, Any]:
    payload = item.to_harbor()
    if plan.assemble_sealed and item.path:
        payload["path"] = plan.assembled_path
    return payload


def dump_harbor_job(job: dict[str, Any]) -> str:
    return yaml.safe_dump(job, sort_keys=False)


def passthrough_trial_count(job: dict[str, Any]) -> int:
    n_agents = len(job.get("agents") or [])
    n_tasks = len(job.get("tasks") or [])
    repeat = int(job.get("n_attempts") or 1)
    return n_agents * n_tasks * repeat
