# Statistical report

These numbers are per-slice evidence, not a ranking and not a single score. Infra errors are excluded from success rate and paired tests.

- Rows: 144
- Paired: bundle vs plan (n=4)
- Mean diff: -0.08333333333333333 CI [-0.25, 0.0]
- McNemar p=1.0 n01=0 n10=0

## Slices (agent × treatment)

- naive-solver / bundle: success=0.75 n=24 infra=0 cost=0.0175 duration=18.590551416666667 failures={'ok': 18, 'test': 6}
- naive-solver / plan: success=0.75 n=24 infra=0 cost=0.0175 duration=18.262251375 failures={'ok': 18, 'test': 6}
- plan-solver / bundle: success=0.875 n=24 infra=0 cost=0.0240625 duration=18.40178475 failures={'ok': 21, 'test': 3}
- plan-solver / plan: success=0.75 n=24 infra=0 cost=0.019250000000000003 duration=18.180119208333334 failures={'ok': 18, 'test': 6}
- skill-solver / bundle: success=0.875 n=24 infra=0 cost=0.021875000000000002 duration=18.446360583333334 failures={'ok': 21, 'test': 3}
- skill-solver / plan: success=0.75 n=24 infra=0 cost=0.0175 duration=18.286986958333333 failures={'ok': 18, 'test': 6}
