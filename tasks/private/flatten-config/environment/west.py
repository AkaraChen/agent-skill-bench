import json, os
from pathlib import Path
APP = Path(os.environ.get("APP", "/app"))
data = json.loads((APP / "input.json").read_text())
# lists joined as comma strings
rows = []
def walk(prefix, value):
    if isinstance(value, dict):
        for k, v in value.items():
            walk(f"{prefix}.{k}" if prefix else k, v)
    elif isinstance(value, list):
        rows.append(f"{prefix}=" + ",".join(map(str, value)))
    else:
        rows.append(f"{prefix}={value}")
walk("", data)
(APP / "west.txt").write_text("\n".join(sorted(rows)) + "\n")
