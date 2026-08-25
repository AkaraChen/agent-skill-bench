# Stage 7: Codex × eric-way freeze (stage7-ericway-2026.08.26.r1)

Design and dry-run only. Do not start billed trials until Akara confirms the budget.

## Pins

- eric-way commit: `786ba75fa2de5238da80415dfad8d7e7ce5b4eab`
- agent-skill-bench base: `7587e40d4a26a8b0a7c004ab81c28f2c89f42256`
- Harbor: `0.22.0`
- Codex CLI: `0.149.1`
- Model snapshot: `openai/gpt-5.6`
- Reasoning effort: `medium`
- Web search: `disabled`
- Prompt: `prompts/stage7-codex.md`
- Network: `no-network`
- Container: `python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7`

## Screening dry-run

- Trials: **132** (repeat=1)
- Estimated USD: **$264.00** at $2.0/trial
- Hard budget (125%): **$330.00**
- Worst-case wall clock, serial stages: **18.0 h**
- Worst-case wall clock, parallel 8A–8D: **8.33 h**

| Stage | Issue | Tasks | Trials | USD | Budget | Config |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 8A | KIT-913 | 15 | 47 | $94.00 | $117.50 | `configs/experiments/stage8a-screen.yaml` |
| 8B | KIT-914 | 15 | 50 | $100.00 | $125.00 | `configs/experiments/stage8b-screen.yaml` |
| 8C | KIT-915 | 5 | 16 | $32.00 | $40.00 | `configs/experiments/stage8c-screen.yaml` |
| 8D | KIT-916 | 6 | 19 | $38.00 | $47.50 | `configs/experiments/stage8d-screen.yaml` |

## Confirm placeholder (Stage 9, not run)

- Placeholder trials: 192 (repeat=3)
- Estimated USD: $384.00
- Config: `configs/experiments/stage9-confirm.example.yaml`

## Artifact map

- Skill freeze: `skills/eric-way/`
- Catalog: `datasets/stage7/catalog.json`
- Coverage matrix: `datasets/stage7/coverage-matrix.csv`
- Task stubs: `tasks/stage7/<id>/`
- Dry-run transcripts: `results/stage7-ericway-2026.08.26.r1/`

`cells[].kwargs.asb_task` is the real task path. `tasks/stage7/_anchor` exists only so the expander counts 1 task unit. Stage 8 must expand those kwargs into per-task Harbor jobs before any billed run.

