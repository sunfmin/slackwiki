---
type: overview
---

# Overview

This wiki is built and maintained by Claude Code from this team's Slack history.
See [[index]] for the full catalog of pages.

## How it works

- New Slack messages are pulled daily into `raw/slack/<channel>/YYYY-MM-DD.md` (immutable).
- Claude reads new raw files and writes / updates pages under `wiki/`.
- Every claim cites its source message; the raw layer is never modified.

## How to read this wiki

- [[index]] — catalog of all pages
- [[log]] — chronological history of ingests and lint passes
- `wiki/people/` — one page per person seen in Slack
- `wiki/channels/` — one page per channel
- `wiki/projects/` — projects identified from discussion
- `wiki/topics/` — recurring concepts
- `wiki/decisions/` — decisions made in Slack
- `wiki/sources/` — daily ingest digests (raw → wiki bridges)
