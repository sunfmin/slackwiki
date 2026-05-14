# Dual-path threshold evaluation

Page-creation thresholds in the schema (e.g. "≥ 3 distinct mentions" for projects) are evaluated against two different counts depending on which workflow is running. **Ingest** counts *Distinct mentions* — Slack threads in the current `state/new_files.txt` batch. **Lint** counts *Wiki page mentions* — existing wiki pages that contain a wikilink to the entity. Neither path keeps a persistent across-batch counter.

The alternative was a single persistent counter file in `state/` (e.g. `state/entity_counts.json`) read and written every run. We rejected it because (a) it is a second source of truth that can desynchronise with the wiki, (b) it is bookkeeping the LLM has to maintain by hand on every ingest, and (c) the lint pass already provides eventual consistency — a recurring below-threshold entity will eventually cross the wiki-page-mention threshold and get stubbed.

Consequence: a project mentioned in two threads spread across two separate weeks will not get a page from either ingest run on its own, and may not get one from lint until enough other wiki pages reference it. This is the intended behaviour — quiet entities should not bloat the wiki, and recurring ones surface through cross-references rather than counters.
