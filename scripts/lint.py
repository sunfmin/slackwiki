"""Run Claude Code in lint mode: diagnose AND fix.

The lint run does five things in one pass:
  1. Apply mechanical fixes to existing pages (wikilink case, symmetric related,
     quote-block wrapping for non-English, decision back-links).
  2. Auto-create stub pages for missing-but-warranted topics and people.
  3. Inject `⚠️ Unverified as of <date>` markers above stale claims.
  4. Append residual items to wiki/todos.md.
  5. Write a report at wiki/lint/<date>.md.

The resulting PR is one reviewable changeset containing diagnosis + fixes.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import date
from pathlib import Path


REPO_ROOT = Path(os.environ.get("GITHUB_WORKSPACE") or ".").resolve()


PROMPT_TEMPLATE = """Run the Lint workflow defined in CLAUDE.md. This is a
combined diagnose-and-fix pass — apply edits, do not just describe them.
Scope: every file under `wiki/`. Never touch anything under `raw/`.

Do all of the following in one run, in this order:

1. **Apply mechanical fixes** to existing wiki pages:
   - Wikilink case: `[[Kate]]` → `[[kate]]` where the target file is lowercase kebab-case.
   - Symmetric `related:` frontmatter.
   - Wrap bare non-English inline terms in `> quote` blocks per the language policy.
   - Add `See also:` lines to decision pages back-linking participants and the related project; add "Key decisions" sub-sections to project pages.

2. **Create stub pages** for missing-but-warranted entities (per the stub
   format in CLAUDE.md, synthesizing content from existing references):
   - Topic pages for concepts referenced in ≥ 5 distinct wiki pages.
   - People pages for `@handle`s referenced in ≥ 3 distinct wiki pages but lacking their own page.

3. **Inject `⚠️ Unverified as of {today}` markers** above each stale claim
   (claims dated more than 5 days ago without a confirming follow-up). Format:
   `> ⚠️ Unverified as of {today}. <one-line description>.`
   The next ingest pass will auto-resolve these when new Slack messages confirm them.

4. **Update `wiki/todos.md`** by appending residual items requiring authorial
   judgment to `## Open`, format:
   `- [ ] {today} — **<action>**. <context with [[wiki-links]]>`
   Create the file if missing (see CLAUDE.md page-types table and seed format).
   Never modify existing `## Resolved` items.

5. **Write the lint report** at `wiki/lint/{today}.md` with one section per
   step above documenting exactly what was changed / created / injected / queued.
   End with a "Residual items" section pointing to `wiki/todos.md`.

6. **Update `wiki/index.md`** for any new pages.

7. **Append one line to `wiki/log.md`**:
   `## [{today}] lint | <N fixes>, <M stubs>, <P markers>, <Q new todos>`

When done, print one final line: `LINT OK: <one-sentence summary>`.
"""


def main() -> int:
    today = date.today().isoformat()
    prompt = PROMPT_TEMPLATE.format(today=today)

    print("running: claude --print --permission-mode acceptEdits (lint+fix) …", flush=True)
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
