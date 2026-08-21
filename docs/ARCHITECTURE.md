# Docs-to-Skill Distillation Pipeline — Architecture

Built and verified 2026-08-20. This document is the extensive record of what
exists, why each design decision was made, and how the pieces connect.

## 1. The problem

A complete textual mirror of a documentation suite (e.g. the Aider docs:
127 pages, ~249k tokens) is far too large to hand an LLM whole, and re-reading
it per question wastes tokens. The pipeline turns such mirrors into:

1. a **distilled, source-anchored reference artifact** (deduped knowledge units,
   each traceable to its source page), and
2. a **semantic index** answering "which pages/chunks are relevant to X?" for
   ~1.5k tokens per question instead of a full read,

with all heavy lifting done by local components (trafilatura, Ollama
embeddings, ChromaDB) at zero LLM-token cost.

## 2. Component map

```
┌──────────────────┐   one .md per docset    ┌──────────────────────┐
│  web-text-mirror  │ ───────────────────────► │  distillers (this)   │
│  trafilatura BFS  │   ====/URL: banners     │  distill_offline.py  │
└──────────────────┘                          └──────────┬───────────┘
                                                  units / pages
                                                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       ~/.global-ai-hub                              │
│  scripts/embed_core.py      weighted multi-host Ollama pool         │
│  scripts/docset_indexer.py  chunk → embed → ChromaDB per docset     │
│  mcp-server/hub_mcp_server.py  global_ai_hub MCP server (7 tools)   │
│  hub.db + idle-indexer      pre-existing file-corpus index          │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ MCP (stdio / localhost HTTP)
                               ▼
        consuming skills: /dr · document-distiller(-offline) ·
        concept-family-explorer (via /dr) · local-semantic-search
```

### 2.1 web-text-mirror (read-only input contract)

Mirrors a whole docset into ONE markdown file. Page delimiter (fixed contract):

```
========================================================================== (≥10 =)
URL: https://host/path.html
========================================================================== (≥10 =)
```

### 2.2 distillers (`~/dev/distillers`)

`distill_offline.py` — stdlib-only CLI. Mirror-aware since this build:

- `mirror` subcommand: `--stats` / `--list` / `--split-dir` / `--extract`;
  units carry `source_anchor = <page-url>#L<page-local-line>`.
- `bulk <mirror.md>`: auto-splits to `<stem>.pages/` (numbered `NNN_slug.md`
  files) then runs the 3-stage offline funnel — exact-hash dedup →
  semantic embed+cluster (Ollama) → grouped master markdown.
- Pre-existing subcommands (render/diff/merge/index/novelty/fetch/clean/extract)
  unchanged: they serve the LLM-assisted distillation loop of the
  document-distiller-offline skill.

Robustness decisions (from adversarial review): bulk re-runs glob only
numbered page files (never their own outputs); single-page mirrors are valid;
stale page files are cleared on re-split; banner URLs must be `http(s)://`;
mirror parsing runs before HTML sniffing.

### 2.3 Hub embedding core (`~/.global-ai-hub/scripts/embed_core.py`)

Generalized from llm-memory-pyramid's `semantic_index.py` patterns:

- `HUB_OLLAMA_URLS` weighted pool, default
  `http://192.168.4.75:11434=4,http://192.168.4.1:11434=2,http://localhost:11434=1`
  (linux box → M5 → local fallback), all verified serving `mxbai-embed-large`.
- Response-shape validation (embeddings travel over plain LAN HTTP — never
  trust a malformed reply into an index), consistent-dimension check.
- 64-text sub-batches, timeout scaled to batch size, bounded retries
  (3 backoff rounds), fail-fast on non-retryable 4xx.

### 2.4 Docset indexer (`~/.global-ai-hub/scripts/docset_indexer.py`)

- Chunks pages paragraph-aware (~1200 chars, 200 overlap, min 40 chars).
- One **ChromaDB collection per docset** (cosine space) at
  `~/.global-ai-hub/.chroma-docsets`; registry (pages, chunks, model, backend)
  in SQLite `~/.global-ai-hub/docsets.db`. SQLite vector fallback when Chroma
  is unavailable (`HUB_DOCSET_BACKEND=sqlite|chroma` to force).
