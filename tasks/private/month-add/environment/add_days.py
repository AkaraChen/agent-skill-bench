import os
from pathlib import Path
APP = Path(os.environ.get("APP", "/app"))
y, m, d = map(int, (APP / "date.txt").read_text().strip().split("-"))
n = int((APP / "days.txt").read_text().strip())
d += n
(APP / "output.txt").write_text(f"{y:04d}-{m:02d}-{d:02d}\n")
