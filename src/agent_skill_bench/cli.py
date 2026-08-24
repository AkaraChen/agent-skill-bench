from __future__ import annotations

import argparse
from pathlib import Path

from agent_skill_bench.run import run_smoke
from agent_skill_bench.summarize import summarize_latest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="asb",
        description="Agent-skill-bench: Harbor 2x2 smoke loop (KIT-908).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="Start the frozen 2x2 smoke job (20 trials).")
    run_p.add_argument("--config", type=Path, default=None)
    run_p.add_argument("-n", "--n-concurrent", type=int, default=2)

    sum_p = sub.add_parser("summarize", help="Summarize the latest Harbor job.")
    sum_p.add_argument("--jobs-dir", type=Path, default=None)
    sum_p.add_argument("--out", type=Path, default=None)

    args = parser.parse_args(argv)
    if args.cmd == "run":
        job_dir = run_smoke(args.config, n_concurrent=args.n_concurrent)
        print(job_dir)
        return 0
    if args.cmd == "summarize":
        md_path = summarize_latest(args.jobs_dir, args.out)
        print(md_path)
        return 0
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
