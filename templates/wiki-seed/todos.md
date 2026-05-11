---
type: todos
---

# Todos

Open items surfaced by lint that require authorial judgment. The ingest pass
reads this file every run and tries to close items based on new Slack messages.

Format:
- Each item is a single line: `- [ ] YYYY-MM-DD — **<action>**. <context with [[wiki-links]]>`
- When an item is closed, change `- [ ]` to `- [x]`, strike it through, append `(resolved YYYY-MM-DD in [[sources/YYYY-MM-DD-slack]])`, and move it under `## Resolved`.

## Open

_None yet._

## Resolved

_None yet._
