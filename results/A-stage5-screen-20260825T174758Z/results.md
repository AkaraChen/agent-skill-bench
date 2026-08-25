# Experiment results

This table is a loop / matrix smoke of the experiment machinery. It is not a ranking, not a capability claim, and not a generalization about models, agents, prompts, or skills.

- Job: `A-stage5-screen-20260825T174758Z`
- Trials: 96
- Unique trial IDs: True
- Unique fingerprints: True
- Newly billed/scored: 0
- Resume replays (not re-billed): 96
- Ledger billed_usd: 1.275
- Summarized at: 2026-08-25T18:06:54.674560+00:00

| track | task | agent | treatment | pair | reward | class | skill loaded | duration_s | fingerprint |
|---|---|---|---|---|---|---|---|---|---|
| A | asb-private-holdout/clamp-range | naive-solver | baseline | baseline__plan,baseline__skill,baseline__bundle | 1.0 | ok | False | 19.1 | `sha256:ff57d8582` |
| A | asb-private-holdout/clamp-range | naive-solver | bundle | baseline__bundle,plan__bundle | 1.0 | ok | False | 18.9 | `sha256:8b9609ef8` |
| A | asb-private-holdout/clamp-range | naive-solver | plan | baseline__plan,plan__bundle | 1.0 | ok | False | 18.7 | `sha256:7ff15e131` |
| A | asb-private-holdout/clamp-range | naive-solver | skill | baseline__skill | 1.0 | ok | False | 17.9 | `sha256:380b3680b` |
| A | asb-private-holdout/clamp-range | plan-solver | baseline | baseline__plan,baseline__skill,baseline__bundle | 1.0 | ok | False | 18.7 | `sha256:8ccbd7174` |
| A | asb-private-holdout/clamp-range | plan-solver | bundle | baseline__bundle,plan__bundle | 1.0 | ok | True | 18.6 | `sha256:513e94ce0` |
| A | asb-private-holdout/clamp-range | plan-solver | plan | baseline__plan,plan__bundle | 1.0 | ok | False | 18.5 | `sha256:ea7eb7d07` |
| A | asb-private-holdout/clamp-range | plan-solver | skill | baseline__skill | 1.0 | ok | True | 17.7 | `sha256:03be7ff5b` |
| A | asb-private-holdout/clamp-range | skill-solver | baseline | baseline__plan,baseline__skill,baseline__bundle | None | test | False | 18.7 | `sha256:543f7f759` |
| A | asb-private-holdout/clamp-range | skill-solver | bundle | baseline__bundle,plan__bundle | 1.0 | ok | True | 18.8 | `sha256:d96ea0d2a` |
| A | asb-private-holdout/clamp-range | skill-solver | plan | baseline__plan,plan__bundle | 1.0 | ok | False | 18.8 | `sha256:ad758fcd6` |
| A | asb-private-holdout/clamp-range | skill-solver | skill | baseline__skill | 1.0 | ok | True | 18.0 | `sha256:1edfb8861` |
| A | asb-private-holdout/path-jail | naive-solver | baseline | baseline__plan,baseline__skill,baseline__bundle | None | test | False | 17.9 | `sha256:974fdcafc` |
| A | asb-private-holdout/path-jail | naive-solver | bundle | baseline__bundle,plan__bundle | None | test | False | 18.6 | `sha256:538bd229b` |
| A | asb-private-holdout/path-jail | naive-solver | plan | baseline__plan,plan__bundle | None | test | False | 17.9 | `sha256:d04a4e402` |
| A | asb-private-holdout/path-jail | naive-solver | skill | baseline__skill | None | test | False | 18.6 | `sha256:c1085d223` |
| A | asb-private-holdout/path-jail | plan-solver | baseline | baseline__plan,baseline__skill,baseline__bundle | None | test | False | 18.5 | `sha256:f95c29615` |
| A | asb-private-holdout/path-jail | plan-solver | bundle | baseline__bundle,plan__bundle | None | test | True | 19.3 | `sha256:9035f2f95` |
| A | asb-private-holdout/path-jail | plan-solver | plan | baseline__plan,plan__bundle | None | test | False | 18.3 | `sha256:a791da345` |
| A | asb-private-holdout/path-jail | plan-solver | skill | baseline__skill | None | test | True | 18.9 | `sha256:906e3467c` |
| A | asb-private-holdout/path-jail | skill-solver | baseline | baseline__plan,baseline__skill,baseline__bundle | None | test | False | 18.1 | `sha256:78b45153d` |
| A | asb-private-holdout/path-jail | skill-solver | bundle | baseline__bundle,plan__bundle | 1.0 | ok | True | 18.7 | `sha256:027e5efa2` |
| A | asb-private-holdout/path-jail | skill-solver | plan | baseline__plan,plan__bundle | None | test | False | 17.8 | `sha256:d8f692c57` |
| A | asb-private-holdout/path-jail | skill-solver | skill | baseline__skill | None | test | True | 18.7 | `sha256:47191c170` |
| A | asb-private-holdout/unique-lines | naive-solver | baseline | baseline__plan,baseline__skill,baseline__bundle | 1.0 | ok | False | 19.0 | `sha256:28efc980d` |
| A | asb-private-holdout/unique-lines | naive-solver | bundle | baseline__bundle,plan__bundle | 1.0 | ok | False | 17.8 | `sha256:5d4dd026b` |
| A | asb-private-holdout/unique-lines | naive-solver | plan | baseline__plan,plan__bundle | 1.0 | ok | False | 19.1 | `sha256:8dbfde7e5` |
| A | asb-private-holdout/unique-lines | naive-solver | skill | baseline__skill | 1.0 | ok | False | 17.6 | `sha256:47cf1748f` |
| A | asb-private-holdout/unique-lines | plan-solver | baseline | baseline__plan,baseline__skill,baseline__bundle | 1.0 | ok | False | 18.5 | `sha256:052f95a01` |
| A | asb-private-holdout/unique-lines | plan-solver | bundle | baseline__bundle,plan__bundle | 1.0 | ok | True | 17.9 | `sha256:8bf9932db` |
| A | asb-private-holdout/unique-lines | plan-solver | plan | baseline__plan,plan__bundle | 1.0 | ok | False | 18.5 | `sha256:67be61b1c` |
| A | asb-private-holdout/unique-lines | plan-solver | skill | baseline__skill | 1.0 | ok | True | 17.9 | `sha256:233becf27` |
| A | asb-private-holdout/unique-lines | skill-solver | baseline | baseline__plan,baseline__skill,baseline__bundle | None | test | False | 18.3 | `sha256:ab4e0d100` |
| A | asb-private-holdout/unique-lines | skill-solver | bundle | baseline__bundle,plan__bundle | 1.0 | ok | True | 17.9 | `sha256:31443fe44` |
| A | asb-private-holdout/unique-lines | skill-solver | plan | baseline__plan,plan__bundle | 1.0 | ok | False | 18.3 | `sha256:317b71741` |
| A | asb-private-holdout/unique-lines | skill-solver | skill | baseline__skill | 1.0 | ok | True | 17.9 | `sha256:731b8edd1` |
| A | asb-private-holdout/word-freq | naive-solver | baseline | baseline__plan,baseline__skill,baseline__bundle | None | test | False | 19.4 | `sha256:a2aa83b15` |
| A | asb-private-holdout/word-freq | naive-solver | bundle | baseline__bundle,plan__bundle | 1.0 | ok | False | 18.2 | `sha256:39dad2a31` |
| A | asb-private-holdout/word-freq | naive-solver | plan | baseline__plan,plan__bundle | 1.0 | ok | False | 19.2 | `sha256:3d4a33237` |
| A | asb-private-holdout/word-freq | naive-solver | skill | baseline__skill | None | test | False | 17.9 | `sha256:fddac808e` |
| A | asb-private-holdout/word-freq | plan-solver | baseline | baseline__plan,baseline__skill,baseline__bundle | None | test | False | 18.3 | `sha256:ef86ddcfc` |
| A | asb-private-holdout/word-freq | plan-solver | bundle | baseline__bundle,plan__bundle | 1.0 | ok | True | 17.9 | `sha256:efa26a5db` |
| A | asb-private-holdout/word-freq | plan-solver | plan | baseline__plan,plan__bundle | 1.0 | ok | False | 18.4 | `sha256:66a2c0b47` |
| A | asb-private-holdout/word-freq | plan-solver | skill | baseline__skill | None | test | True | 17.8 | `sha256:62f7db784` |
| A | asb-private-holdout/word-freq | skill-solver | baseline | baseline__plan,baseline__skill,baseline__bundle | None | test | False | 18.4 | `sha256:a8de7f77f` |
| A | asb-private-holdout/word-freq | skill-solver | bundle | baseline__bundle,plan__bundle | 1.0 | ok | True | 18.1 | `sha256:278542a30` |
| A | asb-private-holdout/word-freq | skill-solver | plan | baseline__plan,plan__bundle | None | test | False | 18.3 | `sha256:f5b610eb2` |
| A | asb-private-holdout/word-freq | skill-solver | skill | baseline__skill | None | test | True | 17.8 | `sha256:3059cabde` |
| A | asb/csv-sum | naive-solver | baseline | baseline__plan,baseline__skill,baseline__bundle | 1.0 | ok | False | 17.6 | `sha256:cf8892108` |
| A | asb/csv-sum | naive-solver | bundle | baseline__bundle,plan__bundle | 1.0 | ok | False | 18.4 | `sha256:e507ddb5c` |
| A | asb/csv-sum | naive-solver | plan | baseline__plan,plan__bundle | 1.0 | ok | False | 17.5 | `sha256:7175770bc` |
| A | asb/csv-sum | naive-solver | skill | baseline__skill | 1.0 | ok | False | 18.5 | `sha256:12d7c725f` |
| A | asb/csv-sum | plan-solver | baseline | baseline__plan,baseline__skill,baseline__bundle | 1.0 | ok | False | 17.7 | `sha256:153f402f1` |
| A | asb/csv-sum | plan-solver | bundle | baseline__bundle,plan__bundle | 1.0 | ok | True | 18.9 | `sha256:bd1a1bf16` |
| A | asb/csv-sum | plan-solver | plan | baseline__plan,plan__bundle | 1.0 | ok | False | 17.6 | `sha256:fed06e75e` |
| A | asb/csv-sum | plan-solver | skill | baseline__skill | 1.0 | ok | True | 18.6 | `sha256:75985ab6a` |
| A | asb/csv-sum | skill-solver | baseline | baseline__plan,baseline__skill,baseline__bundle | 0.0 | model | False | 17.5 | `sha256:7a6ecc146` |
| A | asb/csv-sum | skill-solver | bundle | baseline__bundle,plan__bundle | 1.0 | ok | True | 18.3 | `sha256:2c4c4dd2d` |
| A | asb/csv-sum | skill-solver | plan | baseline__plan,plan__bundle | 1.0 | ok | False | 17.4 | `sha256:01d4c46af` |
| A | asb/csv-sum | skill-solver | skill | baseline__skill | 1.0 | ok | True | 18.5 | `sha256:2c8b3800f` |
| A | asb/fizzbuzz | naive-solver | baseline | baseline__plan,baseline__skill,baseline__bundle | 1.0 | ok | False | 17.5 | `sha256:caaf091d6` |
| A | asb/fizzbuzz | naive-solver | bundle | baseline__bundle,plan__bundle | 1.0 | ok | False | 18.4 | `sha256:9b3511b16` |
| A | asb/fizzbuzz | naive-solver | plan | baseline__plan,plan__bundle | 1.0 | ok | False | 17.5 | `sha256:5d1b5ed70` |
| A | asb/fizzbuzz | naive-solver | skill | baseline__skill | 1.0 | ok | False | 18.4 | `sha256:5d14dbef3` |
| A | asb/fizzbuzz | plan-solver | baseline | baseline__plan,baseline__skill,baseline__bundle | 1.0 | ok | False | 17.5 | `sha256:419142e79` |
| A | asb/fizzbuzz | plan-solver | bundle | baseline__bundle,plan__bundle | 1.0 | ok | True | 18.7 | `sha256:f5d5ef1b4` |
| A | asb/fizzbuzz | plan-solver | plan | baseline__plan,plan__bundle | 1.0 | ok | False | 17.6 | `sha256:77f44a9b2` |
| A | asb/fizzbuzz | plan-solver | skill | baseline__skill | 1.0 | ok | True | 18.5 | `sha256:61ac2bf9e` |
| A | asb/fizzbuzz | skill-solver | baseline | baseline__plan,baseline__skill,baseline__bundle | 0.0 | model | False | 17.6 | `sha256:54d383cfe` |
| A | asb/fizzbuzz | skill-solver | bundle | baseline__bundle,plan__bundle | 1.0 | ok | True | 18.5 | `sha256:059a1d574` |
| A | asb/fizzbuzz | skill-solver | plan | baseline__plan,plan__bundle | 1.0 | ok | False | 17.6 | `sha256:9560c3913` |
| A | asb/fizzbuzz | skill-solver | skill | baseline__skill | 1.0 | ok | True | 18.5 | `sha256:54e6d4aaf` |
| A | asb/reverse-string | naive-solver | baseline | baseline__plan,baseline__skill,baseline__bundle | 1.0 | ok | False | 18.3 | `sha256:3c2df77da` |
| A | asb/reverse-string | naive-solver | bundle | baseline__bundle,plan__bundle | 1.0 | ok | False | 23.1 | `sha256:654f1b496` |
| A | asb/reverse-string | naive-solver | plan | baseline__plan,plan__bundle | 1.0 | ok | False | 19.9 | `sha256:5ae74ecd4` |
| A | asb/reverse-string | naive-solver | skill | baseline__skill | 1.0 | ok | False | 21.8 | `sha256:26b932467` |
| A | asb/reverse-string | plan-solver | baseline | baseline__plan,baseline__skill,baseline__bundle | 1.0 | ok | False | 17.5 | `sha256:58a8edf9a` |
| A | asb/reverse-string | plan-solver | bundle | baseline__bundle,plan__bundle | 1.0 | ok | True | 18.4 | `sha256:d48e0e5cd` |
| A | asb/reverse-string | plan-solver | plan | baseline__plan,plan__bundle | 1.0 | ok | False | 17.6 | `sha256:35e4d3464` |
| A | asb/reverse-string | plan-solver | skill | baseline__skill | 1.0 | ok | True | 18.5 | `sha256:fcac1714c` |
| A | asb/reverse-string | skill-solver | baseline | baseline__plan,baseline__skill,baseline__bundle | 0.0 | model | False | 17.8 | `sha256:c37dd021b` |
| A | asb/reverse-string | skill-solver | bundle | baseline__bundle,plan__bundle | 1.0 | ok | True | 18.9 | `sha256:e612306ec` |
| A | asb/reverse-string | skill-solver | plan | baseline__plan,plan__bundle | 1.0 | ok | False | 18.3 | `sha256:3a093b235` |
| A | asb/reverse-string | skill-solver | skill | baseline__skill | 1.0 | ok | True | 19.0 | `sha256:9a33a9a89` |
| A | asb/slugify | naive-solver | baseline | baseline__plan,baseline__skill,baseline__bundle | 1.0 | ok | False | 17.6 | `sha256:25714b72f` |
| A | asb/slugify | naive-solver | bundle | baseline__bundle,plan__bundle | 1.0 | ok | False | 18.3 | `sha256:4abceacc9` |
| A | asb/slugify | naive-solver | plan | baseline__plan,plan__bundle | 1.0 | ok | False | 17.6 | `sha256:601cf54b3` |
| A | asb/slugify | naive-solver | skill | baseline__skill | 1.0 | ok | False | 18.5 | `sha256:26e02fbf4` |
| A | asb/slugify | plan-solver | baseline | baseline__plan,baseline__skill,baseline__bundle | 1.0 | ok | False | 17.5 | `sha256:918c1256d` |
| A | asb/slugify | plan-solver | bundle | baseline__bundle,plan__bundle | 1.0 | ok | True | 18.6 | `sha256:146556c60` |
| A | asb/slugify | plan-solver | plan | baseline__plan,plan__bundle | 1.0 | ok | False | 17.5 | `sha256:0a5400a0e` |
| A | asb/slugify | plan-solver | skill | baseline__skill | 1.0 | ok | True | 18.5 | `sha256:82319f127` |
| A | asb/slugify | skill-solver | baseline | baseline__plan,baseline__skill,baseline__bundle | 0.0 | model | False | 17.5 | `sha256:d1870a651` |
| A | asb/slugify | skill-solver | bundle | baseline__bundle,plan__bundle | 1.0 | ok | True | 18.6 | `sha256:a6305c41e` |
| A | asb/slugify | skill-solver | plan | baseline__plan,plan__bundle | 1.0 | ok | False | 17.7 | `sha256:6eb8a6fae` |
| A | asb/slugify | skill-solver | skill | baseline__skill | 1.0 | ok | True | 18.6 | `sha256:9ebe8cf25` |

## Counts by failure class

- `ok`: 72
- `agent`: 0
- `model`: 4
- `test`: 20
- `infra`: 0
