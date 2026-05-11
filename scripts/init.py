"""Bootstrap or refresh a downstream slackwiki repo.

Two usages:

1. Run by the Action on every invocation (without --full) to keep CLAUDE.md and
   .claude/settings.json in sync with the latest schema shipped by the Action.

2. Run by a human once to bootstrap a brand-new <company>-wiki repo
   (with --full); creates slackwiki.config.yml, .gitignore, workflow files, and
   seed wiki pages — but only when those files don't already exist, so it is
   safe to re-run.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


ACTION_PATH = Path(__file__).resolve().parent.parent
TEMPLATES = ACTION_PATH / "templates"
REPO_ROOT = Path(os.environ.get("GITHUB_WORKSPACE") or ".").resolve()


REFRESH_ALWAYS = [
    ("CLAUDE.md", "CLAUDE.md"),
    ("claude-settings.json", ".claude/settings.json"),
]

COPY_IF_MISSING = [
    ("slackwiki.config.yml", "slackwiki.config.yml"),
    ("gitignore", ".gitignore"),
    ("daily-ingest.yml", ".github/workflows/daily-ingest.yml"),
    ("weekly-lint.yml", ".github/workflows/weekly-lint.yml"),
]


def copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def refresh_schema() -> None:
    for src_name, dst_rel in REFRESH_ALWAYS:
        src = TEMPLATES / src_name
        if not src.exists():
            print(f"WARN: template missing: {src}", file=sys.stderr)
            continue
        dst = REPO_ROOT / dst_rel
        copy(src, dst)
        print(f"refreshed {dst_rel}")


def copy_seeds() -> None:
    for src_name, dst_rel in COPY_IF_MISSING:
        src = TEMPLATES / src_name
        dst = REPO_ROOT / dst_rel
        if dst.exists():
            print(f"skip (exists): {dst_rel}")
            continue
        if not src.exists():
            print(f"WARN: template missing: {src}", file=sys.stderr)
            continue
        copy(src, dst)
        print(f"created {dst_rel}")

    seed_dir = TEMPLATES / "wiki-seed"
    if seed_dir.exists():
        wiki_dir = REPO_ROOT / "wiki"
        for src in seed_dir.iterdir():
            dst = wiki_dir / src.name
            if dst.exists():
                print(f"skip (exists): wiki/{src.name}")
                continue
            wiki_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            print(f"created wiki/{src.name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full",
        action="store_true",
        help="also create slackwiki.config.yml, workflows, .gitignore, "
             "and seed wiki pages if missing",
    )
    args = parser.parse_args()

    refresh_schema()
    if args.full:
        copy_seeds()
    return 0


if __name__ == "__main__":
    sys.exit(main())
