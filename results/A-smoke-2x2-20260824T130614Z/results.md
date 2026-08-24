# Experiment results

This table is a loop / matrix smoke of the experiment machinery. It is not a ranking, not a capability claim, and not a generalization about models, agents, prompts, or skills.

- Job: `A-smoke-2x2-20260824T130614Z`
- Trials: 20
- Unique trial IDs: True
- Unique fingerprints: True
- Summarized at: 2026-08-24T13:11:35.878635+00:00

| track | task | agent | treatment | reward | class | skill loaded | duration_s | fingerprint |
|---|---|---|---|---|---|---|---|---|
| A | asb/csv-sum | naive-solver | baseline | 1.0 | ok | False | 17.7 | `sha256:cf3c6fc0f` |
| A | asb/csv-sum | naive-solver | candidate | 1.0 | ok | False | 17.7 | `sha256:26f9be07a` |
| A | asb/csv-sum | skill-solver | baseline | 1.0 | ok | False | 17.5 | `sha256:fc36e2a28` |
| A | asb/csv-sum | skill-solver | candidate | 1.0 | ok | True | 17.8 | `sha256:4820efd4f` |
| A | asb/fizzbuzz | naive-solver | baseline | 1.0 | ok | False | 18.0 | `sha256:3efdf92c6` |
| A | asb/fizzbuzz | naive-solver | candidate | 1.0 | ok | False | 18.0 | `sha256:e7f49df0c` |
| A | asb/fizzbuzz | skill-solver | baseline | 1.0 | ok | False | 17.8 | `sha256:abd3922e7` |
| A | asb/fizzbuzz | skill-solver | candidate | 1.0 | ok | True | 18.0 | `sha256:17f1e6d79` |
| A | asb/json-merge | naive-solver | baseline | 1.0 | ok | False | 17.5 | `sha256:a79c1c92f` |
| A | asb/json-merge | naive-solver | candidate | 1.0 | ok | False | 18.0 | `sha256:437441adc` |
| A | asb/json-merge | skill-solver | baseline | 1.0 | ok | False | 17.3 | `sha256:3a587dc1c` |
| A | asb/json-merge | skill-solver | candidate | 1.0 | ok | True | 17.7 | `sha256:b4d95f4bd` |
| A | asb/reverse-string | naive-solver | baseline | 1.0 | ok | False | 17.9 | `sha256:c3674076b` |
| A | asb/reverse-string | naive-solver | candidate | 1.0 | ok | False | 19.1 | `sha256:ee2768bcc` |
| A | asb/reverse-string | skill-solver | baseline | 1.0 | ok | False | 17.9 | `sha256:d7a9d2c25` |
| A | asb/reverse-string | skill-solver | candidate | 1.0 | ok | True | 17.9 | `sha256:8a0a917f4` |
| A | asb/slugify | naive-solver | baseline | 1.0 | ok | False | 17.4 | `sha256:1d486f4f9` |
| A | asb/slugify | naive-solver | candidate | 1.0 | ok | False | 17.5 | `sha256:f85490e4a` |
| A | asb/slugify | skill-solver | baseline | 1.0 | ok | False | 17.2 | `sha256:6e8d82ff1` |
| A | asb/slugify | skill-solver | candidate | 1.0 | ok | True | 17.7 | `sha256:eb3d2206f` |

## Counts by failure class

- `ok`: 20
- `agent`: 0
- `model`: 0
- `test`: 0
- `infra`: 0
