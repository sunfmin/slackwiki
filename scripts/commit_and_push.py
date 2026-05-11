"""Commit raw/, wiki/, state/, CLAUDE.md, .claude/ changes and push.

Modes:
  commit         (default): commit to the current branch and push, rebasing on top of origin.
  pull-request:            create a new branch, push it, open a PR. Used by weekly-lint.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path


REPO_ROOT = Path(os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
PATHS_TO_STAGE = [
    "raw",
    "wiki",
    "state",
    "CLAUDE.md",
    ".claude",
    "slackwiki.config.yml",
    ".gitignore",
    ".github",
]


def run(*cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(cmd)}", flush=True)
    return subprocess.run(list(cmd), cwd=REPO_ROOT, check=check, text=True)


def has_staged_changes() -> bool:
    return subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=REPO_ROOT
    ).returncode != 0


def configure_identity() -> None:
    run("git", "config", "user.name", "github-actions[bot]")
    run(
        "git", "config", "user.email",
        "41898282+github-actions[bot]@users.noreply.github.com",
    )


def commit_message(label: str) -> str:
    return f"{label}: {date.today().isoformat()}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["commit", "pull-request"], default="commit")
    parser.add_argument("--label", default="ingest", help="commit-message prefix")
    args = parser.parse_args()

    configure_identity()

    existing = [p for p in PATHS_TO_STAGE if (REPO_ROOT / p).exists()]
    if not existing:
        print("nothing to stage")
        return 0
    run("git", "add", "--", *existing)

    if not has_staged_changes():
        print("no changes to commit")
        return 0

    if args.mode == "pull-request":
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
        branch = f"slackwiki/{args.label}-{ts}"
        run("git", "checkout", "-b", branch)
        run("git", "commit", "-m", commit_message(args.label))
        run("git", "push", "-u", "origin", branch)
        title = commit_message(args.label)
        body = (
            f"Automated `{args.label}` run from theplant/slackwiki.\n\n"
            "Review the changes and merge if they look right.\n"
        )
        run(
            "gh", "pr", "create",
            "--title", title,
            "--body", body,
            "--base", "main",
            "--head", branch,
        )
        return 0

    # commit mode: rebase on remote head, then push.
    # If autostash hits conflicts (concurrent writer raced us), abort cleanly
    # and exit non-zero — do NOT try to commit a half-merged tree.
    pull = run("git", "pull", "--rebase", "--autostash", "origin", "HEAD", check=False)
    if pull.returncode != 0:
        # Abort any rebase in progress so the runner exits in a sane state
        run("git", "rebase", "--abort", check=False)
        print(
            "\n[commit_and_push] git pull --rebase failed — most likely a concurrent\n"
            "writer landed changes on main while this run was working. Concurrency\n"
            "groups in the workflow should prevent this; if you see this regularly,\n"
            "check that both daily-ingest.yml and weekly-lint.yml share the same\n"
            "concurrency.group key.\n",
            file=sys.stderr,
        )
        return 1
    run("git", "commit", "-m", commit_message(args.label))
    run("git", "push")
    return 0


if __name__ == "__main__":
    sys.exit(main())
