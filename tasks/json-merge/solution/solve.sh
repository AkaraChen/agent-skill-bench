#!/bin/bash
python3 - << 'PY'
import json
from pathlib import Path
a = json.loads(Path("/app/a.json").read_text())
b = json.loads(Path("/app/b.json").read_text())
merged = {**a, **b}
Path("/app/merged.json").write_text(json.dumps(merged, separators=(",", ":"), sort_keys=True) + "\n")
PY
