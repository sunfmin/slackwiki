"""Run Claude Code in lint mode: review wiki/ and write a health report."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import date
from pathlib import Path


REPO_ROOT = Path(os.environ.get("GITHUB_WORKSPACE") or ".").resolve()


PROMPT_TEMPLATE = """Review the wiki under `wiki/` for health issues. Categories to check:

- Stale claims that newer sources have superseded
- Contradictions between pages
- Orphan pages with no inbound links
- Important concepts mentioned in pages but lacking their own page
- Missing cross-references between related pages
- Frontmatter that has drifted from the schema in CLAUDE.md
- Pages that violate the English-only language policy

Write a single markdown report to `wiki/lint/{today}.md` with one H2 section
per category above, plus a final `## Recommended actions` section listing
concrete fixes. If a category has no findings, write `_None._` under it.

Do not modify any wiki page during the lint run — only create the lint report.
Never touch `raw/`.

When done, print one final line: `LINT OK: <one-sentence summary>`.
"""


def main() -> int:
    today = date.today().isoformat()
    prompt = PROMPT_TEMPLATE.format(today=today)

    print("running: claude --print --permission-mode acceptEdits (lint) …", flush=True)
    result = subprocess.run(
        [
            "claude",
            "--print",
            "--permission-mode", "acceptEdits",
            prompt,
        ],
        cwd=REPO_ROOT,
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
