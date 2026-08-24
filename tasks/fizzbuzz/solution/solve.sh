#!/bin/bash
python3 - << 'PY'
from pathlib import Path
n = int(Path("/app/n.txt").read_text().strip())
lines = []
for i in range(1, n + 1):
    if i % 15 == 0:
        lines.append("FizzBuzz")
    elif i % 3 == 0:
        lines.append("Fizz")
    elif i % 5 == 0:
        lines.append("Buzz")
    else:
        lines.append(str(i))
Path("/app/output.txt").write_text("\n".join(lines) + "\n")
PY
