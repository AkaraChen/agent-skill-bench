#!/bin/bash
python3 - << 'PY'
import csv
from pathlib import Path
total = 0
with Path("/app/data.csv").open() as handle:
    for row in csv.DictReader(handle):
        total += int(row["amount"])
Path("/app/output.txt").write_text(str(total) + "\n")
PY
