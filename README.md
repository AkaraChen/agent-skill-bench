# agent-skill-bench

Composable **Agent × Prompt × Skill** programming benchmark on [Harbor](https://github.com/harbor-framework/harbor).

Stage 3: isolated private holdout + validity gates + a scorer that keeps infra errors out of model failure. **Do not treat scores as a ranking or a generalization about models, agents, prompts, or skills.**

## Frozen versions

See `versions.lock.toml`.

- Harbor `0.22.0`
- Base image `python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7`
- Track A smoke model `deterministic/smoke-solver@2026-08-24` (no hosted LLM)

## Tracks

- **A** — fixed harness (custom Harbor agents such as the deterministic solvers).
- **B** — native agents. Prefer Harbor built-ins (`codex`, `claude-code`, `gemini-cli`, …). If Harbor has no runner, use Harbor's ACP shorthand `acp:<registry-id>` — do not wrap acpx.

New Agent / Prompt / Skill = config (and maybe one import_path). The expander does not change.

## Commands

```bash
uv sync --extra dev
uv run asb run --dry-run                          # cells, trial count, budget gate
uv run asb run                                    # A-track 2×2 smoke, 20 trials
uv run asb run --config configs/experiments/track-b.example.yaml --dry-run
uv run asb run --config configs/experiments/stage3-holdout.yaml --dry-run
uv run asb run --config configs/experiments/stage3-public-subset.yaml --dry-run
uv run asb run --resume jobs/<job-dir>            # Harbor job resume
uv run asb generate-holdout                       # writes sealed corpus; not used by validate
uv run asb validate                               # fail-closed pinned-container gates (needs ASB_SEALED_DIR)
uv run asb dataset                                # revision, image digest, scorer version
uv run asb summarize
uv run --extra dev pytest
```

`--dry-run` prints the matrix and **refuses** to proceed when `cells × tasks × repeat` exceeds `max_trials`, when `budget_usd` is set without `usd_per_trial`, or when estimated cost exceeds `budget_usd`.

## Experiment YAML

See `configs/experiments/smoke-2x2.yaml`. Treatments are the factorial unit (not an implicit prompt × skill cartesian). Add `include` / `exclude`, `cells` for an explicit matrix, `sample` (`2` or `{n: 1, by: treatment|agent|model|pairing}`), and `pairs` for same-agent/model paired treatments. `agents[].kwargs` pass through to Harbor.

Harbor cartesian-products `agents[] × tasks[] × n_attempts`. Repeat is `repeat` → Harbor `n_attempts`. Retry is Harbor `max_retries` with a **pre-registered infra-only include list** (agent/model/test outcomes are never retried). Interrupted jobs resume with `asb run --resume`. Each job writes `asb_experiment.json` (resolved schema, seed, cells, pairs, skill tree hashes, dataset refs).

## Stage 3 task set

- Public subset pin: `datasets/public-subset.toml` — `harbor/hello-world` and `terminal-bench/terminal-bench-2` with dataset `ref` (content hash) and explicit task names + task digests.
- Private temporal holdout: 24 original tasks authored 2026-08-25. The public tree has agent-visible files (`tasks/private/*/instruction.md`, `environment/`, `task.toml`) plus `datasets/private-manifest.toml` (provenance + irreversible digests). Hidden tests, gold, alternative, and negative live **outside git** at `$ASB_SEALED_DIR` (default `sealed/holdout/`, gitignored).
- `asb generate-holdout` writes the sealed corpus from a sealed catalog. `asb validate` never generates; it fail-closes if the sealed dir is missing or digests drift, then runs gold/alt/negative in the pinned image (`--network=none`, 1 CPU, 512MB).
- Scorer: hidden-test failures count as **model** failure; only verifier exceptions are `TEST`; infra is not model failure. LLM judge is auxiliary only.


## What each trial stores

Harbor writes `config.json`, `lock.json`, `results.json`, agent logs, verifier logs, and workspace artifacts. `asb summarize` adds `asb_manifest.json` with the experiment seed, pairing key, agent kwargs, skill hashes, track, and an `agent/model/test/infra` failure class.
