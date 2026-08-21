# Distillers Pipeline — build STATUS

Tracking doc for the KICKOFF.md build. Stage progress, decisions, acceptance set, blockers.
Session: 2026-08-20 (background job). User pre-confirmed proceeding through all stages ("implement all of it").

## Stage progress
- [x] Stage 1 — Recon + plan (5 parallel recon reports; decisions below)
- [ ] Stage 2 — Initialize distillers repo safely
- [ ] Stage 3 — Distiller scripts consume text-mirror output
- [ ] Stage 4 — Semantic indexing (Ollama + vector store)
- [ ] Stage 5 — Generalized MCP server in ~/.global-ai-hub
- [ ] Stage 6 — Wire consuming skills
- [ ] Final — Verification, commits, SUMMARY.md

## Design decisions (Stage 1)

**(a) Index coverage — BOTH layers.**
- Raw mirror page-chunks → new docset index (retrieval; answers "where in the docs is X").
- Distilled units → existing `distill_offline.py index`/`novelty` flat-JSON indexes (dedup/novelty filtering). Unchanged.

**(b) Indexing responsibility split.**
- Embedding core: port `~/dev/llm-memory-pyramid/semantic_index.py`'s `OllamaBackend` pattern (multi-host weighted pool, response validation, content-hash embed cache, stdlib fallback) into `~/.global-ai-hub/scripts/embed_core.py` with hub-neutral env vars (`HUB_OLLAMA_URLS`, `HUB_EMBED_MODEL`).
- Storage: ChromaDB **if it installs cleanly** in the new hub venv (user requested chromadb; python 3.14 wheel availability is the risk); otherwise fall back to the hub's proven SQLite pattern (`hub_sqlite.py` style) and log the substitution here. Either way behind one storage-adapter interface so the choice is swappable.
- `~/dev/net-dns-monitor/scripts/*` used as reference only (single-host, hardcoded — superseded by the pyramid's core). NOT edited.
- llm-memory-pyramid keeps all memory-tier duties; the hub MCP memory tools delegate to `napmem_retrieval_agent.py` / `napmem_mcp_server.py` logic rather than reimplementing.
- No daemon/watcher installs (constraint). `watch_and_index` pattern deferred.

**(c) Acceptance questions (verified against aider.chat.md):**
1. Q: What does the `/architect` in-chat command do? → A: "Enter architect/editor mode using 2 different models. If no prompt provided, switches to architect/editor mode." (source page: docs/usage/commands.html)
2. Q: Which providers does Aider support prompt caching for? → A: "Anthropic (Sonnet and Haiku) and DeepSeek (Chat)." (source page: docs/usage/caching.html)
3. Q: Which env var sets the Anthropic API key? → A: `ANTHROPIC_API_KEY` (docs say Aider uses Claude 3.7 Sonnet by default). (source page: docs/llms/anthropic.html)
Verification bar: for each question, the correct source page appears in top-5 semantic query results.

**(d) Memory-pyramid MCP tool surface:** two read-only tools — `hub_memory_search` (substring/semantic over the pyramid) and `hub_memory_stats` — delegating to llm-memory-pyramid. No write/ingest tools in this pass (ingest stays with naptime/pyramid CLI).

**Other pinned decisions:**
- `EMBED_MODEL` = `mxbai-embed-large` (the ONLY embedding-capable model on 192.168.4.75; also distill_offline.py's existing default). Env-overridable.
- Docset key: `<source hostname>__<mirror filename stem>` (e.g. `aider.chat__aider.chat`). Deterministic.
- Mirror page format (fixed input contract): pages delimited by `=====…` / `URL: <url>` / `=====…` banners; 127 pages in aider.chat.md; per-page source_anchor = the URL.
- MCP server: Python, official `mcp` SDK (FastMCP class), in `~/.global-ai-hub/mcp-server/`, borrowing mdb-context-hub PATTERNS (tool prefix `hub_`, READ_ONLY/WRITE annotations, stdio + optional HTTP, `.mcp.json` at hub root, restart runbook) — not its TypeScript code. Tool named `hub_search_codebase` kept compatible with the hub's stale docs promising `search_codebase`.
- New venv `~/.global-ai-hub/.venv` (python3.14 is externally-managed homebrew) for mcp/chromadb/etc. System python untouched.
- Token counting: bytes/4 heuristic (distill_offline.py convention); tiktoken only if it installs cleanly.
- Git: work on branch `build/pipeline` off remote `main` (remote has 1 commit @ 0ff7f7a). Never push main. One commit per stage per repo.

## Recon facts (load-bearing)
- distillers: `distill_offline.py` (43k, 9 subcommands, env `OLLAMA_HOST` default http://192.168.4.75:11434, `DISTILL_EMBED_MODEL` default mxbai-embed-large, flat-JSON indexes at ~/.claude/distillations/.index). 4 helper scripts are one-off DMT-wiki tools (hardcoded `wiki.dmt-nexus.me/` paths). Local dir NOT a git repo; remote exists (main @ 0ff7f7a).
- Gap for Stage 3: no parser for multi-page mirror files; `extract` anchors are line numbers (no per-page URL provenance); `bulk` assumes one-file-one-doc.
- ~/.global-ai-hub: working indexer stack (hub_lib.py, hub_sqlite.py — SQLite WAL, JSON vectors; idle-indexer.py; hub-daemon.py FastAPI :8000; search.py). NO MCP server; `mcp`/`fastmcp` not installed. Stale docs (.global-ai-context.md, skills/local-semantic-search, docs/MCP.md) promise `search_codebase` tool — build it for real, then fix docs. `libraries/mcp-library/registry.json` empty stub = registration point. Git repo, no remote, 1 commit; big runtime files (hub.db 268MB, indexer.log 617MB) untracked — need .gitignore.
- Environment: python3 = 3.14.7 (homebrew). Installed: trafilatura 2.2.0, fastapi/uvicorn. Missing: chromadb, tiktoken, watchdog, mcp, fastmcp.
- Consuming skills: document-distiller-offline (own 29k copy of distill_offline.py — older than repo's 43k; sync needed), document-distiller (WebFetch-based), /dr = ~/.claude/commands/dr.md (already has local-mirror-first step but reads ~/.claude/skill-consolidation/mirrors/<host>.md — path mismatch with web-text-mirror output), concept-family-explorer (delegates to /dr).

## Blockers / risks
- chromadb on python 3.14: wheel availability unknown → storage-adapter fallback planned (see decision b).
- Workflow tool failing this session ("response stopped arriving" ×10 agents) — using Agent tool instead. Zero results lost.

## Assumption log
- User pre-confirmed all stages; Stage-1 "pause for confirmation" satisfied by that pre-confirmation. Decisions (a)-(d) applied as recommended defaults — flag here for review.
