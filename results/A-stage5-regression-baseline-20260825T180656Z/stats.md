# Statistical report

These numbers are per-slice evidence, not a ranking and not a single score. Infra errors are excluded from success rate and paired tests.

- Rows: 48
- Paired: baseline vs bundle (n=4)
- Mean diff: 0.625 CI [0.5, 0.875]
- McNemar p=1.0 n01=1 n10=0

## Slices (agent × treatment)

- plan-solver / baseline: success=0.75 n=12 infra=0 cost=0.0088 duration=18.600528666666666 failures={'ok': 9, 'test': 3}
- plan-solver / bundle: success=1.0 n=12 infra=0 cost=0.013750000000000004 duration=18.880066083333332 failures={'ok': 12}
- skill-solver / baseline: success=0.0 n=12 infra=0 cost=0.008 duration=17.563866333333333 failures={'test': 6, 'model': 6}
- skill-solver / bundle: success=1.0 n=12 infra=0 cost=0.012500000000000002 duration=18.429182583333333 failures={'ok': 12}
