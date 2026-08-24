from pathlib import Path
import sys
sys.path.append("/tests")
from canary import assert_no_canary_in_app

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
expected = "\n".join(lines) + "\n"
got = Path("/app/output.txt").read_text()
assert got == expected, repr(got)
assert_no_canary_in_app()
