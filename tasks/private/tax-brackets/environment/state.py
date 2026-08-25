import os
from pathlib import Path
APP = Path(os.environ.get("APP", "/app"))
income = int((APP / "income.txt").read_text().strip())
# drifted: 15% flat
(APP / "state.txt").write_text(str(round(income * 0.15)) + "\n")
