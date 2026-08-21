# Docs-to-Skill Distillation Pipeline — build summary (2026-08-20)

End-to-end pipeline delivered: **mirror → distill → semantically index → serve via MCP**, all local/self-hosted (trafilatura, Ollama, ChromaDB).

## ~/dev/distillers (github.com/mithudso/distillers, branch `build/pipeline`)
- Repo initialized safely off the existing remote (LICENSE preserved, no force-push).
- `distill_offline.py` gained first-class **web-text-mirror docset support**:
  - `mirror` subcommand — `--stats` (default) / `--list` / `--split-dir D` / `--extract`; parses the `====` / `URL: <url>` / `====` page banners; every extracted unit's `source_anchor` is its originating page URL.
  - `bulk <mirror.md>` auto-splits a mirror into `<stem>.pages/` so the 3-stage offline funnel keeps per-page provenance.
  - Review-hardened: re-runs never ingest bulk's own outputs; single-page mirrors accepted; stale page files cleared; `https?://`-anchored banner regex; mirror parse happens before HTML sniffing.
- Legacy one-off scripts (split_master, categorize_topics, clean_*) untouched by design.

## ~/.global-ai-hub (branch `main`)
- `scripts/embed_core.py` — generalized Ollama embedding core: weighted multi-host pool (`HUB_OLLAMA_URLS`, default `192.168.4.75=4,localhost=1`), response validation, 64-text sub-batches, bounded retries, fail-fast on 4xx. `HUB_EMBED_MODEL` default `mxbai-embed-large`.
- `scripts/docset_indexer.py` — chunks mirror pages (paragraph-aware, 1200/200), embeds via the pool, stores one **ChromaDB collection per docset** (key `<host>__<stem>`; SQLite fallback; registry in `docsets.db`). CLI: `index` / `query` / `list`. Queries always embed with the docset's recorded model.
- `mcp-server/hub_mcp_server.py` — **global_ai_hub MCP server** (official `mcp` 2.0 SDK; stdio default, `--http [port]` on 127.0.0.1): `hub_search_codebase`, `hub_index_docset`, `hub_query_docset`, `hub_list_docsets`, `hub_distill_run`, `hub_memory_search`, `hub_memory_stats`. Wired via `.mcp.json`, registered in `libraries/mcp-library/registry.json`; `docs/MCP.md` and `.global-ai-context.md` now describe reality.
- New venv `.venv/` (python 3.14): mcp 2.0.0, chromadb 1.5.9, tiktoken.

## Skills wired (mirror + index first, fetch last)
- `/dr` (`~/.claude/commands/dr.md`) — checks `hub_list_docsets`/`hub_query_docset` before mirrors, mirrors before live fetches.
- `document-distiller` — ingest checks local mirrors + docset index before WebFetch.
- `document-distiller-offline` — SKILL.md documents `mirror`/`bulk`; its `distill_offline.py` copy synced from this repo (canonical here).
- `local-semantic-search` (hub skills repo) — points at the real `hub_*` tools.
- `concept-family-explorer` — inherits via `/dr` (its research is delegated there).

## Run commands
```bash
# mirror stats / split / heuristic extract (per-page URL anchors)
python3 ~/dev/distillers/distill_offline.py mirror --in <mirror.md> [--list|--split-dir D|--extract]
# full offline funnel on a mirror
python3 ~/dev/distillers/distill_offline.py bulk <mirror.md>
# index + query a docset
~/.global-ai-hub/.venv/bin/python ~/.global-ai-hub/scripts/docset_indexer.py index <mirror.md>
~/.global-ai-hub/.venv/bin/python ~/.global-ai-hub/scripts/docset_indexer.py query <docset> "question" --top 5
# MCP server (stdio; or --http 8787)
~/.global-ai-hub/.venv/bin/python ~/.global-ai-hub/mcp-server/hub_mcp_server.py
# register with Claude Code
claude mcp add global_ai_hub -- ~/.global-ai-hub/.venv/bin/python ~/.global-ai-hub/mcp-server/hub_mcp_server.py
```

## Token savings (aider.chat docset, measured)
| Artifact | Est. tokens (bytes/4) |
|---|---|
| Raw mirror (127 pages) | 248,761 |
| Offline heuristic master (bulk funnel, zero LLM tokens) | 164,033 (−34%) |
| Semantic query answer path (`hub_query_docset`, top-5 chunks) | ~1,500 per question (−99.4% vs reading the mirror) |

Index: 1,012 chunks, 0 embed failures. Acceptance: 3/3 questions return the correct source page in top-5 (2× rank 1).
