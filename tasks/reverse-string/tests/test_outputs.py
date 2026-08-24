from pathlib import Path
import sys
sys.path.append("/tests")
from canary import assert_no_canary_in_app

src = Path("/app/input.txt").read_text()
got = Path("/app/output.txt").read_text()
assert got == src[::-1], repr(got)
assert_no_canary_in_app()
