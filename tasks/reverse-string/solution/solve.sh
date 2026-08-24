#!/bin/bash
python3 -c "from pathlib import Path; p=Path('/app/input.txt'); Path('/app/output.txt').write_text(p.read_text()[::-1])"
