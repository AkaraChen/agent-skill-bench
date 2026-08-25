`/app/east.py` and `/app/west.py` must flatten `/app/input.json` into dotted keys. Objects use `.`, lists use `.0`, `.1`, … Leaves are JSON-encoded with compact separators. Write `key=value` lines in depth-first discovery order (do not sort) to `/app/east.txt` and `/app/west.txt`. Both files currently disagree on lists; make them match the spec.

Also write `2026.08.25.r3` followed by a newline to `/app/ASB_REVISION`.
