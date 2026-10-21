# Development

## Setup

`distill_offline.py` needs only the shared `ollama-client` library for
embeddings (without it every embedding path falls back to lexical):

```bash
python3 -m venv .venv && .venv/bin/pip install -e ~/dev/libraries/ollama-client
.venv/bin/python -m unittest discover -s tests -v   # Ollama layer, fake server
```

Ollama is optional and reached over HTTP via `urllib`; every embedding path
degrades to lexical (`difflib`) matching when the host is down. Configure it by
environment, never in code:

| Var | Default | Meaning |
| --- | --- | --- |
| `OLLAMA_HOST` | `http://localhost:11434` | embedding endpoint (embeddings only) |
| `OLLAMA_HOSTS` | unset | comma-separated host pool (`url=weight` optional); overrides `OLLAMA_HOST` |
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
