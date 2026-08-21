# distillers

Offline document-distillation engine — the zero-LLM-token half of a docs-to-skill
pipeline. Takes large text corpora (especially [web-text-mirror](https://github.com/mithudso/web-text-mirror)
docset mirrors) and mechanically reduces them: page splitting, heuristic unit
extraction, exact + semantic deduplication, markdown rendering, vector indexing
and novelty filtering — so an LLM only ever sees the small, genuinely new part.

Part of a larger local pipeline:

```
web-text-mirror ──► distillers ──► semantic index ──► global_ai_hub MCP server
(docset → one .md)  (this repo)    (Ollama+ChromaDB,   (hub_query_docset,
                                    ~/.global-ai-hub)   hub_distill_run, …)
```

## The one script that matters

`distill_offline.py` — stdlib-only Python, no install required. The LLM does
exactly one irreplaceable step (read text, emit classified JSON units);
everything mechanical lives here at zero token cost.

### Subcommands

| Subcommand | Purpose |
| --- | --- |
| `mirror --in M.md [--list \| --split-dir D \| --extract]` | web-text-mirror docset: stats (default), page URLs, per-page split, or heuristic extract with **per-page URL source anchors** |
| `bulk PATH` | whole directory — or a single mirror file, auto-split to `<stem>.pages/` — through the 3-stage offline funnel: exact-hash dedup → (lexical) → semantic embed+cluster → grouped master .md |
| `render --in units.json` | compact units JSON → central `.md`+`.json` + source-adjacent copies |
| `diff --old A --new B` | added/removed hunks (scopes incremental re-distills) |
| `merge --existing E.json [--semantic]` | dedup new units against an existing distillation |
| `index --in dist.json [--name N]` | embed a distillation's units → persistent flat-JSON vector index |
| `novelty --in cand.json [--against N…]` | drop candidates already covered by prior indexes |
| `fetch --url U` / `clean --in F` / `extract --in F` | plain-text ingest helpers (trafilatura-backed HTML stripping, heuristic unit extraction) |

### Mirror format (fixed input contract)

web-text-mirror concatenates a whole docset into one markdown file; each page is
bounded by a banner triple:

```
==========================================================================================
URL: https://example.com/docs/page.html
==========================================================================================
<page text…>
```

`mirror`/`bulk` preserve that per-page provenance: every extracted unit's
`source_anchor` is its originating page URL (`https://…#L<page-local-line>`).

### Configuration (env — never hardcoded)

| Var | Default | Meaning |
| --- | --- | --- |
| `OLLAMA_HOST` | `http://192.168.4.75:11434` | Ollama endpoint for embeddings (embeddings only — never prose) |
| `DISTILL_EMBED_MODEL` | `mxbai-embed-large` | embedding model |

Outputs land in `~/.claude/distillations/` (+ `.index/` for vector indexes).
Every Ollama path degrades gracefully to lexical (difflib) matching when the
host is down.

### Example: distill the Aider docs

```bash
# stats: 127 pages, ~249k tokens
python3 distill_offline.py mirror --in aider.chat.md

# full offline funnel → aider.chat.pages/aider.chat_master.md
python3 distill_offline.py bulk aider.chat.md
# measured: 10,442 raw units → 2,263 exact-unique → 2,066 semantic points
```

## Legacy one-off scripts

`split_master.py`, `categorize_topics.py`, `clean_binary_garbage.py`,
`clean_index_garbage.py` — post-processors written for a specific past corpus
(hardcoded paths/taxonomy). Kept for reference; not part of the general pipeline.

## Related

- `KICKOFF.md` — the build brief this repo was implemented against
- `STATUS.md` / `SUMMARY.md` — build state, design decisions, verification results
- `~/.global-ai-hub` — semantic docset index + `global_ai_hub` MCP server (`hub_distill_run` shells out to this repo)
- `~/.claude/skills/document-distiller-offline/` — the Claude Code skill wrapping this script (its copy is synced FROM this repo; this repo is canonical)
