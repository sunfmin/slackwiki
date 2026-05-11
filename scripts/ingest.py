"""Run Claude Code to ingest state/new_files.txt into wiki/.

Skips the Claude run entirely when there are no new files (cheap no-op
on quiet days).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import format_claude_stream  # noqa: E402


REPO_ROOT = Path(os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
NEW_FILES = REPO_ROOT / "state" / "new_files.txt"


PROMPT = """Read every file listed in `state/new_files.txt` (only those — do not scan the rest of the repo).
Then follow the "Ingest workflow" in CLAUDE.md exactly:

0. **Pre-pass: resolve open items from prior lint passes.**
   (a) Scan all wiki pages for `⚠️ Unverified as of <date>` markers. For each,
       check the new raw files for a message that resolves the claim. If yes,
       remove the marker and add a confirming `## YYYY-MM-DD` section with a
       source citation. If no, leave it.
   (b) For each `- [ ]` item under `## Open` in `wiki/todos.md`, check the new
       raw files for a closing message. If yes, change to `- [x]`, strike it
       through, append `(resolved YYYY-MM-DD in [[sources/YYYY-MM-DD-slack]])`,
       and move it under `## Resolved`. If no, leave it.

1. Extract entities from each raw file. The full list and detection rules are in
   CLAUDE.md "Entity detection rules". Cover all of: people, projects, decisions,
   **incidents** (impact language), **services / repos**, **vendors / external SaaS**,
   **tickets** (ID patterns like KGM-123, MWMOP-456), **campaigns**, **release events**
   (build / deploy), **acronyms** (track counts, do NOT add to glossary — lint does
   that), **infrastructure changes**, **Q&A pairs from threads**, plus open questions
   and external links.
2. Create or append to pages under wiki/people, wiki/channels, wiki/projects,
   wiki/topics, wiki/decisions, **wiki/incidents, wiki/services, wiki/vendors,
   wiki/tickets, wiki/campaigns**. Apply the thresholds from the page-types
   table — below-threshold entities are not paged this run. Append-only: never
   overwrite existing dated sections.
   - Append a line to **wiki/releases/YYYY-MM.md** for every release event (build
     #s, deploys). Create the month file if missing.
   - Append to **wiki/infrastructure.md** for infra changes.
   - Append to **wiki/faq.md** for clear Q&A pairs from threads.
3. **Auto-link ticket IDs**: in every page you write or update, wrap bare
   `[A-Z]{2,}-[0-9]+` matches as `[[tickets/<ID>]]`. Broken wiki-links are fine;
   the next lint will stub tickets that pass the threshold.
4. Write `wiki/sources/YYYY-MM-DD-slack.md` digesting this ingest batch
   (channels touched, message counts, key events, new entities created across
   all categories, plus what got resolved in step 0).
5. Update `wiki/index.md` with links to any newly created pages, under the
   correct category (add new sections for any category that didn't exist yet).
6. Append one line to `wiki/log.md`:
   `## [YYYY-MM-DD] ingest | slack | N channels, M messages, +X people, +Y projects, +Z decisions, +A incidents, +B services, +C vendors, +D tickets, -K resolved`
7. Never modify anything under `raw/`.

All wiki content must be in English (paraphrase non-English source messages
into English and keep the original in a `> quote` block).

When done, print one final line: `INGEST OK: <one-sentence summary>`.
"""


def main() -> int:
    if not NEW_FILES.exists() or not NEW_FILES.read_text().strip():
        print("no new files to ingest; skipping Claude run")
        return 0

    print("running: claude --print --verbose --output-format stream-json …", flush=True)
    proc = subprocess.Popen(
        [
            "claude",
            "--print",
            "--verbose",
            "--output-format", "stream-json",
            "--permission-mode", "acceptEdits",
            PROMPT,
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
