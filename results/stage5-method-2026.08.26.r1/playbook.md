# Model programming playbook (Track A)

Track A fixed-harness study using deterministic capability profiles. Conclusions apply only to this harness revision unless re-confirmed on Track B native agents. Numbers are per-slice with CIs — not a leaderboard.

- Config revision: `stage5-method-2026.08.26.r1`
- Dataset holdout revision: `2026.08.25.r3`
- Applicability: **fixed Harbor harness (Track A)** with deterministic profiles.
- Not applicable to: hosted LLM product rankings; Track B native agents until re-run.

## How to read evidence

- Prefer paired task-level bootstrap CIs and McNemar over totals.
- Every claim below is bound to a task slice, treatment, and this revision.
- Infra errors are excluded from success rates.

## Per-model cards

### alpha
- Recommended agent: `naive-solver`
- Recommended prompt/skill bundle: `bundle`
- Risky combos: (none flagged <0.35)
- Applicability: Track A fixed harness only

| treatment | success_rate | n_scored | cost_mean |
|---|---:|---:|---:|
| baseline | 0.75 | 8 | 0.002 |
| bundle | 0.875 | 8 | 0.0025 |
| plan | 0.875 | 8 | 0.0025 |
| skill | 0.75 | 8 | 0.002 |

### beta
- Recommended agent: `plan-solver`
- Recommended prompt/skill bundle: `bundle`
- Risky combos: skill-solver/baseline
- Applicability: Track A fixed harness only

| treatment | success_rate | n_scored | cost_mean |
|---|---:|---:|---:|
| baseline | 0.0 | 8 | 0.008 |
| bundle | 0.9318181818181818 | 44 | 0.01215909090909091 |
| plan | 0.75 | 44 | 0.010272727272727274 |
| skill | 0.75 | 8 | 0.0096 |

### gamma
- Recommended agent: `plan-solver`
- Recommended prompt/skill bundle: `bundle`
- Risky combos: (none flagged <0.35)
- Applicability: Track A fixed harness only

| treatment | success_rate | n_scored | cost_mean |
|---|---:|---:|---:|
| baseline | 0.75 | 8 | 0.022000000000000002 |
| bundle | 0.7727272727272727 | 44 | 0.030965909090909093 |
| plan | 0.7727272727272727 | 44 | 0.026136363636363638 |
| skill | 0.75 | 8 | 0.026400000000000003 |

## Research questions

### prompt_gain_across_agents
Is prompt (plan) gain stable across agents?
- Bound to: `{"revision": "stage5-method-2026.08.26.r1", "treatments": ["baseline", "plan"]}`
- See `research_questions.json` for paired CIs / slices.

### skill_gain_dependence
Does skill/bundle gain depend on model, agent, and task slice?
- Bound to: `{"revision": "stage5-method-2026.08.26.r1", "track": "A"}`
- See `research_questions.json` for paired CIs / slices.

### complement_conflict
Do prompt+skill bundles complement or conflict?
- Bound to: `{"revision": "stage5-method-2026.08.26.r1"}`
- See `research_questions.json` for paired CIs / slices.

### cost_latency_worth
Is the success gain worth cost/latency?
- Bound to: `{"cost_model": "profile-fixture", "revision": "stage5-method-2026.08.26.r1"}`
- See `research_questions.json` for paired CIs / slices.

## Failure taxonomy

Counts (from trials; use samples_for_blind_review for human audit):

- `brittle_medium` (2): Medium task failed on brittle model.
- `incomplete_medium` (2): Medium task incomplete without planning cue.
- `no_scaffold` (7): Model needs prompt or skill scaffolding.
- `plan_without_skill` (1): Plan prompt alone insufficient for task slice.
- `security_miss` (33): Security task failed without an appropriate skill.
- `security_partial` (1): Partial skill bundle on security task.
- `skill_conflict` (7): Combined skills conflict for this model/task.
- `skill_without_plan` (1): Skill alone insufficient for task slice.
- `success` (186): 

## Incremental regression

1. Keep `configs/experiments/stage5-regression-baseline.yaml` task/seed pins.
2. Add only the new model/agent/prompt/skill under test.
3. Run `asb run --config configs/experiments/stage5-regression-baseline.yaml`.
4. Diff new slices against `regression_baseline.json`.

## Repro

```bash
uv sync --extra dev
uv run asb fetch-sealed && uv run asb assemble
uv run asb pipeline --config configs/experiments/stage5-pipeline.yaml
uv run asb study --results results/<screen-job> --results results/<confirm-job>
```

