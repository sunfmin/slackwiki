# SlackWiki — Build Plan

Treat Slack as the raw source of truth. Every day, automatically pull new messages and let Claude Code (running in GitHub Actions) ingest them into a continuously growing markdown wiki (karpathy's "LLM Wiki" pattern). Everything lives in a GitHub repository.

## Two governing principles

1. **All stored content in the repo is in English.** This covers `wiki/`, the rendered markdown under `raw/`, `log.md` entries, frontmatter, commit messages, README, and CLAUDE.md. Original Slack message text is preserved in its source language (potentially mixed), but every derived artifact Claude writes is English. The rule is encoded in CLAUDE.md and enforced by Claude itself.
2. **The tooling ships as a reusable GitHub Action.** All workspace-specific differences (token, timezone, focus, channel excludes) are injected through GitHub Secrets and a `slackwiki.config.yml` in each downstream repo. No company names, person names, or channel names are hardcoded anywhere in the Action.

## Locked decisions

| # | Decision | Value |
|---|----------|-------|
| A | Channels to ingest | **All public channels the bot is a member of** (auto-discovered) |
| B | LLM credential | **`CLAUDE_CODE_OAUTH_TOKEN`** (Claude subscription, generated via `claude setup-token`) |
| C | Data repo visibility | **Private** |
| D | Bootstrap backfill | **7 days** (configurable in `slackwiki.config.yml`) |
| E | Storage language | **English** (enforced in CLAUDE.md) |
| F | Lint workflow | **Weekly** (separate workflow file) |
| G | Slack file attachments | **Metadata + URL only**, not downloaded |
| H | Repo separation | **Action repo + data repo, separate** |
| Pkg | Distribution | **GitHub Action only** (composite action), no PyPI package |
| Org | Publishing org | **`theplant`** → `github.com/theplant/slackwiki` (this dir becomes that repo) |

---

## 0. Two-repo architecture

```
theplant/slackwiki              (public, the Action — this current directory)
├── action.yml                  # composite Action definition, Marketplace entry point
├── scripts/                    # Python scripts the Action calls
├── templates/                  # CLAUDE.md, config example, wiki seed files
└── README.md

<company>-wiki                  (per company, private — created by each user)
├── .github/workflows/
│   ├── daily-ingest.yml        # 12-line caller of theplant/slackwiki@v1, mode=ingest
│   └── weekly-lint.yml         # 12-line caller of theplant/slackwiki@v1, mode=lint
├── slackwiki.config.yml        # company-specific (timezone, focus, excludes)
├── CLAUDE.md                   # bootstrapped from Action on first run, refreshed each run
├── .claude/settings.json       # deny writes to raw/
├── raw/                        # immutable Slack source (growing)
├── wiki/                       # LLM-maintained (growing)
├── state/                      # cursors, user cache
└── .gitignore
```

Each company gets a private data repo. The Action is shared across all of them. Update the Action → all downstream data repos pick up improvements on their next scheduled run (or pinned to a tag like `@v1` for stability).

---

## 1. Data flow

```
┌──────────┐    daily cron    ┌──────────────────────────────┐
│  Slack   │ ───────────────▶ │ <company>-wiki Actions runner│
│  API     │                  │                              │
└──────────┘                  │ uses: theplant/slackwiki@v1  │
                              │   mode: ingest               │
                              │     │                        │
                              │     ├─ fetch_slack.py        │
                              │     │   └ pull new msgs      │
                              │     │   └ write raw/         │
                              │     │   └ update state/      │
                              │     │                        │
                              │     ├─ claude-code (npm)     │
                              │     │   └ reads CLAUDE.md    │
                              │     │   └ ingests raw/ → wiki│
                              │     │                        │
                              │     └─ git commit + push     │
                              └──────────┬───────────────────┘
                                         │
                                         ▼
                              ┌──────────────────────┐
                              │  <company>-wiki repo │
                              │  raw/  (immutable)   │
                              │  wiki/ (LLM-owned)   │
                              │  state/ (cursors)    │
                              └──────────────────────┘
```

Three layers (karpathy's naming):

- **Raw sources** = `raw/slack/<channel>/YYYY-MM-DD.md`, append-only.
- **Wiki** = `wiki/`, written by Claude Code.
- **Schema** = `CLAUDE.md`, instructs Claude how to organize the wiki and ingest.

---

## 2. Action repo layout (`theplant/slackwiki`, this directory)

```
slackwiki/
├── action.yml                  # composite Action; Marketplace entry point
├── README.md                   # how to use the Action in a downstream repo
├── PLAN.md                     # this file
│
├── scripts/
│   ├── fetch_slack.py          # discover public channels, fetch new messages → raw/
│   ├── render_message.py       # render Slack JSON message to markdown
│   ├── ingest.py               # invokes `claude -p` with the ingest prompt
│   ├── lint.py                 # invokes `claude -p` with the lint prompt (weekly)
│   ├── init.py                 # bootstrap a downstream repo (CLAUDE.md, wiki seeds, config)
│   ├── commit_and_push.py      # safe commit + rebase + push
│   └── requirements.txt        # slack_sdk, pyyaml
│
├── templates/
│   ├── CLAUDE.md               # karpathy gist + Slack instantiation block (English)
│   ├── slackwiki.config.yml    # annotated example config
│   ├── claude-settings.json    # deny writes to raw/
│   ├── gitignore               # .gitignore for downstream repo
│   ├── daily-ingest.yml        # downstream workflow example
│   ├── weekly-lint.yml         # downstream lint workflow example
│   └── wiki-seed/
│       ├── index.md
│       ├── log.md
│       └── overview.md
│
├── .github/workflows/
│   ├── test.yml                # CI for the Action itself (lint scripts, dry-run)
│   └── release.yml             # tag → Marketplace publish
│
└── LICENSE
```

---

## 3. Downstream `<company>-wiki` repo layout

What ends up in each company's private data repo:

```
<company>-wiki/
├── .github/workflows/
│   ├── daily-ingest.yml        # see §5.1
│   └── weekly-lint.yml         # see §5.2
├── slackwiki.config.yml        # company-specific config
├── CLAUDE.md                   # copied/refreshed from theplant/slackwiki templates
├── .claude/settings.json       # deny raw/ writes
├── .gitignore
├── README.md                   # short pointer to theplant/slackwiki docs
├── raw/                        # grows over time
├── wiki/                       # grows over time
└── state/                      # cursors, user cache
```

The downstream repo carries only configuration and data. No scripts, no logic. Update the Action → every company benefits.

---

## 4. Tools and services

| Category | Tool | Where | Purpose |
|----------|------|-------|---------|
| Source | Slack App + Bot Token | one per company | `conversations.list`, `conversations.history`, `conversations.replies`, `users.info` |
| Action repo | `theplant/slackwiki` | public GitHub | The packaged tool |
| Data repo | `<company>-wiki` | private GitHub | Stores wiki + raw + state |
| Runtime — fetch | Python 3.11 + `slack_sdk` + `pyyaml` | inside Action runner | Pulls messages, renders to markdown |
| Runtime — LLM | `@anthropic-ai/claude-code` (npm) | inside Action runner | Runs `claude --print` non-interactively |
| LLM auth | `CLAUDE_CODE_OAUTH_TOKEN` (Claude subscription) | downstream repo secret | Auth for Claude Code |
| Schedule | GitHub Actions cron | downstream repo | Daily ingest, weekly lint |
| Write-back | `github-actions[bot]` push | inside Action | Commits raw/, wiki/, state/ updates |
| Browse (optional) | Obsidian | each user's laptop | Open data repo as a vault, use graph view |
| Search (optional, later) | qmd (tobi/qmd) | Action runner, future | BM25 + vector search at scale |

---

## 5. Downstream workflow files

### 5.1 `daily-ingest.yml` (downstream repo)

```yaml
name: daily-ingest
on:
  schedule: [{ cron: '0 22 * * *' }]   # UTC 22:00; runner reads timezone from config
  workflow_dispatch:
permissions:
  contents: write
jobs:
  ingest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: theplant/slackwiki@v1
        with:
          mode: ingest
          config: slackwiki.config.yml
          auto_commit: true
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
          CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
```

### 5.2 `weekly-lint.yml` (downstream repo)

```yaml
name: weekly-lint
on:
  schedule: [{ cron: '0 1 * * 1' }]   # Mondays 01:00 UTC
  workflow_dispatch:
permissions:
  contents: write
  pull-requests: write
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: theplant/slackwiki@v1
        with:
          mode: lint
          config: slackwiki.config.yml
          output: pull-request           # or "commit" — pull-request opens a PR with lint findings
        env:
          CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
```

---

## 6. The Action itself (`action.yml`, composite)

Inputs:

| Input | Required | Default | Notes |
|-------|----------|---------|-------|
| `mode` | yes | — | `ingest` \| `lint` \| `fetch-only` \| `init` |
| `config` | no | `slackwiki.config.yml` | Path to per-workspace config |
| `auto_commit` | no | `true` | Commit & push after running |
| `output` | no | `commit` | For `lint` mode: `commit` or `pull-request` |

Env vars consumed (from downstream workflow):

- `SLACK_BOT_TOKEN` — required for `ingest` and `fetch-only`.
- `CLAUDE_CODE_OAUTH_TOKEN` — required for `ingest`, `lint`.

Steps inside `action.yml` (composite, all `using: composite`):

1. `actions/setup-python@v5` (3.11)
2. `pip install -r ${{ github.action_path }}/scripts/requirements.txt`
3. `actions/setup-node@v4` (22)
4. `npm install -g @anthropic-ai/claude-code`
5. If `CLAUDE.md` is missing or out of date in the caller repo, copy from `${{ github.action_path }}/templates/CLAUDE.md` (so schema updates propagate automatically).
6. Same for `.claude/settings.json`, `.gitignore`, and seed `wiki/` files if missing.
7. Dispatch on `mode`:
   - `ingest` → `python scripts/fetch_slack.py && python scripts/ingest.py`
   - `lint` → `python scripts/lint.py`
   - `fetch-only` → `python scripts/fetch_slack.py`
   - `init` → `python scripts/init.py` (just bootstrap, do nothing else)
8. If `auto_commit: true` and there are staged changes → `python scripts/commit_and_push.py`

---

## 7. Key implementation details

### 7.1 Slack fetch (`scripts/fetch_slack.py`)

1. Load `slackwiki.config.yml`.
2. Call `conversations.list(types=public_channel, exclude_archived=true)`. Keep channels where `is_member == true` and name is not in `config.channel_excludes`. Save the `channel_id → name` map to `raw/slack/_channels.json`.
3. Read `state/cursors.json` for each channel's last `latest_ts`. If absent, bootstrap from `now - config.backfill_days`.
4. For each channel:
   - `conversations.history(channel=..., oldest=last_ts, inclusive=false)`, paginating.
   - For every message with `reply_count > 0`, also call `conversations.replies(ts=parent_ts)` (thread substance lives here).
   - Resolve `<@U01ABC>` mentions via `users.info`, cached in `state/users.json`.
   - For file attachments: store only metadata (name, mimetype, permalink) in markdown — do not download files (decision G).
   - Render each message to markdown (see §7.2) and append to `raw/slack/<channel>/YYYY-MM-DD.md` (day bucketed by `config.timezone`).
5. Update `state/cursors.json` with new latest `ts`.
6. Emit `state/new_files.txt` — list of files written or modified in this run.

Rate limiting: `slack_sdk.WebClient` with `RateLimitErrorRetryHandler`; Tier 3 is ~50 req/min.

### 7.2 Message render (`scripts/render_message.py`)

```markdown
## 14:32 — @example     <!-- ts=1731305520.123456 -->
Message body with <@handle> mentions resolved.
[attached file](https://files.slack.com/...) (image/png, 1.2 MB)

> **thread (3 replies)**
> - 14:35 @alice: reply 1
> - 14:40 @bob: reply 2
```

Each message gets a stable anchor (the Slack `ts`) so wiki pages can deep-link to specific messages.

### 7.3 CLAUDE.md (templated, fully English)

CLAUDE.md = karpathy gist (English) **+** the Slack-instantiation block below (English):

```markdown
## Instantiation: Slack-fed team wiki

**Domain**: an internal knowledge base maintained from a team's Slack history.
**Raw sources**: `raw/slack/<channel>/YYYY-MM-DD.md` — one file per channel per day,
each Slack message already rendered to markdown with author, timestamp, and thread replies.
**Wiki output**: everything Claude writes goes under `wiki/`. Never modify anything under `raw/`.

### Language policy (strict)

- All wiki content is written in English. This includes summaries, entity pages,
  decisions, index, log, frontmatter values, commit messages — everything Claude produces.
- Source messages may be in any language. When ingesting non-English messages,
  Claude paraphrases them into English and preserves the original in a `> quote` block.
- File and directory names: lowercase ASCII, kebab-case.

### Page types and naming

- `wiki/people/<slack-handle>.md` — one page per person. Frontmatter: type, slack_handle, aliases, channels, first_seen.
- `wiki/channels/<channel-name>.md` — one page per channel: what is discussed, who is active, recent topics.
- `wiki/projects/<kebab-case>.md` — projects (only after ≥ 3 distinct mentions).
- `wiki/topics/<kebab-case>.md` — recurring concepts.
- `wiki/decisions/YYYY-MM-DD-<slug>.md` — decisions made in Slack.
- `wiki/sources/YYYY-MM-DD-slack.md` — one summary page per ingest batch.

### Ingest workflow

1. Read `state/new_files.txt`. Only read those files; do not scan the whole repo.
2. Extract: people, projects, decisions, open questions, links.
3. For each entity: create the page if missing, otherwise append a new `## YYYY-MM-DD` section.
4. Write `wiki/sources/YYYY-MM-DD-slack.md` summarizing the batch.
5. Update `wiki/index.md` with links to new pages.
6. Append one line to `wiki/log.md`:
   `## [YYYY-MM-DD] ingest | slack | N channels, M messages, +X people, +Y projects`
7. Never touch `raw/`.

### Writing style

- Encyclopedic, neutral, factual. No first person.
- Cite the source after every claim: `[source](../sources/YYYY-MM-DD-slack.md#msg-1432)`.
- Use Obsidian wiki links `[[slack-handle]]`.
- YAML frontmatter on every page.
- Contradictions: mark with `> ⚠️ Conflicts with the 2026-04-20 entry`, do not silently overwrite.

### Lint mode

When invoked in lint mode: review wiki for stale claims, orphans, contradictions,
missing cross-links. Output a markdown report at `wiki/lint/YYYY-MM-DD.md`.
```

The full karpathy gist is the first half of CLAUDE.md; the block above is the second half. CLAUDE.md is copied from `templates/` on every Action run so schema updates propagate without manual intervention.

### 7.4 `slackwiki.config.yml` (downstream)

```yaml
# slackwiki.config.yml — per-workspace settings. Action is workspace-agnostic.
workspace_name: example-corp
timezone: Asia/Tokyo                   # cron runs in UTC; raw files bucketed in this TZ
backfill_days: 7                       # how far back to pull on the first run
include_threads: true
include_private_channels: false        # bot must be a member to fetch private channels
channel_excludes:                      # public channels to skip even if bot is a member
  - random
  - off-topic
wiki:
  language: en
  focus: |
    Internal product engineering team. Emphasize decisions about the
    payments and onboarding products. Treat customer names as PII —
    summarize impact, do not store full names.
```

### 7.5 Gotchas

1. **`ts` is the cursor, not date.** `conversations.history(oldest=last_ts, inclusive=false)` returns strictly new messages.
2. **Threads must be pulled separately.** `conversations.history` returns thread parents only; replies require `conversations.replies`.
3. **Bot must be invited** to every channel — including public ones — to read history.
4. **Rate limits**: Slack Tier 3 ~50 req/min. Use `slack_sdk.WebClient` with `RateLimitErrorRetryHandler`.
5. **First run**: bootstrap with `backfill_days` only. Do not pull years of history in one shot — it's expensive and the wiki ends up incoherent.
6. **Don't let Claude write into `raw/`.** `.claude/settings.json` denies it; CLAUDE.md says it; `claude --permission-mode acceptEdits` (not `bypassPermissions`).
7. **Token budget**: prompt explicitly says "only read files in `state/new_files.txt`."
8. **Privacy**: the downstream repo holds private channel content. Repo must be private.
9. **Push conflicts**: `commit_and_push.py` does `git pull --rebase` before pushing.
10. **CI = non-interactive**: always `claude --print`, never the REPL.
11. **CLAUDE.md drift**: the Action overwrites `CLAUDE.md` and `.claude/settings.json` from `templates/` on every run, so downstream repos can't accidentally fall behind on schema. Users who want a custom schema fork the Action.

---

## 8. Setup steps (per company)

For each new company adopting SlackWiki:

### 8.1 Slack App (one-time, per workspace)

1. https://api.slack.com/apps → **Create New App** → From scratch.
2. Name it (e.g. `SlackWiki Ingest`). Pick the workspace.
3. **OAuth & Permissions** → Bot Token Scopes:
   - `channels:history`, `channels:read`
   - `groups:history`, `groups:read` (only if `include_private_channels: true`)
   - `users:read`
   - `files:read`
4. **Install to Workspace** → copy the Bot User OAuth Token (`xoxb-...`).
5. Invite the bot to every channel you want ingested: `/invite @SlackWiki Ingest`.

### 8.2 Claude Code OAuth token (one-time, per Claude account)

1. On a machine where Claude Code is installed and logged in to a Claude subscription account: `claude setup-token`.
2. Copy the printed token.

### 8.3 Data repo

1. `gh repo create <company>-wiki --private --clone`.
2. From the cloned repo, run once:
   ```bash
   gh workflow run -R theplant/slackwiki init.yml   # or copy templates manually
   ```
   Or copy these files from `theplant/slackwiki/templates/` into the new repo:
   - `slackwiki.config.yml` (edit timezone, workspace_name, channel_excludes, focus)
   - `daily-ingest.yml` → `.github/workflows/`
   - `weekly-lint.yml` → `.github/workflows/`
   - `CLAUDE.md`, `.claude/settings.json`, `.gitignore`, `wiki/` seed files (auto-refreshed on first Action run, but committing them once avoids the first run being empty).
3. **Settings → Secrets and variables → Actions**:
   - `SLACK_BOT_TOKEN` = `xoxb-...`
   - `CLAUDE_CODE_OAUTH_TOKEN` = the value from §8.2
4. **Settings → Actions → General → Workflow permissions** → **Read and write permissions**.
5. Push, then **Actions → daily-ingest → Run workflow** to do the first ingest.

---

## 9. Implementation checklist

✅ = I will write in this directory next. ❌ = your manual step.

### Action repo (`theplant/slackwiki`, this directory)

- [ ] ✅ `action.yml` (composite Action)
- [ ] ✅ `scripts/fetch_slack.py` (auto-discover public channels, fetch, render, cursor)
- [ ] ✅ `scripts/render_message.py`
- [ ] ✅ `scripts/ingest.py` (invokes `claude -p`)
- [ ] ✅ `scripts/lint.py` (invokes `claude -p` lint prompt, opens PR or commits report)
- [ ] ✅ `scripts/init.py` (bootstrap helper, also used by the Action to refresh CLAUDE.md)
- [ ] ✅ `scripts/commit_and_push.py`
- [ ] ✅ `scripts/requirements.txt`
- [ ] ✅ `templates/CLAUDE.md` (karpathy gist + Slack instantiation, all English)
- [ ] ✅ `templates/slackwiki.config.yml`
- [ ] ✅ `templates/claude-settings.json`
- [ ] ✅ `templates/gitignore`
- [ ] ✅ `templates/daily-ingest.yml`
- [ ] ✅ `templates/weekly-lint.yml`
- [ ] ✅ `templates/wiki-seed/{index,log,overview}.md`
- [ ] ✅ `README.md` (English; "use this action in your repo" + setup steps)
- [ ] ✅ `.github/workflows/test.yml` (CI for the Action)
- [ ] ✅ `LICENSE`
- [ ] ❌ Create `theplant/slackwiki` repo on GitHub (you / your org admin)
- [ ] ❌ `git init && git push -u origin main` and tag `v1` (you, or I can run while you watch)
- [ ] ❌ Publish to GitHub Marketplace (optional — `@v1` ref works without Marketplace listing)

### Per-company data repo (`<company>-wiki`)

- [ ] ❌ Create Slack App, install, invite bot to channels (you, in browser)
- [ ] ❌ `claude setup-token` and grab the OAuth token (you, locally)
- [ ] ❌ `gh repo create <company>-wiki --private` (you)
- [ ] ❌ Copy `templates/` files into the new repo, edit `slackwiki.config.yml` (you, or I scaffold a `gh` one-liner)
- [ ] ❌ Set repo secrets `SLACK_BOT_TOKEN` and `CLAUDE_CODE_OAUTH_TOKEN` (you)
- [ ] ❌ Set workflow permissions to Read and write (you)
- [ ] ❌ Trigger first run manually (you)

---

## 10. Next step

All decisions are locked. Say **"go"** and I'll generate every ✅ file in this directory.
