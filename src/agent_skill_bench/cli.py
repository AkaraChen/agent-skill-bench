from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent_skill_bench.dataset import revision_payload
from agent_skill_bench.experiment import ExperimentError
from agent_skill_bench.holdout import HoldoutError, assemble_dataset, fetch_sealed, generate
from agent_skill_bench.run import run_job
from agent_skill_bench.summarize import summarize_latest
from agent_skill_bench.validity import ValidityError, validate_private, write_validity_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="asb",
        description="Agent-skill-bench: Harbor experiment runner.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="Expand an experiment YAML and start a Harbor job.")
    run_p.add_argument("--config", type=Path, default=None)
    run_p.add_argument("-n", "--n-concurrent", type=int, default=None)
    run_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print cells, trial count, and budget, then exit without running.",
    )
    run_p.add_argument(
        "--resume",
        type=Path,
        default=None,
        help="Resume an existing Harbor job directory (harbor job resume).",
    )

    sum_p = sub.add_parser("summarize", help="Summarize the latest Harbor job.")
    sum_p.add_argument("--jobs-dir", type=Path, default=None)
    sum_p.add_argument("--out", type=Path, default=None)

    val_p = sub.add_parser(
        "validate",
        help="Fail-closed gates on the immutable sealed corpus (does not generate).",
    )
    val_p.add_argument("--out", type=Path, default=None)

    sub.add_parser(
        "generate-holdout",
        help="Write sealed corpus + public manifest from the sealed catalog. Not used by validate.",
    )
    sub.add_parser(
        "fetch-sealed",
        help="Clone the pinned private holdout repo and verify digests.",
    )
    sub.add_parser(
        "assemble",
        help="Merge public task trees with sealed tests/solution for Harbor.",
    )

    sub.add_parser("dataset", help="Print the pinned dataset revision.")

    args = parser.parse_args(argv)
    if args.cmd == "run":
        try:
            job_dir = run_job(
                args.config,
                n_concurrent=args.n_concurrent,
                dry_run=args.dry_run,
                resume=args.resume,
            )
        except ExperimentError as exc:
            print(f"error: {exc}")
            return 2
        if job_dir is not None:
            print(job_dir)
        return 0
    if args.cmd == "summarize":
        md_path = summarize_latest(args.jobs_dir, args.out)
        print(md_path)
        return 0
    if args.cmd == "validate":
        from agent_skill_bench.constants import repo_root

        try:
            payload = validate_private(execute=True)
        except ValidityError as exc:
            print(f"error: {exc}")
            return 2
        out = args.out or (repo_root() / "results" / "validity")
        md_path = write_validity_report(payload, out)
        print(md_path)
        print(f"pass={payload['n_pass']} fail={payload['n_fail']} quarantined={payload['n_quarantined']}")
        return 0 if not payload["live_failures"] else 1
    if args.cmd == "generate-holdout":
        try:
            path = generate()
        except HoldoutError as exc:
            print(f"error: {exc}")
            return 2
        print(path)
        return 0
    if args.cmd == "fetch-sealed":
        try:
            path = fetch_sealed()
        except HoldoutError as exc:
            print(f"error: {exc}")
            return 2
        print(path)
        return 0
    if args.cmd == "assemble":
        try:
            path = assemble_dataset()
        except HoldoutError as exc:
            print(f"error: {exc}")
            return 2
        print(path)
        return 0
    if args.cmd == "dataset":
        print(json.dumps(revision_payload(), indent=2))
        return 0
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
