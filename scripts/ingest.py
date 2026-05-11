"""Run Claude Code to ingest state/new_files.txt into wiki/.

Skips the Claude run entirely when there are no new files (cheap no-op
on quiet days).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
NEW_FILES = REPO_ROOT / "state" / "new_files.txt"


PROMPT = """Read every file listed in `state/new_files.txt` (only those — do not scan the rest of the repo).
Then follow the "Ingest workflow" in CLAUDE.md exactly:

1. Extract people, projects, decisions, open questions, and links from each raw file.
2. Create or append to pages under wiki/people, wiki/channels, wiki/projects,
   wiki/topics, wiki/decisions. Append-only: never overwrite existing sections;
   add a new `## YYYY-MM-DD` section with today's findings.
3. Write `wiki/sources/YYYY-MM-DD-slack.md` digesting this ingest batch
   (channels touched, message counts, key events, new entities created).
4. Update `wiki/index.md` with links to any newly created pages.
5. Append one line to `wiki/log.md`:
   `## [YYYY-MM-DD] ingest | slack | N channels, M messages, +X people, +Y projects`
6. Never modify anything under `raw/`.

All wiki content must be in English (paraphrase non-English source messages
into English and keep the original in a `> quote` block).

When done, print one final line: `INGEST OK: <one-sentence summary>`.
"""


def main() -> int:
    if not NEW_FILES.exists() or not NEW_FILES.read_text().strip():
        print("no new files to ingest; skipping Claude run")
        return 0

    print("running: claude --print --permission-mode acceptEdits …", flush=True)
    result = subprocess.run(
        [
            "claude",
            "--print",
            "--permission-mode", "acceptEdits",
            PROMPT,
        ],
        cwd=REPO_ROOT,
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
