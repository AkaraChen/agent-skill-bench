import os
from pathlib import Path
APP = Path(os.environ.get("APP", "/app"))
lines = (APP / "doc.md").read_text().splitlines()
out = [line[3:] for line in lines if line.startswith("## ")]
(APP / "toc.txt").write_text("\n".join(out) + "\n")
