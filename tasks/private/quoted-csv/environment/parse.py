import os
from pathlib import Path
APP = Path(os.environ.get("APP", "/app"))
lines = (APP / "input.csv").read_text().splitlines()
out = []
for line in lines:
    fields = line.split(",")
    out.append(str(len(fields)) + " " + "|".join(fields))
(APP / "output.txt").write_text("\n".join(out) + "\n")
