# SlackWiki

A reusable GitHub Action that turns a team's Slack history into a Claude-maintained markdown wiki. This document is the glossary of terms used in the schema (`templates/CLAUDE.md`), the action scripts, and downstream data repos.

## Language

**Action repo**:
This repository (`theplant/slackwiki`) — the reusable composite Action, the Python scripts it calls, and the schema templates.
_Avoid_: "tool repo", "main repo".

**Data repo**:
A per-company private repository (e.g. `theplant-wiki`) that consumes the Action and holds `raw/`, `wiki/`, and `state/`.
_Avoid_: "downstream repo", "<company>-wiki repo", "consumer repo".

**Schema**:
The instructional document that tells Claude how to organise the wiki. Lives at `templates/CLAUDE.md` in the Action repo and is copied into every data repo on every run.
_Avoid_: "prompt". `CLAUDE.md` is the file; **schema** is the concept.

**Raw file**:
An immutable markdown rendering of one channel's Slack messages for one calendar day, at `raw/slack/<channel>/YYYY-MM-DD.md`. Day boundaries are in the configured timezone.

**Ingest batch**:
The set of raw files (paths listed in `state/new_files.txt`) that one ingest run consumes.

**Digest page**:
A summary of all activity on one **source day** at `wiki/sources/YYYY-MM-DD-slack.md`. One file per source day, not per ingest run — a batch that touches three source days writes (or appends to) three digests. Wiki pages cite this page (not raw files directly) via `#msg-HHMM` anchors, which are unique inside one source-day. Legacy `-slack-b`, `-slack-c` suffixed files from before 2026-05-14 are frozen and remain as-is.

**Distinct mention** (ingest-time):
One Slack thread (parent + replies, treated as one unit) inside the current **Ingest batch** that contains the entity. Five posts by one author in a single thread = 1 distinct mention. Two separate threads on the same day = 2 distinct mentions.
_Avoid_: "distinct message", "distinct day".

**Distinct dated mention** (tickets only, ingest-time):
A **Distinct mention** that lands on a distinct calendar day. Three threads in one morning = 1 distinct dated mention.

**Wiki page mention** (lint-time):
One existing wiki page (any type) that contains a wikilink to the entity. Counts pages, not threads.

**Last seen**:
Frontmatter field `last_seen: YYYY-MM-DD` on every **Portrait** whose entity has a temporal trail (people, channels, projects, topics, services, vendors, tickets, campaigns, teams). Updated by ingest on every run that touches the entity, so the portrait reflects daily activity.

**Active / Dormant**:
The two values of `status` driven by the lifecycle rule. A portrait is **Dormant** when `last_seen` is older than its page-type window. Both directions of the flip are performed by ingest — the `dormant → active` flip when an entity is touched again, and the `active → dormant` flip when ingest notices, while updating maintenance fields, that `last_seen` is past the window. Lint mirrors the resulting `status` into `index.md` (moving the entry between the category section and the `## Dormant` section) but does not change `status` itself. See ADR 0002.

**Internal name**:
A name belonging to theplant — its people, projects, services, vendors theplant integrates with, or any term with an established team-wide English form (`Kakuyasu`, `JMA`, `Veritrans`). Used verbatim in wiki prose, per Language Policy 2.

**Portrait**:
The single canonical page for a recurring entity (person, channel, project, topic, service, vendor, campaign, team) at `wiki/<type>/<slug>.md`. Contains frontmatter, an **Identity zone**, the **Monthly chronicle**, the open-action-items rollup section, and a "Recent activity" link list pointing at the latest log files. Wikilinks like `[[people/dorothy]]` always resolve to a portrait. **Ingest owns nearly all portrait writes** — on each run that touches an entity, ingest updates maintenance fields (`last_seen`, `dormant → active` flips, recent-activity list), writes any missing **Monthly summary** entries from existing log files, refreshes the identity zone when a new summary lands, and performs the one-shot organic migration on legacy single-file pages. **Lint writes two specific things on portraits and nothing else**: (a) the `## Open action items (from [[todos]])` section, replaced in full each lint pass from `todos.md`; (b) the `status: dormant` frontmatter flag (the `active → dormant` direction only). See ADR 0005.

