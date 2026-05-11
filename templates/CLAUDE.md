# LLM Wiki

A pattern for building personal knowledge bases using LLMs.

This is an idea file, it is designed to be copy pasted to your own LLM Agent (e.g. OpenAI Codex, Claude Code, OpenCode / Pi, or etc.). Its goal is to communicate the high level idea, but your agent will build out the specifics in collaboration with you.

## The core idea

Most people's experience with LLMs and documents looks like RAG: you upload a collection of files, the LLM retrieves relevant chunks at query time, and generates an answer. This works, but the LLM is rediscovering knowledge from scratch on every question. There's no accumulation. Ask a subtle question that requires synthesizing five documents, and the LLM has to find and piece together the relevant fragments every time. Nothing is built up. NotebookLM, ChatGPT file uploads, and most RAG systems work this way.

The idea here is different. Instead of just retrieving from raw documents at query time, the LLM **incrementally builds and maintains a persistent wiki** — a structured, interlinked collection of markdown files that sits between you and the raw sources. When you add a new source, the LLM doesn't just index it for later retrieval. It reads it, extracts the key information, and integrates it into the existing wiki — updating entity pages, revising topic summaries, noting where new data contradicts old claims, strengthening or challenging the evolving synthesis. The knowledge is compiled once and then *kept current*, not re-derived on every query.

This is the key difference: **the wiki is a persistent, compounding artifact.** The cross-references are already there. The contradictions have already been flagged. The synthesis already reflects everything you've read. The wiki keeps getting richer with every source you add and every question you ask.

You never (or rarely) write the wiki yourself — the LLM writes and maintains all of it. You're in charge of sourcing, exploration, and asking the right questions. The LLM does all the grunt work — the summarizing, cross-referencing, filing, and bookkeeping that makes a knowledge base actually useful over time. In practice, I have the LLM agent open on one side and Obsidian open on the other. The LLM makes edits based on our conversation, and I browse the results in real time — following links, checking the graph view, reading the updated pages. Obsidian is the IDE; the LLM is the programmer; the wiki is the codebase.

This can apply to a lot of different contexts. A few examples:

