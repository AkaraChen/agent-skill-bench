import os
from pathlib import Path
APP = Path(os.environ.get("APP", "/app"))
values = [float(line) for line in (APP / "series.txt").read_text().splitlines() if line.strip() != ""]
w = int((APP / "window.txt").read_text().strip())
out = []
for i in range(len(values)):
    window = values[i:i + w - 1]  # bug: off-by-one and looks forward
    out.append(str(sum(window) / len(window)))
(APP / "output.txt").write_text("\n".join(out) + "\n")
