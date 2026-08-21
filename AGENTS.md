# AGENTS.md — distillers

Instructions for any coding agent working in this repo. `CLAUDE.md` is the
authoritative version of these rules; this file mirrors it for non-Claude
agents.

- `distill_offline.py` is canonical; sync the skill copy at
  `~/.claude/skills/document-distiller-offline/` after edits.
- Stdlib only. Env-driven config (`OLLAMA_HOST`, `DISTILL_EMBED_MODEL`).
  Graceful lexical fallback when Ollama is unreachable.
- Mirror banner format is a fixed external contract; per-page URL
  `source_anchor` provenance must survive every code path.
- Verify with `python3 -m py_compile distill_offline.py` plus a `mirror --in`
  run against a known docset before declaring done.
- Legacy helper scripts are frozen one-offs.
