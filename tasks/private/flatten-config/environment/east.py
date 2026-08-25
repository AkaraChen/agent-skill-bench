import json, os
from pathlib import Path
APP = Path(os.environ.get("APP", "/app"))
data = json.loads((APP / "input.json").read_text())
rows = []
def walk(prefix, value):
    if isinstance(value, dict):
        for k, v in value.items():
            walk(f"{prefix}.{k}" if prefix else k, v)
    else:
        rows.append(f"{prefix}={json.dumps(value, separators=(',', ':'))}")
walk("", data)
(APP / "east.txt").write_text("\n".join(sorted(rows)) + "\n")
