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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import format_claude_stream  # noqa: E402


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
   format in CLAUDE.md, synthesizing content from existing references — never
   leave a stub empty):
   - **Topics**: concepts referenced in ≥ 5 distinct wiki pages
   - **People**: `@handle`s referenced in ≥ 3 distinct pages without a people page
   - **Services**: internal repos / services referenced in ≥ 3 distinct pages
   - **Vendors**: external SaaS referenced in ≥ 2 distinct pages
   - **Tickets**: ticket IDs auto-linked by ingest, referenced in ≥ 3 distinct dated mentions
   - **Incidents**: when impact language references a past event with no incident page
   - **Campaigns**: named campaigns referenced in ≥ 3 distinct pages
   - **Teams**: when ≥ 3 people consistently co-appear in the same channel + project
     (derive team membership from `channels:` and project participation)

3. **Inject `⚠️ Unverified as of {today}` markers** above each stale claim
   (claims dated more than 5 days ago without a confirming follow-up). Format:
   `> ⚠️ Unverified as of {today}. <one-line description>.`

4. **Update `wiki/todos.md`** by appending residual items requiring authorial
   judgment to `## Open`, format:
   `- [ ] {today} — **<action>**. <context with [[wiki-links]]>`
   Create the file if missing. Never modify existing `## Resolved` items.

5. **Update `wiki/glossary.md`.** Scan every wiki page for uppercase tokens
   `[A-Z]{{3,}}`. For each token in ≥ 5 distinct pages and not yet in the
   glossary, add an alphabetical entry: a one-line synthesized definition plus
   a `[[wiki-link]]` to the canonical page if one exists. Skip generic English
   in caps (API, URL, HTTP, etc.) unless they're project-specific.

6. **Roll up open action items into people pages.** For each `## Open` item in
   `wiki/todos.md` containing `[[people/X]]`, mirror that line into the matching
   `wiki/people/X.md` under a section named `## Open action items (from [[todos]])`.
   REPLACE that whole section on every lint — do not append. If a person has no
   open items, remove the section entirely.

7. **Cross-link decisions ↔ incidents.** For each decision page that references
   an incident page (body or "See also"), add `triggered_by: <incident-slug>` to
   the decision's frontmatter (skip if already present).

8. **Write the lint report** at `wiki/lint/{today}.md` with one section per
   step above documenting exactly what was changed / created / injected / queued /
   glossed / rolled-up / cross-linked. End with a "Residual items" section
   pointing to `wiki/todos.md`.

9. **Update `wiki/index.md`** for any new pages (add new category sections
   if needed).

10. **Append one line to `wiki/log.md`**:
    `## [{today}] lint | <N fixes>, <M stubs>, <P markers>, <Q new todos>, <R gloss>, <S rollups>`

When done, print one final line: `LINT OK: <one-sentence summary>`.
"""


def main() -> int:
    today = date.today().isoformat()
    prompt = PROMPT_TEMPLATE.format(today=today)

    print("running: claude --print --verbose --output-format stream-json (lint+fix) …", flush=True)
    proc = subprocess.Popen(
        [
            "claude",
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
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
