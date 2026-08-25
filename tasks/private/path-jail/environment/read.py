import os
from pathlib import Path
APP = Path(os.environ.get("APP", "/app"))
rel = (APP / "path.txt").read_text().strip()
target = str(APP / "data") + "/" + rel
if target.startswith(str(APP / "data")):
    (APP / "output.txt").write_text(Path(target).read_text())
else:
    (APP / "output.txt").write_text("DENIED\n")