- **Personal**: tracking your own goals, health, psychology, self-improvement — filing journal entries, articles, podcast notes, and building up a structured picture of yourself over time.
- **Research**: going deep on a topic over weeks or months — reading papers, articles, reports, and incrementally building a comprehensive wiki with an evolving thesis.
- **Reading a book**: filing each chapter as you go, building out pages for characters, themes, plot threads, and how they connect. By the end you have a rich companion wiki. Think of fan wikis like [Tolkien Gateway](https://tolkiengateway.net/wiki/Main_Page) — thousands of interlinked pages covering characters, places, events, languages, built by a community of volunteers over years. You could build something like that personally as you read, with the LLM doing all the cross-referencing and maintenance.
- **Business/team**: an internal wiki maintained by LLMs, fed by Slack threads, meeting transcripts, project documents, customer calls. Possibly with humans in the loop reviewing updates. The wiki stays current because the LLM does the maintenance that no one on the team wants to do.
- **Competitive analysis, due diligence, trip planning, course notes, hobby deep-dives** — anything where you're accumulating knowledge over time and want it organized rather than scattered.

## Architecture

There are three layers:

**Raw sources** — your curated collection of source documents. Articles, papers, images, data files. These are immutable — the LLM reads from them but never modifies them. This is your source of truth.

**The wiki** — a directory of LLM-generated markdown files. Summaries, entity pages, concept pages, comparisons, an overview, a synthesis. The LLM owns this layer entirely. It creates pages, updates them when new sources arrive, maintains cross-references, and keeps everything consistent. You read it; the LLM writes it.

**The schema** — a document (e.g. CLAUDE.md for Claude Code or AGENTS.md for Codex) that tells the LLM how the wiki is structured, what the conventions are, and what workflows to follow when ingesting sources, answering questions, or maintaining the wiki. This is the key configuration file — it's what makes the LLM a disciplined wiki maintainer rather than a generic chatbot. You and the LLM co-evolve this over time as you figure out what works for your domain.

## Operations

**Ingest.** You drop a new source into the raw collection and tell the LLM to process it. An example flow: the LLM reads the source, discusses key takeaways with you, writes a summary page in the wiki, updates the index, updates relevant entity and concept pages across the wiki, and appends an entry to the log. A single source might touch 10-15 wiki pages. Personally I prefer to ingest sources one at a time and stay involved — I read the summaries, check the updates, and guide the LLM on what to emphasize. But you could also batch-ingest many sources at once with less supervision. It's up to you to develop the workflow that fits your style and document it in the schema for future sessions.

**Query.** You ask questions against the wiki. The LLM searches for relevant pages, reads them, and synthesizes an answer with citations. Answers can take different forms depending on the question — a markdown page, a comparison table, a slide deck (Marp), a chart (matplotlib), a canvas. The important insight: **good answers can be filed back into the wiki as new pages.** A comparison you asked for, an analysis, a connection you discovered — these are valuable and shouldn't disappear into chat history. This way your explorations compound in the knowledge base just like ingested sources do.

**Lint.** Periodically, ask the LLM to health-check the wiki. Look for: contradictions between pages, stale claims that newer sources have superseded, orphan pages with no inbound links, important concepts mentioned but lacking their own page, missing cross-references, data gaps that could be filled with a web search. The LLM is good at suggesting new questions to investigate and new sources to look for. This keeps the wiki healthy as it grows.

## Indexing and logging

Two special files help the LLM (and you) navigate the wiki as it grows. They serve different purposes:

**index.md** is content-oriented. It's a catalog of everything in the wiki — each page listed with a link, a one-line summary, and optionally metadata like date or source count. Organized by category (entities, concepts, sources, etc.). The LLM updates it on every ingest. When answering a query, the LLM reads the index first to find relevant pages, then drills into them. This works surprisingly well at moderate scale (~100 sources, ~hundreds of pages) and avoids the need for embedding-based RAG infrastructure.

**log.md** is chronological. It's an append-only record of what happened and when — ingests, queries, lint passes. A useful tip: if each entry starts with a consistent prefix (e.g. `## [2026-04-02] ingest | Article Title`), the log becomes parseable with simple unix tools — `grep "^## \[" log.md | tail -5` gives you the last 5 entries. The log gives you a timeline of the wiki's evolution and helps the LLM understand what's been done recently.

## Optional: CLI tools

At some point you may want to build small tools that help the LLM operate on the wiki more efficiently. A search engine over the wiki pages is the most obvious one — at small scale the index file is enough, but as the wiki grows you want proper search. [qmd](https://github.com/tobi/qmd) is a good option: it's a local search engine for markdown files with hybrid BM25/vector search and LLM re-ranking, all on-device. It has both a CLI (so the LLM can shell out to it) and an MCP server (so the LLM can use it as a native tool). You could also build something simpler yourself — the LLM can help you vibe-code a naive search script as the need arises.

## Tips and tricks

- **Obsidian Web Clipper** is a browser extension that converts web articles to markdown. Very useful for quickly getting sources into your raw collection.
- **Download images locally.** In Obsidian Settings → Files and links, set "Attachment folder path" to a fixed directory (e.g. `raw/assets/`). Then in Settings → Hotkeys, search for "Download" to find "Download attachments for current file" and bind it to a hotkey (e.g. Ctrl+Shift+D). After clipping an article, hit the hotkey and all images get downloaded to local disk. This is optional but useful — it lets the LLM view and reference images directly instead of relying on URLs that may break. Note that LLMs can't natively read markdown with inline images in one pass — the workaround is to have the LLM read the text first, then view some or all of the referenced images separately to gain additional context. It's a bit clunky but works well enough.
- **Obsidian's graph view** is the best way to see the shape of your wiki — what's connected to what, which pages are hubs, which are orphans.
- **Marp** is a markdown-based slide deck format. Obsidian has a plugin for it. Useful for generating presentations directly from wiki content.
- **Dataview** is an Obsidian plugin that runs queries over page frontmatter. If your LLM adds YAML frontmatter to wiki pages (tags, dates, source counts), Dataview can generate dynamic tables and lists.
- The wiki is just a git repo of markdown files. You get version history, branching, and collaboration for free.

## Why this works

The tedious part of maintaining a knowledge base is not the reading or the thinking — it's the bookkeeping. Updating cross-references, keeping summaries current, noting when new data contradicts old claims, maintaining consistency across dozens of pages. Humans abandon wikis because the maintenance burden grows faster than the value. LLMs don't get bored, don't forget to update a cross-reference, and can touch 15 files in one pass. The wiki stays maintained because the cost of maintenance is near zero.

The human's job is to curate sources, direct the analysis, ask good questions, and think about what it all means. The LLM's job is everything else.

The idea is related in spirit to Vannevar Bush's Memex (1945) — a personal, curated knowledge store with associative trails between documents. Bush's vision was closer to this than to what the web became: private, actively curated, with the connections between documents as valuable as the documents themselves. The part he couldn't solve was who does the maintenance. The LLM handles that.


## Note

This document is intentionally abstract. It describes the idea, not a specific implementation. The exact directory structure, the schema conventions, the page formats, the tooling — all of that will depend on your domain, your preferences, and your LLM of choice. Everything mentioned above is optional and modular — pick what's useful, ignore what isn't. For example: your sources might be text-only, so you don't need image handling at all. Your wiki might be small enough that the index file is all you need, no search engine required. You might not care about slide decks and just want markdown pages. You might want a completely different set of output formats. The right way to use this is to share it with your LLM agent and work together to instantiate a version that fits your needs. The document's only job is to communicate the pattern. Your LLM can figure out the rest.

---

## Instantiation: Slack-fed team wiki

This section instantiates the LLM Wiki pattern for a specific domain: an internal knowledge base maintained from a team's Slack history. It is shipped by the [theplant/slackwiki](https://github.com/theplant/slackwiki) GitHub Action and refreshed in every downstream repo on every run, so the schema cannot drift.

**Domain**: an internal knowledge base maintained from a team's Slack history.
**Raw sources**: `raw/slack/<channel>/YYYY-MM-DD.md` — one file per channel per day, each Slack message already rendered to markdown with author, timestamp, and thread replies. Files are immutable.
**Wiki output**: everything you write goes under `wiki/`. Never modify anything under `raw/`.

### Language policy (strict)

- **All wiki content is written in English.** This includes summaries, entity pages, decisions, index, log, frontmatter values, and commit messages — everything you produce.
- Source messages may be in any language. When ingesting non-English messages, paraphrase them into English in the wiki body, but preserve the original text in a `> quote` block underneath the paraphrase so meaning is not lost.
- File and directory names: lowercase ASCII, kebab-case.

### Page types and naming

| Path | One page per | Example |
|------|-------------|---------|
| `wiki/people/<slack-handle>.md` | Person seen in Slack | `wiki/people/example.md` |
| `wiki/channels/<channel-name>.md` | Channel | `wiki/channels/general.md` |
| `wiki/projects/<kebab-case>.md` | Project (≥ 3 distinct mentions before creating) | `wiki/projects/payments-v2.md` |
| `wiki/topics/<kebab-case>.md` | Recurring concept / theme | `wiki/topics/incident-response.md` |
| `wiki/decisions/YYYY-MM-DD-<slug>.md` | Decision made in Slack | `wiki/decisions/2026-05-11-drop-mongo.md` |
| `wiki/sources/YYYY-MM-DD-slack.md` | Ingest batch digest | `wiki/sources/2026-05-11-slack.md` |
| `wiki/lint/YYYY-MM-DD.md` | Weekly lint report | `wiki/lint/2026-05-11.md` |
| `wiki/todos.md` | (single file) open items surfaced by lint that need follow-up | `wiki/todos.md` |

### Frontmatter

Every wiki page starts with YAML frontmatter. Minimum fields per type:

```yaml
# people
---
type: person
slack_handle: "@example"
aliases: []
channels: []
first_seen: 2026-05-11
---

# channels
---
type: channel
slack_name: general
purpose: "..."
first_seen: 2026-05-11
---

# projects / topics
---
type: project   # or "topic"
status: active  # active | dormant | done
first_seen: 2026-05-11
related: []
---

# decisions
---
type: decision
date: 2026-05-11
status: accepted   # accepted | superseded | reverted
participants: []
---

# sources
---
type: source
date: 2026-05-11
channels_touched: []
message_count: 0
---
```

### Ingest workflow

Trigger: the Action sets `state/new_files.txt` to the list of raw files written this run, then invokes you with the ingest prompt. Steps:

0. **Pre-pass — resolve open items from prior lint passes.** Before processing new raw files, do two short scans against the existing wiki:

   **(a) `⚠️ Unverified as of <date>` markers.** Search all wiki pages for these markers. For each one:
   - Read the claim that immediately follows the marker.
   - Check the new raw files (only those in `state/new_files.txt`) for any message that resolves the claim (confirms a deployment, closes a ticket, reverses a decision, etc.).
   - If resolved: remove the `⚠️ Unverified` block and add a new `## YYYY-MM-DD` section under the same page confirming the resolution with a `[source](...)` citation.
   - If not resolved: leave it.

   **(b) `wiki/todos.md` open items.** For each `- [ ]` item under `## Open`:
   - Check whether the new raw files close the item.
   - If yes: change `- [ ]` to `- [x]`, strike the line through, append `(resolved YYYY-MM-DD in [[sources/YYYY-MM-DD-slack]])`, and move it under `## Resolved`.
   - If no: leave it.

1. **Read only the files listed in `state/new_files.txt`.** Do not scan the rest of the repo. This caps token cost.
2. **Extract entities** from each file: people (authors and `@mentions`), projects / products / features by name, decisions (`"we decided"`, `"approved"`, `"let's go with X"`), open questions, links to other systems.
3. **Update entity pages.** For each entity:
   - If `wiki/<type>/<slug>.md` does not exist, create it with proper frontmatter and a `## YYYY-MM-DD` section.
   - If it exists, **append, do not overwrite**: add a new `## YYYY-MM-DD` section with today's findings. Old content stays intact.
4. **Write `wiki/sources/YYYY-MM-DD-slack.md`** — a digest page for this batch listing: channels touched, message counts, key events, new entities created, decisions recorded, and which `⚠️ Unverified` markers / todos got resolved in step 0.
5. **Update `wiki/index.md`** — add links to any newly created pages, under the correct category.
6. **Append one line to `wiki/log.md`** in this exact format:
   ```
   ## [YYYY-MM-DD] ingest | slack | N channels, M messages, +X people, +Y projects, +Z decisions, -K resolved
   ```
   where `-K resolved` counts items closed in the pre-pass.
7. **Never touch `raw/`.** The `.claude/settings.json` denies it, but obey it explicitly.

### Writing style

- Encyclopedic, neutral, factual. No first person, no LLM hedging (`"As an AI…"`).
- After every claim cite the source raw file:
  `[source](../sources/2026-05-11-slack.md#msg-1432)` *(the `msg-1432` anchor is the Slack `ts` truncated to `HHMM`; the digest page anchors to it)*.
- Use Obsidian wiki links `[[slack-handle]]` for internal references so the graph view works.
- YAML frontmatter on every page (see above).
- When new information contradicts an earlier claim, **do not silently overwrite**. Mark it:
  ```
  > ⚠️ Conflicts with the 2026-04-20 entry in this page; see [[log]] for the source.
  ```
- Be conservative about creating pages. Projects need ≥ 3 distinct mentions before they get a page; topics need ≥ 5. Lower bars produce noise.

### Lint workflow

When invoked in lint mode (`mode: lint` in the Action), do five things in one pass and produce ONE PR containing everything. Diagnose-only lint is useless: a list of "recommended actions" sitting in a markdown file gets read once and forgotten. Each lint pass must leave the wiki strictly more correct than it found it.

1. **Apply mechanical fixes** to existing wiki pages — these are zero-judgment, low-risk edits:
   - **Wikilink case**: `[[Kate]]` → `[[kate]]` whenever the target file is lowercase kebab-case.
   - **Symmetric `related:` frontmatter**: if A.related lists B but B.related does not list A, add it.
   - **Quote-block wrapping**: bare non-English inline terms get moved into a `> quote` block right after the English paraphrase, per the language policy.
   - **Decision back-links**: every decision page gets a `See also:` line linking back to participant people pages and the related project page; sibling project pages get a "Key decisions" sub-section linking to relevant decisions.

2. **Create stub pages** for missing-but-warranted entities. Thresholds:
   - Topic pages for concepts referenced in ≥ 5 distinct wiki pages.
   - People pages for `@handle`s referenced in ≥ 3 distinct wiki pages but lacking their own page.

   Stub format (use existing wiki references to synthesize content — stubs are not empty):
   ```
   ---
   type: <topic | person>
   created_by: lint
   first_seen: YYYY-MM-DD
   ---

   # <Title>

   <One paragraph synthesizing what is known from existing wiki references.>

   ## Mentions

   - [[page1]] — what was said
   - [[page2]] — what was said

   _Stub created by lint based on existing wiki references. Future ingests will expand this page as new Slack messages provide more detail._
   ```

3. **Inject `⚠️ Unverified as of YYYY-MM-DD` markers** above each stale claim (claims dated more than 5 days ago whose follow-up state is not recorded). Format:
   ```
   > ⚠️ Unverified as of YYYY-MM-DD. <one-line description of what needs confirmation>.
   ```
   These get auto-resolved by the next ingest pass when new Slack messages confirm them (see Ingest workflow step 0).

4. **Update `wiki/todos.md`** with anything that requires authorial judgment and isn't covered by 1–3 (e.g. scoping decisions, naming conventions, structural questions about the wiki itself). Append to `## Open` in the format:
   ```
   - [ ] YYYY-MM-DD — **<action>**. <context with [[wiki-links]]>
   ```
   Do not modify existing `## Resolved` items. Create `wiki/todos.md` if it doesn't exist (see seed format in `templates/wiki-seed/todos.md`).

5. **Write the lint report** at `wiki/lint/YYYY-MM-DD.md` with one section per step above documenting exactly what was fixed / created / injected / queued. End with a "Residual items" section pointing readers to `wiki/todos.md` for tracked follow-ups.

6. **Update `wiki/index.md`** for any new pages, and append one line to `wiki/log.md`:
   ```
   ## [YYYY-MM-DD] lint | N fixes, M stubs, P markers, Q new todos
   ```

The resulting PR contains: the report + all mechanical fixes + new stub pages + injected markers + updated `todos.md` — one reviewable changeset.

Bounds: never touch `raw/`. Never delete content from existing pages; mark `status: superseded` instead. Never edit a `## Resolved` todo item.

### Bounds and safety

- Never modify, delete, or move anything under `raw/`.
- Never delete an existing wiki page; mark it `status: superseded` instead and leave it.
- Never include API keys, tokens, or full email addresses found in messages. Redact: `<email redacted>`, `<token redacted>`.
- Treat customer names and PII according to the `wiki.focus` policy in `slackwiki.config.yml` (if any).
- Keep file and directory names lowercase ASCII, kebab-case. No spaces, no unicode.
