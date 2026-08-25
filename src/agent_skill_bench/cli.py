from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent_skill_bench.constants import repo_root
from agent_skill_bench.dataset import revision_payload
from agent_skill_bench.experiment import ExperimentError, load_yaml
from agent_skill_bench.holdout import HoldoutError, assemble_dataset, fetch_sealed, generate
from agent_skill_bench.pipeline import format_pipeline, plan_pipeline
from agent_skill_bench.policy import list_expired_jobs
from agent_skill_bench.report import write_report
from agent_skill_bench.run import cancel_job, run_job
from agent_skill_bench.summarize import summarize_latest
from agent_skill_bench.validity import ValidityError, validate_private, write_validity_report
from agent_skill_bench.warehouse import index_jobs, write_warehouse


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

    cancel_p = sub.add_parser("cancel", help="Cancel a running or paused Harbor job.")
    cancel_p.add_argument("job", type=Path)

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

    report_p = sub.add_parser(
        "report",
        help="Warehouse + stats + dashboard. No composite score.",
    )
    report_p.add_argument("--job", type=Path, default=None)
    report_p.add_argument("--jobs-dir", type=Path, default=None)
    report_p.add_argument("--out", type=Path, default=None)

    wh_p = sub.add_parser("warehouse", help="Index trial_id → manifest and artifacts.")
    wh_p.add_argument("--jobs-dir", type=Path, default=None)
    wh_p.add_argument("--out", type=Path, default=None)

    pipe_p = sub.add_parser("pipeline", help="Screen then confirm. Ranking is a filter.")
    pipe_p.add_argument("--config", type=Path, required=True)
    pipe_p.add_argument("--results", type=Path, default=None, help="Screen results.json")
    pipe_p.add_argument("--dry-run", action="store_true")

    prune_p = sub.add_parser("prune", help="List (or delete) jobs past retention_days.")
    prune_p.add_argument("--days", type=int, required=True)
    prune_p.add_argument("--jobs-dir", type=Path, default=None)
    prune_p.add_argument("--delete", action="store_true", help="Actually delete expired jobs.")

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
    if args.cmd == "cancel":
        print(cancel_job(args.job))
        return 0
    if args.cmd == "summarize":
        md_path = summarize_latest(args.jobs_dir, args.out)
        print(md_path)
        return 0
    if args.cmd == "validate":
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
    if args.cmd == "report":
        path = write_report(args.job, jobs_dir=args.jobs_dir, out_dir=args.out)
        print(path)
        return 0
    if args.cmd == "warehouse":
        payload = index_jobs(args.jobs_dir)
        out = args.out or (repo_root() / "results" / "warehouse")
        print(write_warehouse(payload, out))
        return 0
    if args.cmd == "pipeline":
        try:
            spec = load_yaml(args.config)
            screen_ref = (spec.get("screen") or {}).get("experiment")
            if not screen_ref:
                raise ExperimentError("pipeline needs screen.experiment")
            screen_path = Path(screen_ref)
            if not screen_path.is_absolute():
                screen_path = repo_root() / screen_ref
            screen_spec = load_yaml(screen_path)
            rows = []
            if args.results and args.results.exists():
                rows = json.loads(args.results.read_text()).get("rows") or []
            payload = plan_pipeline(spec, screen_spec, repo_root(), rows)
            print(format_pipeline(payload))
        except ExperimentError as exc:
            print(f"error: {exc}")
            return 2
        if args.dry_run:
            return 0
        confirm_path = repo_root() / "jobs" / ".generated" / f"{payload['name']}-confirm.yaml"
        confirm_path.parent.mkdir(parents=True, exist_ok=True)
        import yaml

        confirm_path.write_text(yaml.safe_dump(payload["confirm"]["spec"], sort_keys=False))
        print(confirm_path)
        return 0
    if args.cmd == "prune":
        import shutil

        jobs_dir = args.jobs_dir or (repo_root() / "jobs")
        expired = list_expired_jobs(jobs_dir, args.days)
        for path in expired:
            print(path)
        if args.delete:
            for path in expired:
                shutil.rmtree(path)
        return 0
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