- Docset identity: `<host-slug>__<filename-stem-slug>` (e.g.
  `aiderchat__aiderchat`) — deterministic, so re-indexing updates in place and
  consuming skills share one index instead of re-embedding.
- Queries always embed with the model **recorded for that docset** — a query
  embedded with a different model is in a different vector space.
- Index build aborts (nothing written) if >5% of chunks fail to embed.

### 2.5 MCP server (`~/.global-ai-hub/mcp-server/hub_mcp_server.py`)

Official `mcp` 2.0 SDK (`MCPServer`), Python, in the hub venv. Patterns
borrowed from mdb-context-hub (tool prefix, read/write annotations, dual
transport, localhost trust) without porting its TypeScript.

| Tool | Kind | Backing |
| --- | --- | --- |
| `hub_search_codebase` | read | pre-existing hub.db file index (hub_lib's own embedding model) |
| `hub_index_docset` | write | subprocess → docset_indexer (venv) |
| `hub_query_docset` | read | in-process docset_indexer, docset's recorded model |
| `hub_list_docsets` | read | registry |
| `hub_distill_run` | write | subprocess → distillers `distill_offline.py` (stats/list/extract/split/bulk) |
| `hub_memory_search` / `hub_memory_stats` | read | subprocess → llm-memory-pyramid retrieval agent |

Security model: localhost-only (stdio client-spawn; `--http [port]` binds
127.0.0.1, default 8787). Subprocesses run as argv lists (no shell); free-text
values pass as `--flag=value` so they cannot be parsed as extra flags;
control characters rejected. No daemon installation — the server is started on
demand and the smoke-test contract requires stopping it afterward.

### 2.6 Consuming skills (wired mirror/index-first)

- **/dr** (`~/.claude/commands/dr.md` step 6): check `hub_list_docsets` →
  `hub_query_docset` first, then local mirrors, then live fetch.
- **document-distiller**: ingest checks mirrors + docset index before WebFetch.
- **document-distiller-offline**: documents `mirror`/`bulk`; its script copy is
  synced from this repo.
- **concept-family-explorer**: inherits via /dr (research is delegated there).
- **local-semantic-search** (hub skills repo): points at the real `hub_*` tools.

## 3. Data flow for one docset (measured, Aider docs)

| Step | Artifact | Size |
| --- | --- | --- |
| Mirror | `aider.chat.md` | 127 pages, ~249k tokens |
| Offline funnel | `aider.chat_master.md` | 10,442 units → 2,263 exact-unique → 2,066 semantic points (~164k tokens) |
| Semantic index | `aiderchat__aiderchat` collection | 1,012 chunks, 0 embed failures |
| Query path | `hub_query_docset` top-5 | ~1.5k tokens per question |

Acceptance (top-5 bar): 3/3 questions returned the correct source page
(2× rank 1). Questions + expected pages live in `STATUS.md`.

## 4. Operational notes

- **Venv:** `~/.global-ai-hub/.venv` (python 3.14; mcp 2.0.0, chromadb 1.5.9,
  tiktoken). `mcp-server/requirements.txt` pins the set.
- **Registration:** `~/.global-ai-hub/.mcp.json` (stdio) or
  `claude mcp add global_ai_hub -- ~/.global-ai-hub/.venv/bin/python
  ~/.global-ai-hub/mcp-server/hub_mcp_server.py`.
- **Runbooks:** `~/.global-ai-hub/mcp-server/README.md` (start/restart/setup),
  `~/.global-ai-hub/docs/MCP.md` (tool inventory + env config).
- **Git:** this repo → github.com/mithudso/distillers; the hub →
  github.com/mithudso/global-ai-hub (private). Runtime state (hub.db, logs,
  chroma dirs, venv) is gitignored in both.

## 5. Deliberate non-goals of this build

- No daemons/launchd installs (watch-and-index deferred; start things on demand).
- No auth on the MCP server (localhost trust; add auth before any off-box exposure).
- Legacy DMT-wiki helper scripts left as frozen one-offs.
- The LLM classify pass (turning the offline extract into the polished distilled
  skill package) is the designed next step, not part of the offline engine.
