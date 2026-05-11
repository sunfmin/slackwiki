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


sys.path.insert(0, str(Path(__file__).resolve().parent))
import format_claude_stream  # noqa: E402

REPO_ROOT = Path(os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-7")
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

# Cap the diff sent to Claude for commit-message generation. Large ingests
# can produce 100k+ char diffs; we don't need all of it for a good message.
DIFF_PROMPT_CHAR_LIMIT = 12_000
# Bound Claude commit-message generation latency.
CLAUDE_COMMIT_MSG_TIMEOUT_SEC = 240


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


def _unmerged_paths() -> list[str]:
    """Return paths currently in unmerged (conflict) state."""
    r = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=U"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    return [p for p in r.stdout.splitlines() if p.strip()]


def resolve_conflicts_with_claude() -> bool:
    """Ask Claude to resolve the current set of merge-conflicted files.

    Restricts Claude to Read/Edit/Write only (no Bash, no git commands).
    After Claude finishes, this function verifies no conflict markers remain,
    then `git add`s the resolved files and drops the autostash entry.
    Returns True on success, False if conflicts remain.
    """
    files = _unmerged_paths()
    if not files:
        return True

    file_list = "\n".join(f"  - `{f}`" for f in files)
    prompt = (
        "You are resolving a `git pull --rebase --autostash` conflict in a "
        "slackwiki repo. Two concurrent runs (ingest + lint, or two ingests) "
        "both edited the same wiki files and their changes were not "
        "auto-mergeable. The wiki is the karpathy LLM-wiki pattern instantiated "
        "for Slack — almost every page is append-only, so the right resolution "
        "is usually to KEEP BOTH SIDES' contributions.\n\n"
        "Conflicted files:\n"
        f"{file_list}\n\n"
        "For each file:\n"
        "  1. Read it. It contains `<<<<<<< / ======= / >>>>>>>` conflict markers.\n"
        "  2. Understand each side's intent. Both sides are valid wiki edits.\n"
        "  3. Write the file back with a merged version: ALL conflict markers "
        "removed, content from both sides preserved.\n\n"
        "Type-specific merge rules:\n"
        "- `wiki/index.md` — keep every newly added link from both sides, "
        "deduped, under the correct category section. Preserve alphabetical / "
        "chronological order where the section already had one.\n"
        "- `wiki/log.md` — both sides each appended one `## [YYYY-MM-DD] ...` "
        "line. Keep BOTH lines, in chronological order.\n"
        "- `wiki/todos.md` — combine the `## Open` lists (union, dedupe). "
        "Combine the `## Resolved` lists (union). Never delete an item.\n"
        "- People / project / topic / channel pages — each side typically added "
        "a `## YYYY-MM-DD` dated section. Keep ALL of them in chronological "
        "order. If the same date has both sides' content, merge by combining "
        "non-duplicate bullets / sentences.\n"
        "- Frontmatter list fields (`channels`, `related`, `participants`, "
        "`aliases`) — union; no duplicates.\n"
        "- Single-file pages (`glossary.md`, `infrastructure.md`, `faq.md`) — "
        "merge entries; never delete.\n\n"
        "Do NOT run any bash commands. Do NOT run git commands. Do NOT commit. "
        "Only Read and Edit / Write to fix the files. After every conflict "
        "marker is gone from every file, print one final line: "
        "`RESOLVED: <one-line summary of what you merged>`."
    )

    print("[commit_and_push] invoking claude to resolve conflicts in:")
    for f in files:
        print(f"    {f}")

    proc = subprocess.Popen(
        [
            "claude",
            "--model", MODEL,
            "--print",
            "--verbose",
            "--output-format", "stream-json",
            "--permission-mode", "acceptEdits",
            "--allowedTools", "Read Edit Write",
            prompt,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=REPO_ROOT,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        format_claude_stream.format_line(line)
    proc.wait()

    if proc.returncode != 0:
        print(
            f"[commit_and_push] claude exited {proc.returncode} during conflict resolution",
            file=sys.stderr,
        )
        return False

    # Verify all conflict markers are gone.
    still_unmerged = _unmerged_paths()
    if still_unmerged:
        # Git still thinks these are unmerged because we haven't `git add`-ed yet.
        # But also check for raw conflict markers — Claude might have written valid
        # files but missed a marker somewhere.
        for path in files:
            full = (REPO_ROOT / path).read_text(errors="replace")
            if "<<<<<<<" in full or "=======" in full or ">>>>>>>" in full:
                print(
                    f"[commit_and_push] conflict markers still present in {path}",
                    file=sys.stderr,
                )
                return False

    # Stage the resolved files.
    run("git", "add", "--", *files)

    # Drop the autostash entry; it was preserved by `git stash pop` failure.
    # If there's no stash, this is harmless.
    subprocess.run(["git", "stash", "drop"], cwd=REPO_ROOT, check=False)
    print("[commit_and_push] conflicts resolved by claude; staged and stash dropped")
    return True


def _fallback_commit_message(label: str) -> str:
    return f"{label}: {date.today().isoformat()}"


def commit_message(label: str) -> str:
    """Ask Claude to write a commit message describing the currently-staged diff.

    Falls back to `<label>: <date>` if anything goes wrong (Claude unavailable,
    timeout, non-zero exit, malformed output). The fallback is intentionally
    silent so a transient Claude error never blocks a commit.
    """
    try:
        stat = subprocess.run(
            ["git", "diff", "--cached", "--stat"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
        full = subprocess.run(
            ["git", "diff", "--cached"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        ).stdout
    except subprocess.CalledProcessError:
        return _fallback_commit_message(label)

    excerpt = full[:DIFF_PROMPT_CHAR_LIMIT]
    if len(full) > DIFF_PROMPT_CHAR_LIMIT:
        excerpt += f"\n\n... [truncated; full diff is {len(full):,} chars]"

    prompt = (
        f"You just finished a slackwiki `{label}` run on {date.today().isoformat()}.\n"
        f"Below is `git diff --cached` for the changes you are about to commit.\n"
        f"Write the commit message that should accompany them.\n\n"
        "Format strictly:\n"
        f"- Line 1: `{label}: {date.today().isoformat()} — <specific imperative summary>`, "
        "no more than 72 chars total. The summary mentions concrete counts or "
        "notable named entities (e.g. `+4 channels, +22 people, +2 incidents`, "
        "`resolve 3 todos, add Forter vendor page`).\n"
        "- Line 2: blank.\n"
        "- Following lines: 1–3 short paragraphs of body. Cover: how many "
        "entities of each kind were created or updated, which notable named "
        "entities appeared, which todos were resolved, which unverified markers "
        "were added or cleared, anything unusual. Be concrete and specific to "
        "this diff; do not write generic boilerplate.\n"
        "- Do NOT include `INGEST OK` / `LINT OK` or any meta-commentary. "
        "Do NOT reference yourself, the LLM, or this prompt. "
        "Output ONLY the commit message itself, nothing before or after.\n\n"
        "## Diff stat\n"
        f"```\n{stat}\n```\n\n"
        "## Diff (may be truncated)\n"
        f"```diff\n{excerpt}\n```\n"
    )

    try:
        result = subprocess.run(
            ["claude", "--model", MODEL, "--print", prompt],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=CLAUDE_COMMIT_MSG_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        print(
            "[commit_and_push] claude commit-message timed out, using fallback",
            file=sys.stderr,
        )
        return _fallback_commit_message(label)

    if result.returncode != 0:
        print(
            f"[commit_and_push] claude returned {result.returncode}, using fallback",
            file=sys.stderr,
        )
        return _fallback_commit_message(label)

    msg = result.stdout.strip()
    lines = msg.splitlines()
    if not lines or len(lines[0]) > 100:
        print(
            "[commit_and_push] claude commit message looks malformed, using fallback",
            file=sys.stderr,
        )
        return _fallback_commit_message(label)
    print(f"[commit_and_push] claude wrote commit message ({len(msg)} chars)")
    return msg


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
        # Generate the message ONCE (the Claude call is non-deterministic + costs tokens);
        # use the first line as the PR title and the rest as the PR body.
        msg = commit_message(args.label)
        lines = msg.splitlines()
        pr_title = lines[0]
        pr_body = "\n".join(lines[2:]).strip() if len(lines) > 2 else (
            f"Automated `{args.label}` run from theplant/slackwiki. "
            "Review the changes and merge if they look right."
        )
        run("git", "commit", "-m", msg)
        run("git", "push", "-u", "origin", branch)
        run(
            "gh", "pr", "create",
            "--title", pr_title,
            "--body", pr_body,
            "--base", "main",
            "--head", branch,
        )
        return 0

    # commit mode: rebase on remote head, then push.
    # If autostash conflicts (concurrent writer raced us through the concurrency
    # group somehow, or someone pushed manually), invoke Claude to merge the
    # conflicted files. Concurrency groups should make this rare, but it's the
    # only sound recovery: bailing here loses the run's work permanently.
    pull = run("git", "pull", "--rebase", "--autostash", "origin", "HEAD", check=False)
    if pull.returncode != 0:
        if _unmerged_paths():
            if not resolve_conflicts_with_claude():
                print(
                    "[commit_and_push] claude could not fully resolve conflicts; "
                    "aborting so the next run can retry from origin",
                    file=sys.stderr,
                )
                run("git", "rebase", "--abort", check=False)
                return 1
        else:
            # Non-conflict rebase failure (e.g. network). Abort cleanly.
            run("git", "rebase", "--abort", check=False)
            print(
                "[commit_and_push] git pull --rebase failed without conflicts; aborting",
                file=sys.stderr,
            )
            return 1
    run("git", "commit", "-m", commit_message(args.label))
    run("git", "push")
    return 0


if __name__ == "__main__":
    sys.exit(main())
