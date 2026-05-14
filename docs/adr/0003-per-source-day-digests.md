# Per-source-day digests, `msg-HHMM` anchors

Source digests are keyed by **source day**, not by ingest batch. Each ingest run writes (or appends to) one `wiki/sources/YYYY-MM-DD-slack.md` per source day its raw files cover. A bootstrap run that pulls seven days writes seven digests; a steady-state run that touches today plus a thread reply on a five-day-old parent writes two. Inside each digest, rendered messages anchor as `<a id="msg-HHMM"></a>`, which is unique because the digest is single-day.

Two alternatives were rejected. *Keep per-batch digests and switch to `msg-YYYYMMDD-HHMM` anchors* fixes anchor collisions but leaves the digest filename misleading ("Batch B labelled 2026-05-11 actually covers 2026-05-06 to 2026-05-11"), and makes every citation URL noisier forever. *Status quo with `-slack-b`, `-slack-c` suffixes* silently collides anchors when two messages share a wall-clock minute across days within one batch, and forces readers to mentally translate filename-date to content-date.

Legacy artifacts in `theplant-wiki` from before this rule landed (`2026-05-11-slack-b.md` through `-slack-e.md`, plus citations pointing at them) are deliberately not migrated. The files keep working as link targets; new ingests use the per-source-day scheme alongside them. Eventually they age out of the active wiki via the dormancy rule (ADR 0002) — they're sources of historical record, not living context.

Consequence: ingest runs may write more digest files but each one is internally consistent. Anchor collisions are eliminated by construction. The `wiki/log.md` line stays per-batch (`## [YYYY-MM-DD] ingest | slack | ...`) — log records *runs*, sources record *content*.
