# Distillers Pipeline — build STATUS

Tracking doc for the KICKOFF.md build. Session: 2026-08-20 (background job).
User pre-confirmed proceeding through all stages.

## Stage progress — ALL COMPLETE
- [x] Stage 1 — Recon + plan (5 parallel recon reports; decisions below)
- [x] Stage 2 — distillers repo initialized: `build/pipeline` off origin/main (LICENSE preserved), scripts committed
- [x] Stage 3 — `distill_offline.py mirror` subcommand + mirror-aware extract/bulk; verified on aider.chat.md (127 pages, 10,442 units, per-page URL anchors); bulk funnel end-to-end: 10,442 → 2,263 exact-unique → 2,066 semantic points
- [x] Stage 4 — `~/.global-ai-hub/scripts/embed_core.py` (multi-host Ollama pool) + `docset_indexer.py` (ChromaDB); aider docset indexed: 1,012 chunks, 0 failed (< 5% threshold), model mxbai-embed-large
- [x] Stage 5 — `~/.global-ai-hub/mcp-server/hub_mcp_server.py` (mcp 2.0, 7 tools) + .mcp.json + registry + docs; stdio smoke test: all tools listed, 6/7 PASS (hub_distill_run needs the branch merge below — clean-env spawn saw the pre-merge script)
- [x] Stage 6 — wired: /dr (docset-index-first step), document-distiller (mirror/index-first ingest), document-distiller-offline (SKILL.md + script synced), local-semantic-search (real tool names); concept-family-explorer inherits via /dr

## Verification results
- Distiller: aider.chat.md end-to-end; tokens(raw mirror) 248,761 → tokens(offline heuristic master) ~164,033 (34% reduction from the zero-LLM funnel alone; the LLM classify pass deepens this)
- Index: 1,012/1,012 chunks embedded (0%% failure); acceptance queries — /architect → docs/usage/commands.html rank 1; prompt-caching providers → docs/usage/caching.html rank 1; ANTHROPIC_API_KEY → docs/llms/anthropic.html rank 4 (top-1 was the also-correct docs/config/api-keys.html). ALL PASS (top-5 bar)
- MCP server: starts via stdio, answers all read tools + memory tools; stopped after test
- Adversarial review (2 agents): 2 Critical + 6 High + 8 Medium found → ALL Medium+ fixed and committed (distillers 23838d4, hub a65adb7)

## Design decisions (Stage 1) — as built
- (a) Index covers BOTH layers: raw mirror page-chunks (docset index, ChromaDB) + distilled units (distill_offline's own flat-JSON indexes)
- (b) Embedding core generalized from llm-memory-pyramid's semantic_index.py patterns into embed_core.py (HUB_OLLAMA_URLS weighted pool, default 192.168.4.75=4,localhost=1; HUB_EMBED_MODEL default mxbai-embed-large — the only embed model on the LAN host). net-dns-monitor scripts kept as read-only reference. llm-memory-pyramid keeps memory tiers; hub delegates via napmem_retrieval_agent CLI
- (c) Acceptance questions recorded above and in ~/.claude/jobs/66086bb4/tmp/acceptance.py
- (d) Memory MCP surface: hub_memory_search + hub_memory_stats (read-only)
- Docset key: `<host-slug>__<stem-slug>` (aiderchat__aiderchat)
- MCP: Python mcp 2.0 MCPServer, stdio default + `--http [port]` (127.0.0.1:8787), tool prefix `hub_`, mdb-context-hub patterns

## Remaining / next session
1. `git -C ~/dev/distillers merge --ff-only wt/build` if the wrap-up merge didn't land (then hub_distill_run works from the default DISTILLERS_DIR).
2. Optional: LLM classify pass over the aider extract to produce the reference distilled SKILL package (offline funnel is done; the classify pass is the quality step).
3. Optional: `sko` pass over the 4 touched skills (deferred from hooks); watch_and_index daemon port (explicitly out of scope this run — no daemons).
4. The 4 legacy helper scripts (split_master, categorize_topics, clean_*) remain one-off DMT-wiki tools — left as-is by design.

## Environment facts
- Ollama: 192.168.4.75:11434 (mxbai-embed-large, qwen3.5:35b) + localhost:11434 (mxbai, nomic-embed-text, qwen2.5-coder)
- Hub venv: ~/.global-ai-hub/.venv (python 3.14.7, mcp 2.0.0, chromadb 1.5.9, tiktoken)
- Chroma store: ~/.global-ai-hub/.chroma-docsets ; registry: ~/.global-ai-hub/docsets.db
