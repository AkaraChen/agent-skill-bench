import os
from pathlib import Path
APP = Path(os.environ.get("APP", "/app"))
text = (APP / "input.txt").read_text().strip()
ok = text.count("(") == text.count(")") and text.count("[") == text.count("]") and text.count("{") == text.count("}")
(APP / "output.txt").write_text("ok\n" if ok else "bad\n")
