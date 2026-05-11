"""Format Claude Code's --output-format=stream-json events as one-line log entries.

Used by ingest.py and lint.py to surface what Claude is doing in CI logs:
each tool call, each tool result (with FAIL markers on errors), each text
chunk, and the final cost / duration summary.

Exports `format_line(raw_json_line)` for streaming use, and also runs as a
CLI filter when invoked directly (reads stdin).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime


def _stamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _truncate(s: str, n: int = 140) -> str:
    s = " ".join(str(s).split())
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"


def _tool_key(name: str, inp: dict) -> str:
    """Pick the most informative single field per tool for human display."""
    if name in ("Read", "Edit", "Write", "NotebookEdit"):
        return inp.get("file_path", "")
    if name == "Bash":
        return inp.get("command", "")
    if name == "Grep":
        return f"pattern={inp.get('pattern','')} path={inp.get('path','')}"
    if name == "Glob":
        return inp.get("pattern", "")
    if name == "Agent":
        return inp.get("description", inp.get("subagent_type", ""))
    if name == "WebFetch":
        return inp.get("url", "")
    if name == "TaskCreate":
        return inp.get("subject", "")
    return json.dumps(inp, ensure_ascii=False) if inp else ""


def format_line(raw: str) -> None:
    """Print one formatted log line for one stream-json event."""
    raw = raw.rstrip("\n")
    if not raw.strip():
        return
    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        print(f"[{_stamp()}] [RAW   ] {_truncate(raw)}", flush=True)
        return

    t = event.get("type")
    if t == "system":
        sub = event.get("subtype", "")
        model = event.get("model", "")
        print(f"[{_stamp()}] [SYS  ] {sub} model={model}", flush=True)

    elif t == "assistant":
        msg = event.get("message", {}) or {}
        for block in msg.get("content", []) or []:
            btype = block.get("type")
            if btype == "text":
                text = block.get("text", "")
                if text.strip():
                    print(f"[{_stamp()}] [CLAUDE] {_truncate(text, 240)}", flush=True)
            elif btype == "tool_use":
                name = block.get("name", "?")
                inp = block.get("input") or {}
                print(
                    f"[{_stamp()}] [TOOL ] {name:<8} {_truncate(_tool_key(name, inp), 160)}",
                    flush=True,
                )

    elif t == "user":
        # tool_result messages come back as a user-role event
        msg = event.get("message", {}) or {}
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if block.get("type") == "tool_result":
                    is_error = block.get("is_error", False)
                    cval = block.get("content", "")
                    if isinstance(cval, list):
                        text = " ".join(
                            c.get("text", "")
                            for c in cval
                            if isinstance(c, dict) and c.get("type") == "text"
                        )
                    else:
                        text = str(cval)
                    marker = "FAIL" if is_error else "OK  "
                    print(f"[{_stamp()}] [RES {marker}] {_truncate(text, 140)}", flush=True)

    elif t == "result":
        sub = event.get("subtype", "")
        duration = event.get("duration_ms", 0)
        cost = event.get("total_cost_usd")
        if cost is None:
            cost = event.get("cost_usd", 0)
        try:
            cost_str = f"${float(cost):.4f}"
        except (TypeError, ValueError):
            cost_str = f"${cost}"
        print(
            f"[{_stamp()}] [DONE ] {sub} duration={duration}ms cost={cost_str}",
            flush=True,
        )

    else:
        label = (t or "UNK").upper()
        print(f"[{_stamp()}] [{label:<6}] {_truncate(raw, 200)}", flush=True)


def main() -> int:
    for raw in sys.stdin:
        format_line(raw)
    return 0


if __name__ == "__main__":
    sys.exit(main())
