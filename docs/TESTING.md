# Testing

No CI. This is deliberate — there is nothing to run on a runner beyond
`py_compile`, and the meaningful checks are live verification harnesses against
real corpora and a running Ollama/ChromaDB host, which CI cannot reach. Tests
are run by hand before a commit.

## 1. Compile check

```bash
python3 -m py_compile distill_offline.py
```

## 2. Mirror stats (smoke)

Parse the pinned aider sample and confirm the page/token counts:

```bash
python3 distill_offline.py mirror --in ~/.claude/skills/web-text-mirror/text-mirror/aider.chat.md
# expect: 127 pages, ~249k tokens
```

## 3. Bulk funnel (integration)

Run the whole offline funnel on the same sample and confirm the stage counts:

```bash
python3 distill_offline.py bulk aider.chat.md
# expect: 10,442 raw units → 2,263 exact-unique → 2,066 semantic points
#         → aider.chat.pages/aider.chat_master.md
```

## 4. Acceptance (semantic index, end-to-end)

Owned downstream, not by this repo: `~/.global-ai-hub/scripts/docset_indexer.py`
builds the `aiderchat__aiderchat` docset index (1,012 chunks, <5% embed-failure
gate). The recorded acceptance queries and their expected top-5 source pages
live in `STATUS.md`; all pass at the top-5 bar (2 of 3 at rank 1).
