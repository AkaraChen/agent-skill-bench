import re
from pathlib import Path
import sys
sys.path.append("/tests")
from canary import assert_no_canary_in_app

raw = Path("/app/title.txt").read_text().strip().lower()
expected = re.sub(r"[^a-z0-9]+", "-", raw).strip("-") + "\n"
got = Path("/app/slug.txt").read_text()
assert got == expected, repr(got)
assert_no_canary_in_app()
