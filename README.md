# agent-skill-bench

Composable **Agent × Prompt × Skill** programming benchmark on [Harbor](https://github.com/harbor-framework/harbor).

This repository is the Stage 1 smoke loop for KIT-908 / KIT-903: prove the experiment machinery works. **Do not treat smoke scores as a ranking or a generalization about models, agents, prompts, or skills.**

## Frozen versions

See `versions.lock.toml`.

- Harbor `0.22.0`
- Base image `python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7`
- Model snapshot `deterministic/smoke-solver@2026-08-24` (deterministic Harbor agents, no hosted LLM)

Stage 1 wires two custom Harbor agents so the 20-trial loop can finish without API keys. Native Claude Code / Codex adapters belong in later stages.

## Matrix

| Axis | Values |
|---|---|
| Agents | `naive-solver`, `skill-solver` |
| Treatments | `baseline` prompt + no skill, `candidate` prompt + `test-first` skill |
| Tasks | 5 tiny file-writing tasks |
| Attempts | 1 |

`2 agents × 2 treatments × 5 tasks × 1 attempt = 20 trials`.

Each trial runs in a fresh Docker container (`delete: true`). Hidden tests and gold solutions live under `tests/` and `solution/` and are copied in only for verification. Agents probe `/tests` and `/solution` and must not see them during the solve phase.

## Commands

```bash
uv sync --extra dev
uv run asb run          # start the 20-trial Harbor job
uv run asb summarize    # write results table + fingerprints
uv run pytest           # host-side checks
```

## What each trial stores

Harbor writes `config.json`, `lock.json`, `results.json`, agent logs, verifier logs, and workspace artifacts. `asb summarize` adds `asb_manifest.json` with a config fingerprint and an `agent/model/test/infra` failure class.
