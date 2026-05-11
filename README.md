# SlackWiki

A reusable GitHub Action that turns a team's Slack history into a continuously growing, Claude Code-maintained markdown wiki.

Implements the [karpathy LLM-wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) for the Slack-fed-team-wiki domain. See [`PLAN.md`](./PLAN.md) for the full architecture and design decisions, and [`templates/CLAUDE.md`](./templates/CLAUDE.md) for the schema Claude follows when ingesting.

## What it does

Every day in your private `<company>-wiki` repo:

1. **Fetch** — auto-discovers every public Slack channel the bot has been invited to and pulls new messages (and thread replies) since the last cursor, into immutable `raw/slack/<channel>/YYYY-MM-DD.md` files.
2. **Ingest** — runs Claude Code with the schema in `CLAUDE.md` to extract entities (people, projects, topics, decisions) and update interlinked pages under `wiki/`. Every claim cites its source message.
3. **Commit + push** — commits `raw/`, `wiki/`, `state/` back to the repo so the wiki compounds over time.

Once a week, a separate workflow runs `mode: lint` to flag stale claims, contradictions, orphan pages, and missing cross-references — output as a PR for human review.

## Quick start (per company)

### 1. Slack App

1. https://api.slack.com/apps → **Create New App** → From scratch.
2. **OAuth & Permissions** → Bot Token Scopes:
   - `channels:history`, `channels:read`
   - `groups:history`, `groups:read` *(only if you set `include_private_channels: true`)*
   - `users:read`
   - `files:read`
3. **Install to Workspace**; copy the **Bot User OAuth Token** (`xoxb-...`).
4. `/invite @<your-bot>` into every channel you want ingested.

### 2. Claude Code OAuth token

On any machine with Claude Code installed and logged into a Claude subscription account:

```bash
claude setup-token
```

Copy the printed token. You will store it as a GitHub Secret in step 3.

### 3. Data repo

```bash
gh repo create <company>-wiki --private --clone
cd <company>-wiki
```

Add these GitHub Secrets in **Settings → Secrets and variables → Actions**:

- `SLACK_BOT_TOKEN` — the `xoxb-...` from step 1
- `CLAUDE_CODE_OAUTH_TOKEN` — the token from step 2

Set **Settings → Actions → General → Workflow permissions** to **Read and write permissions**.

Then bootstrap the repo by running this once (commit the result):

```bash
gh workflow run "init" --ref main   # or copy templates/ files manually
```

Or, manually, copy these files from this action repo into your data repo:

- `templates/slackwiki.config.yml` → `slackwiki.config.yml` *(edit timezone, workspace_name, channel_excludes, focus)*
- `templates/daily-ingest.yml` → `.github/workflows/daily-ingest.yml`
- `templates/weekly-lint.yml` → `.github/workflows/weekly-lint.yml`
- `templates/CLAUDE.md` → `CLAUDE.md` *(refreshed automatically on every run)*
- `templates/claude-settings.json` → `.claude/settings.json`
- `templates/gitignore` → `.gitignore`
- `templates/wiki-seed/*.md` → `wiki/`

Push, then trigger **Actions → daily-ingest → Run workflow** for the first run.

## Usage in a downstream workflow

This is all that lives in `<company>-wiki/.github/workflows/daily-ingest.yml`:

```yaml
name: daily-ingest
on:
  schedule: [{ cron: '0 22 * * *' }]
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
          auto_commit: 'true'
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
          CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
```

## Action inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `mode` | yes | — | `ingest` \| `lint` \| `fetch-only` \| `init` |
| `config` | no | `slackwiki.config.yml` | Path to the per-workspace config (relative to caller repo root) |
| `auto_commit` | no | `true` | Commit and push after running |
| `output` | no | `commit` | For `mode: lint` only: `commit` pushes the lint diff straight to main; `pull-request` opens a PR (also requires `pull-requests: write` permission and the repo setting "Allow GitHub Actions to create and approve pull requests") |

## Environment variables consumed

| Variable | Required for | Source |
|----------|--------------|--------|
| `SLACK_BOT_TOKEN` | `ingest`, `fetch-only` | Slack App Bot Token (`xoxb-...`) |
| `CLAUDE_CODE_OAUTH_TOKEN` | `ingest`, `lint` | `claude setup-token` |

## What lives where

```
theplant/slackwiki                (this repo)
├── action.yml                    composite Action entry point
├── scripts/                      Python: fetch, ingest, lint, init, commit
└── templates/                    CLAUDE.md, config example, wiki seeds, downstream workflows

<company>-wiki                    (per company, private)
├── slackwiki.config.yml          timezone, channel excludes, focus
├── CLAUDE.md                     refreshed from this repo on every run
├── .claude/settings.json         denies writes to raw/
├── raw/                          immutable Slack source (grows daily)
├── wiki/                         LLM-maintained pages (grows daily)
└── state/                        cursors, user cache, new_files.txt
```

## Cron caveats

GitHub Actions cron is UTC-only and **best-effort**, not guaranteed-on-time — runs may be delayed during high-load windows. Pick a time that doesn't overlap typical busy windows (top of the hour is heavily contested) and accept ~5–30 minute slop. Scheduled workflows are auto-disabled after 60 days of repo inactivity; the daily ingest commit keeps activity alive as long as Slack has messages.

## License

MIT — see [`LICENSE`](./LICENSE).
