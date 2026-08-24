from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANARY = "ASB_HIDDEN_CANARY_DO_NOT_LEAK_9f3c"
DIGEST = "sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7"

DOCKERFILE = f"""FROM python:3.12.11-slim-bookworm@{DIGEST}
WORKDIR /app
COPY . /app
RUN rm -f /app/Dockerfile
"""

TASK_TOML = """schema_version = "1.4"

[task]
name = "asb/{name}"
version = "1.0.0"

[metadata]
difficulty = "easy"
category = "programming"
tags = ["smoke", "stage1"]

[verifier]
timeout_sec = 60.0
network_mode = "no-network"

[agent]
timeout_sec = 60.0
network_mode = "no-network"

[environment]
build_timeout_sec = 300.0
cpus = 1
memory_mb = 512
storage_mb = 1024
gpus = 0
workdir = "/app"
network_mode = "no-network"

[[artifacts]]
source = "/app"
destination = "workspace"
"""

TEST_SH = """#!/bin/bash
python3 /tests/test_outputs.py
status=$?
if [ "$status" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
exit "$status"
"""

CANARY_CHECK = f'''from pathlib import Path

CANARY = "{CANARY}"

def assert_no_canary_in_app() -> None:
    for path in Path("/app").rglob("*"):
        if path.is_file():
            text = path.read_text(errors="ignore")
            assert CANARY not in text, f"hidden canary leaked into {{path}}"
'''

