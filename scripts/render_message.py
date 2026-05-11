"""Render a Slack message dict to markdown.

The output format is consumed by Claude during ingest, so it must be stable.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


_USER_RE = re.compile(r"<@([A-Z0-9]+)(?:\|[^>]+)?>")
_CHANNEL_RE = re.compile(r"<#[A-Z0-9]+\|([^>]+)>")
_LINK_LABELED_RE = re.compile(r"<((?:https?|mailto):[^|>]+)\|([^>]+)>")
_LINK_BARE_RE = re.compile(r"<((?:https?|mailto):[^>]+)>")


def _resolve_mentions(text: str, users: dict[str, str]) -> str:
    def user_repl(m: re.Match) -> str:
        uid = m.group(1)
        return f"@{users.get(uid, uid)}"
    text = _USER_RE.sub(user_repl, text)
    text = _CHANNEL_RE.sub(r"#\1", text)
    return text


def _resolve_links(text: str) -> str:
    text = _LINK_LABELED_RE.sub(r"[\2](\1)", text)
    text = _LINK_BARE_RE.sub(r"\1", text)
    return text


def _unescape(text: str) -> str:
    return text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")


def clean_text(text: str, users: dict[str, str]) -> str:
    """Resolve Slack-flavored markup into plain markdown."""
    return _unescape(_resolve_links(_resolve_mentions(text, users))).strip()


def _format_time(ts: str, tz: Any) -> str:
    dt = datetime.fromtimestamp(float(ts), tz=timezone.utc).astimezone(tz)
    return dt.strftime("%H:%M")


def _author(msg: dict, users: dict[str, str]) -> str:
    uid = msg.get("user") or msg.get("bot_id") or "unknown"
    return users.get(uid, uid)


def render_message(
    msg: dict,
    *,
    users: dict[str, str],
    tz: Any,
    replies: list[dict] | None = None,
) -> str:
    """Render one Slack message (with optional thread replies) as a markdown block."""
    ts = msg.get("ts", "0")
    lines: list[str] = [
        f"## {_format_time(ts, tz)} — @{_author(msg, users)}     <!-- ts={ts} -->",
        "",
    ]

    body = clean_text(msg.get("text", ""), users)
    if body:
        lines.append(body)
        lines.append("")

    for f in msg.get("files") or []:
        name = f.get("name", "file")
        permalink = f.get("permalink") or f.get("url_private", "")
        mimetype = f.get("mimetype", "")
        size = f.get("size")
        size_str = f", {size:,} bytes" if isinstance(size, int) else ""
        lines.append(f"- attached: [{name}]({permalink}) ({mimetype}{size_str})")
    if msg.get("files"):
        lines.append("")

    real_replies = [r for r in (replies or []) if r.get("ts") != ts]
    if real_replies:
        lines.append(f"> **thread ({len(real_replies)} replies)**")
        for r in real_replies:
            r_time = _format_time(r.get("ts", "0"), tz)
            r_author = _author(r, users)
            r_body = " ".join(clean_text(r.get("text", ""), users).splitlines()).strip()
            lines.append(f"> - {r_time} @{r_author}: {r_body}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n\n"
