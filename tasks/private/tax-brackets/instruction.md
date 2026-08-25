`/app/federal.py` and `/app/state.py` both compute tax from `/app/income.txt` using brackets `0-10k: 10%`, `10k-20k: 20%`, `above 20k: 30%` (marginal). `state.py` drifted. Make both write the same integer cents using `math.floor` to `/app/federal.txt` and `/app/state.txt` as a single integer line. You may share logic.

Also write `2026.08.25.r3` followed by a newline to `/app/ASB_REVISION`.