TASKS = {
    "reverse-string": {
        "instruction": "Reverse the exact contents of `/app/input.txt` and write the reversed text to `/app/output.txt`. Preserve every character, including newlines. Do not add extra characters.",
        "env": {"input.txt": "harbor-smoke"},
        "test": '''from pathlib import Path
import sys
sys.path.append("/tests")
from canary import assert_no_canary_in_app

src = Path("/app/input.txt").read_text()
got = Path("/app/output.txt").read_text()
assert got == src[::-1], repr(got)
assert_no_canary_in_app()
''',
        "solve": "#!/bin/bash\npython3 -c \"from pathlib import Path; p=Path('/app/input.txt'); Path('/app/output.txt').write_text(p.read_text()[::-1])\"\n",
    },
    "fizzbuzz": {
        "instruction": "Read n from `/app/n.txt`. Write FizzBuzz for 1 through n inclusive to `/app/output.txt`, one token per line. Use Fizz for multiples of 3, Buzz for multiples of 5, FizzBuzz for multiples of both, and the number otherwise. End the file with a newline.",
        "env": {"n.txt": "15\n"},
        "test": r'''from pathlib import Path
import sys
sys.path.append("/tests")
from canary import assert_no_canary_in_app

n = int(Path("/app/n.txt").read_text().strip())
lines = []
for i in range(1, n + 1):
    if i % 15 == 0:
        lines.append("FizzBuzz")
    elif i % 3 == 0:
        lines.append("Fizz")
    elif i % 5 == 0:
        lines.append("Buzz")
    else:
        lines.append(str(i))
expected = "\n".join(lines) + "\n"
got = Path("/app/output.txt").read_text()
assert got == expected, repr(got)
assert_no_canary_in_app()
''',
        "solve": r'''#!/bin/bash
python3 - << 'PY'
from pathlib import Path
n = int(Path("/app/n.txt").read_text().strip())
lines = []
for i in range(1, n + 1):
    if i % 15 == 0:
        lines.append("FizzBuzz")
    elif i % 3 == 0:
        lines.append("Fizz")
    elif i % 5 == 0:
        lines.append("Buzz")
    else:
        lines.append(str(i))
Path("/app/output.txt").write_text("\n".join(lines) + "\n")
PY
''',
    },
    "csv-sum": {
        "instruction": "Read /app/data.csv with headers name,amount. Sum the amount column as integers and write the total followed by a newline to /app/output.txt.",
        "env": {"data.csv": "name,amount\nalice,10\nbob,25\ncarol,7\n"},
        "test": r'''from pathlib import Path
import csv
import sys
sys.path.append("/tests")
from canary import assert_no_canary_in_app

total = 0
with Path("/app/data.csv").open() as handle:
    for row in csv.DictReader(handle):
        total += int(row["amount"])
got = Path("/app/output.txt").read_text().strip()
assert got == str(total), repr(got)
assert_no_canary_in_app()
''',
        "solve": r'''#!/bin/bash
python3 - << 'PY'
import csv
from pathlib import Path
total = 0
with Path("/app/data.csv").open() as handle:
    for row in csv.DictReader(handle):
        total += int(row["amount"])
Path("/app/output.txt").write_text(str(total) + "\n")
PY
''',
    },
    "json-merge": {
        "instruction": "Shallow-merge `/app/a.json` and `/app/b.json` into `/app/merged.json`. Keys from b overwrite keys from a. Write compact JSON with sorted keys and a trailing newline.",
        "env": {
            "a.json": '{"keep":1,"overlap":"a","nested":{"x":1}}\n',
            "b.json": '{"overlap":"b","added":2,"nested":{"y":2}}\n',
        },
        "test": r'''import json
from pathlib import Path
import sys
sys.path.append("/tests")
from canary import assert_no_canary_in_app

a = json.loads(Path("/app/a.json").read_text())
b = json.loads(Path("/app/b.json").read_text())
expected = {**a, **b}
got = json.loads(Path("/app/merged.json").read_text())
assert got == expected, got
raw = Path("/app/merged.json").read_text()
assert raw.endswith("\n")
assert_no_canary_in_app()
''',
        "solve": r'''#!/bin/bash
python3 - << 'PY'
import json
from pathlib import Path
a = json.loads(Path("/app/a.json").read_text())
b = json.loads(Path("/app/b.json").read_text())
merged = {**a, **b}
Path("/app/merged.json").write_text(json.dumps(merged, separators=(",", ":"), sort_keys=True) + "\n")
PY
''',
    },
    "slugify": {
        "instruction": "Read `/app/title.txt`, lowercase it, replace each run of non-alphanumeric characters with a single hyphen, strip leading and trailing hyphens, and write the slug plus a newline to `/app/slug.txt`.",
        "env": {"title.txt": "Hello, Harbor Bench!\n"},
        "test": r'''import re
from pathlib import Path
import sys
sys.path.append("/tests")
from canary import assert_no_canary_in_app

raw = Path("/app/title.txt").read_text().strip().lower()
expected = re.sub(r"[^a-z0-9]+", "-", raw).strip("-") + "\n"
got = Path("/app/slug.txt").read_text()
assert got == expected, repr(got)
assert_no_canary_in_app()
''',
        "solve": r'''#!/bin/bash
python3 - << 'PY'
import re
from pathlib import Path
raw = Path("/app/title.txt").read_text().strip().lower()
slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
Path("/app/slug.txt").write_text(slug + "\n")
PY
''',
    },
}


def main() -> None:
    for name, spec in TASKS.items():
        base = ROOT / "tasks" / name
        env = base / "environment"
        tests = base / "tests"
        solution = base / "solution"
        env.mkdir(parents=True, exist_ok=True)
        tests.mkdir(parents=True, exist_ok=True)
        solution.mkdir(parents=True, exist_ok=True)
        (base / "instruction.md").write_text(spec["instruction"] + "\n")
        (base / "task.toml").write_text(TASK_TOML.format(name=name))
        (env / "Dockerfile").write_text(DOCKERFILE)
        for fname, content in spec["env"].items():
            (env / fname).write_text(content)
        (tests / "test.sh").write_text(TEST_SH)
        (tests / "canary.py").write_text(CANARY_CHECK + "\n")
        (tests / "test_outputs.py").write_text(spec["test"])
        (tests / "HIDDEN_CANARY.txt").write_text(CANARY + "\n")
        (solution / "solve.sh").write_text(spec["solve"])
        (solution / "HIDDEN_CANARY.txt").write_text(CANARY + "\n")
        (tests / "test.sh").chmod(0o755)
        (solution / "solve.sh").chmod(0o755)
        print("wrote", name)


if __name__ == "__main__":
    main()
