# agent-skill-bench

Composable **Agent × Prompt × Skill** programming benchmark on [Harbor](https://github.com/harbor-framework/harbor).

Stage 4: concurrent isolated workers, durable artifacts, resume-without-rebill, and task-level paired stats. **Do not treat scores as a ranking or a generalization about models, agents, prompts, or skills.** There is no composite total.

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
uv run asb run --resume jobs/<job-dir>            # Harbor job resume (completed trials are not re-run or re-billed)
uv run asb cancel jobs/<job-dir>                  # SIGINT if still running; writes asb_cancelled.json
uv run asb pipeline --config configs/experiments/stage4-pipeline.yaml --dry-run
uv run asb pipeline --config configs/experiments/stage4-pipeline.yaml   # runs screen, then confirm
uv run asb report --job jobs/<job-dir>            # warehouse + McNemar/bootstrap + dashboard
uv run asb warehouse
uv run asb prune --days 30                        # list expired jobs; add --delete to remove
uv run asb fetch-sealed                           # authorized clone of private holdout + digest check
uv run asb assemble                               # public + sealed → cache/asb/assembled/holdout
uv run asb validate                               # fail-closed pinned-container gates (needs sealed corpus)
uv run asb run --config configs/experiments/stage3-holdout.yaml --dry-run
uv run asb dataset                                # revision, image digest, scorer version
uv run asb summarize
uv run --extra dev pytest
```

`--dry-run` prints the matrix and **refuses** to proceed when `cells × tasks × repeat` exceeds `max_trials`, when `budget_usd` is set without `usd_per_trial`, or when estimated cost exceeds `budget_usd`.

## Experiment YAML

See `configs/experiments/smoke-2x2.yaml`. Treatments are the factorial unit (not an implicit prompt × skill cartesian). Add `include` / `exclude`, `cells` for an explicit matrix, `sample` (`2` or `{n: 1, by: treatment|agent|model|pairing}`), and `pairs` for same-agent/model paired treatments. `agents[].kwargs` pass through to Harbor.

Harbor cartesian-products `agents[] × tasks[] × n_attempts`. Repeat is `repeat` → Harbor `n_attempts`. Retry is Harbor `max_retries` with a **pre-registered infra-only include list** (agent/model/test outcomes are never retried). Interrupted jobs resume with `asb run --resume`. Completed trials keep their `result.json`; `asb_ledger.json` refuses to bill or score the same `trial_id` twice. A new run of the same spec gets a new timestamped job directory — patches live under that trial dir and are never looked up by config fingerprint (`policy.cache_scope` may be `image` or `none`, never `patch`). Each job writes `asb_experiment.json` (resolved schema, seed, cells, pairs, skill tree hashes, dataset refs). `environment.type` selects an isolated worker Harbor already supports (`docker`, `daytona`, `e2b`, `modal`, …).

## Stage 4 analysis

- `asb report` writes `index.json` (trial_id → manifest, result, patch digest, tests, trajectory), `stats.json` / `stats.md` (slice tables, pass^k, paired bootstrap CI, McNemar, task-clustered interaction bootstrap), and `dashboard.html`.
- Paired tests are task × agent × model. Infra errors are dropped, not counted as model failure.
- Interaction uses a hierarchical (task-clustered) bootstrap, not a single score and not a mixed-model fitter.
- `asb pipeline` runs the screen job, ranks treatments by success rate as a **filter**, then runs a confirm job with higher `repeat`. `--dry-run` only prints the plan. The rank is not published as a total.
- Paired stats average repeats per (task, agent, model) arm, then cluster-bootstrap **tasks** (every agent/model cell of a drawn task is kept). McNemar uses the same task unit. Allowlisted secret **values** stay in the process environment; generated Harbor YAML and `asb_secrets.json` keep names / `[redacted]` only, written before Harbor starts so an interrupted first run can still resume. `asb run --resume` records the Harbor PID so `asb cancel` can SIGINT a resumed job.

Policy keys (`policy.cache_scope`, `retention_days`, `secret_allowlist`, `durable_artifacts`) stay out of Harbor's job YAML. Secret-looking keys are redacted in manifests; allowlisted names are recorded as present, never as values.

## Stage 3 task set

- Public subset pin: `datasets/public-subset.toml` — `harbor/hello-world` and `terminal-bench/terminal-bench-2` with dataset `ref` (content hash) and explicit task names + task digests.
- Private holdout **revision `2026.08.25.r3`**. Public tree: agent-visible files + `datasets/private-manifest.toml`. Hidden tests / gold / alt / negative live in private `AkaraChen/agent-skill-bench-holdout` at tag `v2026.08.25.r3`. Fetch: `asb fetch-sealed` (cache only under `cache/asb/`, atomic replace after verify).
- Revisions `2026.08.25` and `2026.08.25.r2` are **compromised** (`datasets/compromised.toml`). Each task pins a `compromised_gold_digest`; fetch and validate check the inventory, and the `compromised-gold` gate always runs (missing or drift fails).
- `assemble_sealed` jobs write into `cache/asb/assembled/holdout`. Absolute/`..` paths are rejected.
- `asb validate` never generates. Scorer: hidden-test failures are **model** failure; only verifier exceptions are `TEST`.


## What each trial stores

Harbor writes `config.json`, `lock.json`, `result.json`, agent logs, verifier logs, and workspace artifacts. `asb summarize` adds `asb_manifest.json` with the experiment seed, pairing key, agent kwargs, skill hashes, track, an `agent/model/test/infra` failure class, token/cost/duration, tool-call counts, and URIs for the manifest, tests, trajectory, and patch digest. `asb warehouse` / `asb report` index those URIs so a table row is always traceable to the raw files.
