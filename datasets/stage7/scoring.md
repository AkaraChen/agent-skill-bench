# Stage 7 scoring

- Hidden tests own execution reward. Infra errors are not model failure.
- Static checks are a second automatic axis, not a composite total.
- UI/visual/grill/review use blinded human packets (no agent/model/treatment).
- LLM judge is auxiliary only.
- Review scores TP/FP/FN against a gold finding list.
- Cost and duration are reported, never mixed into a single score.

## Axes

- `correctness` (pass/fail): Hidden tests and stated oracle passed?
- `hidden_tests` (pass/fail): Hidden tests passed? Infra errors are not model failure.
- `static_checks` (pass/fail): Format/lint/typecheck/compile of the touched path passed?
- `diff_quality` (1-5): Is the diff local, named honestly, and free of drive-by edits?
- `overengineering` (1-5): Did the agent add unneeded abstractions, tools, or files?
- `test_value` (1-5): Did tests lock a real contract instead of mirroring code or chasing coverage?
- `ui_correctness` (1-5): Does the UI disclose the right information and hide internals?
- `visual_quality` (1-5): Visual craft only: tokens, anti-slop, landing vs app. Ignore usefulness.
- `review_tp` (count): True-positive findings vs the gold list.
- `review_fp` (count): False-positive findings vs the gold list.
- `review_fn` (count): Missed gold findings.
- `cost_usd` (usd): Trial USD cost from the agent metrics.
- `duration_sec` (seconds): Wall-clock duration.