**Activity log** (folder) / **Log file** (one month):
The append-only history for one entity, stored as monthly markdown files under `wiki/logs/<type>/<slug>/<YYYY-MM>.md`. Ingest-owned. Each file holds the dated sections (`## YYYY-MM-DD`) for that entity in that calendar month. Empty months get no file — absence is signal.

**Monthly summary**:
A single paragraph in the portrait's **Monthly chronicle** synthesising one calendar month of activity from the log file for that month. Written once on the first lint run of the following month and **frozen** thereafter — never rewritten. The growing list of monthly summaries gives the portrait memory of every month.

**Identity zone**:
The rolling-synthesis top half of the portrait — role, areas, collaborators, recurring patterns. Derived by lint from the most-recent 3–6 monthly summaries (not from raw logs). Rewritten whenever a new monthly summary is added; otherwise left alone.

**Monthly chronicle**:
The portrait section that holds frozen **Monthly summary** entries, newest first. Grows by one paragraph per active month.

**History substrate**:
The append-only set of **Log files** under `wiki/logs/`, plus decision pages, incident pages, release pages, source digests, and lint reports. Nothing here is ever pruned or rewritten. (Log files may eventually roll off into `wiki/logs/<type>/<slug>/archive/` after a long retention window, but the monthly summaries on the portrait preserve readable history regardless.)

**View layer**:
The current-state outputs computed by lint over the history substrate: every **Portrait** (identity zone + monthly chronicle), `index.md` with its active vs dormant split, `todos.md`, the per-person open-action-items rollup, `glossary.md`, and the dormant frontmatter flags. Portraits are written by lint; the monthly chronicle section grows monotonically (frozen entries), the identity zone is rewritten when a new month lands.

## Relationships

- An **Ingest batch** writes: one **Digest page** per source day touched, appended dated sections to the corresponding **Log files**, and full updates to each touched **Portrait** (maintenance + any missing monthly summaries + identity zone refresh when a new summary lands + migration if the entity is still in legacy single-file form). Both `active → dormant` and `dormant → active` flips happen in ingest.
- Lint never writes portrait bodies. Lint touches: `index.md` (move entries between category sections and `## Dormant` to reflect each portrait's current `status`), `todos.md`, `glossary.md`, lint reports, and mechanical fixes on non-portrait pages.
- A **Distinct mention** is counted within a single **Ingest batch**; it does not accumulate across batches.
- A **Wiki page mention** is counted across the whole wiki at lint time.
- Page-creation thresholds have **two evaluation paths**: ingest uses distinct mentions inside this batch, lint uses wiki page mentions across the wiki. See ADR 0001.
- On the first ingest of each calendar month that touches an active entity, ingest writes that entity's **Monthly summary** for the previous month — read the prev-month **Log file**, paraphrase to one paragraph, freeze it at the top of the **Monthly chronicle**, and refresh the **Identity zone** from the recent monthly summaries. See ADR 0005.

## Example dialogue

> **Reader:** "The schema says a project gets a page after ≥3 distinct mentions. @alice posted about `payments-v2` five times in one thread on Tuesday — does that trigger a page?"
> **Maintainer:** "No. That's one **Distinct mention** — one thread. We need three different threads."
> **Reader:** "What if she mentioned it in three separate threads, but all on Tuesday?"
> **Maintainer:** "That's three distinct mentions, so yes — ingest creates the page. The 'distinct dated' rule only applies to tickets, where we additionally require three different calendar days, to stop a hot ticket ID from getting a page off one morning's storm."
> **Reader:** "And if the project was discussed weeks ago and the ingest only sees today's raw file?"
> **Maintainer:** "Ingest won't see the historical mentions — it only reads `state/new_files.txt`. But lint will, because at lint time we count **Wiki page mentions** (existing pages that wikilink to the entity), not raw threads."

## Flagged ambiguities

- "Distinct mention" was undefined in the original schema; resolved to **one Slack thread at ingest time, one existing wiki page at lint time**. See ADR 0001.
- "Downstream repo" / "<company>-wiki" / "data repo" all named the same thing; canonical is **Data repo**.
- `CLAUDE.md` is the file, **Schema** is the concept — keep them distinct in prose.
