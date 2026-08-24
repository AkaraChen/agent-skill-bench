import json
from pathlib import Path
import sys
sys.path.append("/tests")
from canary import assert_no_canary_in_app

a = json.loads(Path("/app/a.json").read_text())
b = json.loads(Path("/app/b.json").read_text())
expected = {**a, **b}
got = json.loads(Path("/app/merged.json").read_text())
assert got == expected, got
raw = Path("/app/merged.json").read_text()
assert raw.endswith("\n")
assert_no_canary_in_app()
