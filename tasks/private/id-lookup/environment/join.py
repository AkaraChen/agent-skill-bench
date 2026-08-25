import csv, os
from pathlib import Path
APP = Path(os.environ.get("APP", "/app"))
users = list(csv.DictReader((APP / "users.csv").open()))
orders = list(csv.DictReader((APP / "orders.csv").open()))
out = ["order_id,name,item"]
for order in orders:
    for user in users:
        if user["name"] == order["user_id"]:  # bug: compares name to id
            out.append(f'{order["order_id"]},{user["name"]},{order["item"]}')
(APP / "joined.csv").write_text("\n".join(out) + "\n")
