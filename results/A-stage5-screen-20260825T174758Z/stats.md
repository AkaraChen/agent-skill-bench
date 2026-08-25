# Statistical report

These numbers are per-slice evidence, not a ranking and not a single score. Infra errors are excluded from success rate and paired tests.

- Rows: 96
- Paired: baseline vs bundle (n=8)
- Mean diff: 0.41666666666666663 CI [0.3333333333333333, 0.5833333333333334]
- McNemar p=1.0 n01=1 n10=0

## Slices (agent × treatment)

- naive-solver / baseline: success=0.75 n=8 infra=0 cost=0.002 duration=18.30516475 failures={'ok': 6, 'test': 2}
- naive-solver / bundle: success=0.875 n=8 infra=0 cost=0.0025 duration=18.955323625 failures={'ok': 7, 'test': 1}
- naive-solver / plan: success=0.875 n=8 infra=0 cost=0.0025 duration=18.441564625 failures={'ok': 7, 'test': 1}
- naive-solver / skill: success=0.75 n=8 infra=0 cost=0.002 duration=18.652268375 failures={'ok': 6, 'test': 2}
- plan-solver / baseline: success=0.75 n=8 infra=0 cost=0.022000000000000002 duration=18.04251525 failures={'ok': 6, 'test': 2}
- plan-solver / bundle: success=0.875 n=8 infra=0 cost=0.034375 duration=18.53368875 failures={'ok': 7, 'test': 1}
- plan-solver / plan: success=0.875 n=8 infra=0 cost=0.027500000000000004 duration=18.008931 failures={'ok': 7, 'test': 1}
- plan-solver / skill: success=0.75 n=8 infra=0 cost=0.026400000000000003 duration=18.302079374999998 failures={'ok': 6, 'test': 2}
- skill-solver / baseline: success=0.0 n=8 infra=0 cost=0.008 duration=17.99865075 failures={'test': 4, 'model': 4}
- skill-solver / bundle: success=1.0 n=8 infra=0 cost=0.0125 duration=18.483446875 failures={'ok': 8}
- skill-solver / plan: success=0.75 n=8 infra=0 cost=0.01 duration=18.0125135 failures={'ok': 6, 'test': 2}
- skill-solver / skill: success=0.75 n=8 infra=0 cost=0.0096 duration=18.369939125 failures={'ok': 6, 'test': 2}
