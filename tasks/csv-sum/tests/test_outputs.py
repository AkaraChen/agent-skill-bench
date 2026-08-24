from pathlib import Path
import csv
import sys
sys.path.append("/tests")
from canary import assert_no_canary_in_app

total = 0
with Path("/app/data.csv").open() as handle:
    for row in csv.DictReader(handle):
        total += int(row["amount"])
got = Path("/app/output.txt").read_text().strip()
assert got == str(total), repr(got)
assert_no_canary_in_app()
