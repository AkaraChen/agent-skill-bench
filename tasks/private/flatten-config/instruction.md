`/app/east.py` and `/app/west.py` must flatten `/app/input.json` into dotted keys. Objects use `.`, lists use `.0`, `.1`, … Leaves are JSON-encoded with compact separators. Write sorted `key=value` lines to `/app/east.txt` and `/app/west.txt`. Both files currently disagree on lists; make them match the spec.

Also write `2026.08.25.r2` followed by a newline to `/app/ASB_REVISION`.
