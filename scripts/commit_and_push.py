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
            # Same reasoning as in commit_and_push_via_claude: --allowedTools
            # breaks arg parsing. Prompt-level guardrail is "Do NOT run any
            # bash commands. Do NOT run git commands. Do NOT commit."
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


def _git_head() -> str:
    r = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    return r.stdout.strip()


def _git_upstream() -> str:
    r = subprocess.run(
        ["git", "rev-parse", "@{u}"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    return r.stdout.strip()


def _strip_code_fences(msg: str) -> str:
    """Remove a wrapping ``` … ``` block from Claude output. Idempotent."""
    lines = msg.splitlines()
    while lines and lines[0].strip().startswith("```"):
        lines.pop(0)
    while lines and lines[-1].strip().startswith("```"):
        lines.pop()
    return "\n".join(lines).strip()


def commit_via_claude(label: str) -> bool:
    """Have Claude write the commit message and run `git commit`. Returns True
    on success (HEAD moved), False if Claude didn't commit. Push is handled
    by Python afterwards — claude-settings.json does NOT allow git push.
    """
    head_before = _git_head()
    today = date.today().isoformat()

    prompt = (
        f"You're finalising a slackwiki `{label}` run on {today}. The repo has "
        f"staged changes ready to commit. Your job: write a good commit message "
        f"for them, then run `git commit`. Python will run `git push` after you "
        f"return; you must NOT push.\n\n"
        f"Steps:\n"
        f"1. Run `git diff --cached --stat` to see what changed.\n"
        f"2. Run `git diff --cached | head -400` to skim representative content.\n"
        f"3. Compose the commit message:\n"
        f"   - Title: `{label}: {today} — <specific imperative summary>`, "
        f"no more than 72 chars. Mention concrete counts or notable named "
        f"entities (e.g. `+4 channels, +22 people, +2 incidents`, "
        f"`resolve 3 todos, add Forter vendor page`).\n"
        f"   - Body: 1-3 short paragraphs covering: counts of entities of each "
        f"kind created or updated; specific named entities; which todos got "
        f"resolved; which `⚠️ Unverified` markers were added or cleared; "
        f"anything unusual.\n"
        f"4. Commit with `git commit -m \"<title>\" -m \"<body>\"` (or repeated "
        f"`-m` for multiple body paragraphs, or `-F -` with a HEREDOC). "
        f"DO NOT wrap the body in markdown ``` code fences — the message goes "
        f"straight into git history, not into a markdown doc.\n"
        f"5. Print one final line: `DONE: <one-line summary>`.\n\n"
        f"Forbidden:\n"
        f"- `git push` (any form) — Python will push.\n"
        f"- `git reset`, `git rebase`, `git commit --amend`, `git filter-branch`, "
        f"`git reflog expire`.\n"
        f"- Modifying tracked files (the staged diff is already correct).\n"
        f"- `INGEST OK` / `LINT OK` / self-references in the commit body.\n"
    )

    print("[commit_and_push] invoking claude to write message + run git commit")
    proc = subprocess.Popen(
        [
            "claude",
            "--model", MODEL,
            "--print",
            "--verbose",
            "--output-format", "stream-json",
            "--permission-mode", "acceptEdits",
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

    head_after = _git_head()
    if head_after == head_before:
        return False
    print(f"[commit_and_push] claude committed: {head_before[:8]} -> {head_after[:8]}")
    return True


def _fallback_commit_message(label: str) -> str:
    """Plain commit message used only when the Claude commit step balks.

    Includes `git diff --cached --shortstat` for a bit of signal —
    "ingest: 2026-05-12 — 27 files, +790/-73" is at least navigable in
    `git log` versus a bare date.
    """
    today = date.today().isoformat()
    try:
        shortstat = subprocess.run(
            ["git", "diff", "--cached", "--shortstat"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
        # shortstat looks like " 27 files changed, 790 insertions(+), 73 deletions(-)"
        # condense it: "27 files, +790/-73"
        if shortstat:
            import re
            m = re.search(
                r"(\d+) files? changed(?:, (\d+) insertions?\(\+\))?(?:, (\d+) deletions?\(-\))?",
                shortstat,
            )
            if m:
                files = m.group(1)
                ins = m.group(2) or "0"
                dele = m.group(3) or "0"
                return f"{label}: {today} — {files} files, +{ins}/-{dele}"
    except subprocess.CalledProcessError:
        pass
    return f"{label}: {today}"


def _read_head_commit_message() -> str:
    """Read the commit message of HEAD."""
    r = subprocess.run(
        ["git", "log", "-1", "--format=%B"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    return r.stdout.strip()


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

        # Same split as commit mode: Claude runs git commit (with a real
        # message); Python runs git push and gh pr create. If Claude doesn't
        # commit, fall back to the diff-stat-enriched fallback message.
        if not commit_via_claude(args.label):
            run("git", "commit", "-m", _fallback_commit_message(args.label))

        # Read the message back from git so PR title + body match the commit.
        msg = _read_head_commit_message()
        lines = msg.splitlines()
        pr_title = lines[0] if lines else f"{args.label}: {date.today().isoformat()}"
        pr_body = "\n".join(lines[2:]).strip() if len(lines) > 2 else (
            f"Automated `{args.label}` run from theplant/slackwiki. "
            "Review the changes and merge if they look right."
        )

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
    # Claude writes the commit message and runs git commit (allowed by
    # claude-settings.json's Bash(git commit:*) rule). git push is NOT
    # allowed for Claude — Python handles push so it can react to push
    # failures and so push is always mechanical (no LLM judgment needed).
    if not commit_via_claude(args.label):
        print(
            "[commit_and_push] claude did not commit; falling back to a plain commit",
            file=sys.stderr,
        )
        run("git", "commit", "-m", _fallback_commit_message(args.label))

    # Python pushes. If the push fails (e.g. concurrent writer landed
    # between our pull and our push despite the concurrency group),
    # surface a non-zero exit so the workflow run is marked failed.
    push = run("git", "push", check=False)
    if push.returncode != 0:
        print(
            "[commit_and_push] git push failed; commit is local only, next "
            "run will pick up the cursor + try again",
            file=sys.stderr,
        )
        return push.returncode

    head_after = _git_head()
    upstream = _git_upstream()
    if head_after != upstream:
        print(
            f"[commit_and_push] post-push HEAD ({head_after[:8]}) != upstream "
            f"({upstream[:8]}); something odd happened",
            file=sys.stderr,
        )
        return 1
    print(f"[commit_and_push] ok: HEAD @ {head_after[:8]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
