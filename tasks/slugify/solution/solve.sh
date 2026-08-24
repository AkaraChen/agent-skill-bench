#!/bin/bash
python3 - << 'PY'
import re
from pathlib import Path
raw = Path("/app/title.txt").read_text().strip().lower()
slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
Path("/app/slug.txt").write_text(slug + "\n")
PY
