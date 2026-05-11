"""Fetch new Slack messages and append them to raw/slack/.

- Auto-discovers public (and optionally private) channels the bot is a member of.
- Uses state/cursors.json for per-channel incremental fetch; bootstraps from
  backfill_days when a channel has no cursor.
- Resolves user_id -> handle, caches in state/users.json.
- Pulls thread replies for any parent with reply_count > 0.
- Writes one file per channel per day, bucketed by config timezone.
- Emits state/new_files.txt listing every file written or modified.

Environment:
  SLACK_BOT_TOKEN     required, xoxb-... bot token
  SLACKWIKI_CONFIG    optional, path to config (default: slackwiki.config.yml)
  GITHUB_WORKSPACE    set by GitHub Actions; falls back to "."
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Allow `python scripts/fetch_slack.py` from the action repo to import sibling modules.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_message import render_message  # noqa: E402


REPO_ROOT = Path(os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
CONFIG_PATH = REPO_ROOT / os.environ.get("SLACKWIKI_CONFIG", "slackwiki.config.yml")
STATE_DIR = REPO_ROOT / "state"
RAW_DIR = REPO_ROOT / "raw" / "slack"
CURSORS_PATH = STATE_DIR / "cursors.json"
USERS_PATH = STATE_DIR / "users.json"
CHANNELS_PATH = RAW_DIR / "_channels.json"
NEW_FILES_PATH = STATE_DIR / "new_files.txt"

_USER_REF_RE = re.compile(r"<@([A-Z0-9]+)(?:\|[^>]+)?>")


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        sys.exit(f"slackwiki.config.yml not found at {CONFIG_PATH}")
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f) or {}


def load_json(path: Path, default):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")


def call(method, **kwargs):
    """slack_sdk call with retry on 429."""
    for attempt in range(6):
        try:
            return method(**kwargs)
        except SlackApiError as e:
            if e.response.status_code == 429:
                retry = int(e.response.headers.get("Retry-After", 2 ** attempt))
                print(f"rate limited, sleeping {retry}s", file=sys.stderr)
                time.sleep(retry)
                continue
            raise
    raise RuntimeError("too many rate-limit retries")


def discover_channels(client: WebClient, config: dict) -> list[dict]:
    excludes = set(config.get("channel_excludes") or [])
    types = "public_channel"
    if config.get("include_private_channels"):
        types = "public_channel,private_channel"

    channels: list[dict] = []
    cursor = None
    while True:
        resp = call(
            client.conversations_list,
            types=types,
            exclude_archived=True,
            limit=200,
            cursor=cursor,
        )
        for ch in resp["channels"]:
            if not ch.get("is_member"):
                continue
            if ch["name"] in excludes:
                continue
            channels.append({"id": ch["id"], "name": ch["name"]})
        cursor = (resp.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            break
    return channels


def ensure_user(client: WebClient, users: dict[str, str], uid: str) -> str:
    if uid in users:
        return users[uid]
    try:
        resp = call(client.users_info, user=uid)
        u = resp["user"]
        handle = (
            u.get("profile", {}).get("display_name")
            or u.get("profile", {}).get("real_name")
            or u.get("name")
            or uid
        )
        users[uid] = handle
    except SlackApiError:
        users[uid] = uid
    return users[uid]


def resolve_users_in_message(client: WebClient, users: dict[str, str], msg: dict) -> None:
    if msg.get("user"):
        ensure_user(client, users, msg["user"])
    for uid in _USER_REF_RE.findall(msg.get("text", "") or ""):
        ensure_user(client, users, uid)


def fetch_history(client: WebClient, channel_id: str, oldest: float) -> list[dict]:
    msgs: list[dict] = []
    cursor = None
    while True:
        resp = call(
            client.conversations_history,
            channel=channel_id,
            oldest=str(oldest),
            inclusive=False,
            limit=200,
            cursor=cursor,
        )
        msgs.extend(resp["messages"])
        cursor = (resp.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            break
    msgs.sort(key=lambda m: float(m["ts"]))
    return msgs


def fetch_replies(client: WebClient, channel_id: str, parent_ts: str) -> list[dict]:
    msgs: list[dict] = []
    cursor = None
    while True:
        resp = call(
            client.conversations_replies,
            channel=channel_id,
            ts=parent_ts,
            limit=200,
            cursor=cursor,
        )
        msgs.extend(resp["messages"])
        cursor = (resp.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            break
    return msgs


SKIP_SUBTYPES = {
    "channel_join", "channel_leave", "channel_topic", "channel_purpose",
    "channel_name", "channel_archive", "channel_unarchive",
}


def main() -> int:
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        sys.exit("SLACK_BOT_TOKEN not set")

    config = load_config()
    tz = ZoneInfo(config.get("timezone", "UTC"))
    backfill_days = int(config.get("backfill_days", 7))
    include_threads = bool(config.get("include_threads", True))

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    cursors: dict[str, str] = load_json(CURSORS_PATH, {})
    users: dict[str, str] = load_json(USERS_PATH, {})
    channels_map: dict[str, str] = load_json(CHANNELS_PATH, {})

    client = WebClient(token=token)
    channels = discover_channels(client, config)
    print(
        f"discovered {len(channels)} channels: {[c['name'] for c in channels]}",
        file=sys.stderr,
    )
    for ch in channels:
        channels_map[ch["id"]] = ch["name"]
    save_json(CHANNELS_PATH, channels_map)

    bootstrap_oldest = (
        datetime.now(tz=timezone.utc) - timedelta(days=backfill_days)
    ).timestamp()

    new_files: set[Path] = set()
    total_msgs = 0

    for ch in channels:
        cid, name = ch["id"], ch["name"]
        oldest = float(cursors.get(cid, bootstrap_oldest))
        print(f"#{name}: fetching since ts={oldest:.0f}", file=sys.stderr)
        msgs = fetch_history(client, cid, oldest)
        if not msgs:
            continue

        for m in msgs:
            resolve_users_in_message(client, users, m)

        by_day: dict[str, list[str]] = defaultdict(list)
        for m in msgs:
            if m.get("subtype") in SKIP_SUBTYPES:
                continue
            replies = None
            if (
                include_threads
                and m.get("reply_count", 0) > 0
                and m.get("thread_ts") == m.get("ts")
            ):
                thread = fetch_replies(client, cid, m["ts"])
                for r in thread:
                    resolve_users_in_message(client, users, r)
                replies = thread
            md = render_message(m, users=users, tz=tz, replies=replies)
            day = (
                datetime.fromtimestamp(float(m["ts"]), tz=timezone.utc)
                .astimezone(tz)
                .strftime("%Y-%m-%d")
            )
            by_day[day].append(md)

        for day, blocks in sorted(by_day.items()):
            out = RAW_DIR / name / f"{day}.md"
            out.parent.mkdir(parents=True, exist_ok=True)
            is_new = not out.exists()
            with open(out, "a", encoding="utf-8") as f:
                if is_new:
                    f.write(f"# #{name} — {day}\n\n")
                for b in blocks:
                    f.write(b)
            new_files.add(out)
            total_msgs += len(blocks)

        cursors[cid] = msgs[-1]["ts"]

    save_json(CURSORS_PATH, cursors)
    save_json(USERS_PATH, users)

    rel = sorted(str(p.relative_to(REPO_ROOT)) for p in new_files)
    NEW_FILES_PATH.write_text(("\n".join(rel) + "\n") if rel else "")
    print(f"wrote {len(rel)} raw files, {total_msgs} messages", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
