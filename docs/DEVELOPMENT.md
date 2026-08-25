# Development

## Setup

None. `distill_offline.py` is stdlib-only Python 3 — no venv, no `pip install`,
no `requirements.txt`. Clone and run.

Ollama is optional and reached over HTTP via `urllib`; every embedding path
degrades to lexical (`difflib`) matching when the host is down. Configure it by
environment, never in code:

| Var | Default | Meaning |
| --- | --- | --- |
| `OLLAMA_HOST` | `http://192.168.4.75:11434` | embedding endpoint (embeddings only) |
| `DISTILL_EMBED_MODEL` | `mxbai-embed-large` | embedding model |

## Verify

```bash
python3 -m py_compile distill_offline.py
python3 distill_offline.py mirror --in ~/.claude/skills/web-text-mirror/text-mirror/aider.chat.md   # 127 pages
```

See `docs/TESTING.md` for the full check set (funnel integration + acceptance).

## Skill-copy sync (required after editing `distill_offline.py`)

`distill_offline.py` is CANONICAL here. The copy in
`~/.claude/skills/document-distiller-offline/` is synced FROM this repo — after
changing the script here, re-copy it there so the skill and the engine stay
identical.

A near-identical mirror-banner parser also lives in
`~/.global-ai-hub/scripts/docset_indexer.py` by design (no cross-repo import).
When the `====` / `URL:` banner contract changes, update both parsers together.

## Frozen code

`split_master.py`, `categorize_topics.py`, `clean_binary_garbage.py`,
`clean_index_garbage.py` are one-off DMT-wiki tools with hardcoded paths — leave
them as-is unless explicitly asked to touch them.
