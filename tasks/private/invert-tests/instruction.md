`/app/impl.py` implements `add(a, b)` correctly. `/app/test_impl.py` currently asserts the wrong result. Fix the tests so they pass against the real implementation and fail against a broken `add` that returns `a + b + 1`. Keep `test_impl.py` runnable as a script (exit 0 on success).

Also write `2026.08.25.r2` followed by a newline to `/app/ASB_REVISION`.
