# Stage 1 smoke results

This table is a Stage 1 smoke of the experiment loop. It is not a ranking, not a capability claim, and not a generalization about models, agents, prompts, or skills.

- Job: `smoke-2x2-20260824T120050Z`
- Trials: 20
- Unique trial IDs: True
- Unique fingerprints: True
- Summarized at: 2026-08-24T12:04:26.163946+00:00

| task | agent | treatment | reward | class | skill loaded | duration_s | fingerprint |
|---|---|---|---|---|---|---|---|
| asb/csv-sum | naive-solver | baseline | 1.0 | ok | False | 17.8 | `sha256:745199c9c` |
| asb/csv-sum | naive-solver | candidate | 1.0 | ok | False | 17.7 | `sha256:6ba4ef09d` |
| asb/csv-sum | skill-solver | baseline | 1.0 | ok | False | 17.6 | `sha256:a2077d3f7` |
| asb/csv-sum | skill-solver | candidate | 1.0 | ok | True | 17.8 | `sha256:4d4ece1dc` |
| asb/fizzbuzz | naive-solver | baseline | 1.0 | ok | False | 17.8 | `sha256:464d3286c` |
| asb/fizzbuzz | naive-solver | candidate | 1.0 | ok | False | 17.9 | `sha256:b2b970610` |
| asb/fizzbuzz | skill-solver | baseline | 1.0 | ok | False | 17.8 | `sha256:437850723` |
| asb/fizzbuzz | skill-solver | candidate | 1.0 | ok | True | 17.8 | `sha256:40ba4f4af` |
| asb/json-merge | naive-solver | baseline | 1.0 | ok | False | 17.5 | `sha256:a02f678ac` |
| asb/json-merge | naive-solver | candidate | 1.0 | ok | False | 17.7 | `sha256:2e3d93a34` |
| asb/json-merge | skill-solver | baseline | 1.0 | ok | False | 17.4 | `sha256:ac03a5aee` |
| asb/json-merge | skill-solver | candidate | 1.0 | ok | True | 17.8 | `sha256:fe5c9076d` |
| asb/reverse-string | naive-solver | baseline | 1.0 | ok | False | 17.9 | `sha256:6868f5b0d` |
| asb/reverse-string | naive-solver | candidate | 1.0 | ok | False | 19.0 | `sha256:f787a2270` |
| asb/reverse-string | skill-solver | baseline | 1.0 | ok | False | 17.8 | `sha256:afbce51a5` |
| asb/reverse-string | skill-solver | candidate | 1.0 | ok | True | 17.9 | `sha256:59a01dc75` |
| asb/slugify | naive-solver | baseline | 1.0 | ok | False | 17.4 | `sha256:03a7e63e0` |
| asb/slugify | naive-solver | candidate | 1.0 | ok | False | 17.4 | `sha256:a396c7637` |
| asb/slugify | skill-solver | baseline | 1.0 | ok | False | 17.1 | `sha256:7db762c79` |
| asb/slugify | skill-solver | candidate | 1.0 | ok | True | 17.6 | `sha256:79b7493d4` |

## Counts by failure class

- `ok`: 20
- `agent`: 0
- `model`: 0
- `test`: 0
- `infra`: 0
