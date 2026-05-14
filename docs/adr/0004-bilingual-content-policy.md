# Bilingual content policy: prose English, proper nouns transliterated

The original "all wiki content is English" rule was doing two jobs at once and the second was undefined. Split into two explicit policies:

**Policy 1 — Prose language.** All narrative, descriptions, summaries, decision text, frontmatter values are English. Non-English source-message text is paraphrased into English in the body and preserved in a `> quote` block. (Unchanged behaviour; given an explicit name.)

**Policy 2 — Proper noun handling.** Internal names (theplant people, projects, services, vendors that theplant integrates with, established team-wide English terms) are used verbatim in their established team-wide English form (`Kakuyasu`, `JMA`, `Veritrans`). When in doubt, romanise. Place / product names in a non-Latin script are paraphrased into English in the body and preserved in a `> quote` block once per page on first mention — same shape as Policy 1.

Customer-side PII handling (originally drafted as Policy 3) is deliberately deferred — the project is not ready to commit to a token format or a redaction mode, and a wrong default would either leak names or burden every page with bookkeeping that doesn't pay off yet. Revisit when there is concrete need.

Alternative considered and rejected: *status quo, single "all English" rule with Claude exercising judgement*. That produced inconsistent treatment in the existing wiki (some non-English terms quote-blocked, some bare, some honorific-stripped) and was unenforceable at lint time. Naming the two policies separately gives lint and the entity-detection rules a place to land.
