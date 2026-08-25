# CLAUDE.md — distillers

## What this repo is
Offline document-distillation engine (`distill_offline.py`, stdlib-only Python).
The zero-LLM-token half of the docs-to-skill pipeline: mirror parsing, heuristic
extraction, exact+semantic dedup, rendering, vector indexing, novelty filtering.
See `README.md` for the full subcommand table and `docs/ARCHITECTURE.md` for the
pipeline it belongs to.

## Ground rules
- `distill_offline.py` is CANONICAL here. The copy in
  `~/.claude/skills/document-distiller-offline/` is synced FROM this repo —
  after changing it here, re-copy it there.
- Stdlib only in `distill_offline.py`. No new dependencies; Ollama is reached
  via `urllib`, and every Ollama path must degrade gracefully to the lexical
  path when the host is down.
- Config via env, never hardcoded: `OLLAMA_HOST` (default
  `http://192.168.4.75:11434`), `DISTILL_EMBED_MODEL` (default
  `mxbai-embed-large`).
- The mirror banner format (`====` / `URL: <url>` / `====`) is a fixed input
  contract owned by web-text-mirror — adapt this repo to it, never the reverse.
  A near-identical parser lives in `~/.global-ai-hub/scripts/docset_indexer.py`
  by design (no cross-repo import); keep the two in sync when the format moves.
- Per-page URL provenance is sacred: every extracted unit carries a
  `source_anchor` traceable to its page. Don't add code paths that drop it.
- Legacy scripts (`split_master.py`, `categorize_topics.py`, `clean_*.py`) are
  one-off DMT-wiki tools — leave them alone unless explicitly asked.

## Verify
```bash
python3 -m py_compile distill_offline.py
python3 distill_offline.py mirror --in ~/.claude/skills/web-text-mirror/text-mirror/aider.chat.md   # 127 pages
```
Acceptance harness (semantic index end-to-end): see `STATUS.md` and
`~/.global-ai-hub/scripts/docset_indexer.py`.

## Git
- Default branch: `main` on github.com/mithudso/distillers. Work on feature
  branches; sole-maintainer repo.
- One commit per logical stage, stage named in the message.
