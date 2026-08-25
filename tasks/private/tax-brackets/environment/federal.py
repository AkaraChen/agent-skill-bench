import os
from pathlib import Path
APP = Path(os.environ.get("APP", "/app"))
income = int((APP / "income.txt").read_text().strip())
tax = 0
if income > 0:
    slab = min(income, 10000)
    tax += slab * 0.10
if income > 10000:
    slab = min(income - 10000, 10000)
    tax += slab * 0.20
if income > 20000:
    tax += (income - 20000) * 0.30
(APP / "federal.txt").write_text(str(round(tax)) + "\n")
