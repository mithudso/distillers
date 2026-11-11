# Architecture

## Context

Distillers is one offline Python CLI and importable module. It converts local text,
HTML, mirror Markdown, and classified JSON units into smaller artifacts. A caller
may use these artifacts in an LLM classification workflow. The engine does not
call an LLM or generate prose through a model.

```text
web-text-mirror or local documents
              |
              v
 distill_offline.py CLI / Python module
  | parse / extract / dedup / render |
  |                |                |
  v                v                v
stdout JSON     local files    optional ollama-client
                                | embeddings only
                                v
                         configured Ollama hosts
```

`fetch` is a separate ingest path: curl retrieves a caller-selected HTTP(S) URL,
then stdlib HTML parsing strips markup. The operating-system user owns input and
output access. No service, daemon, watcher, or database is installed here.

## Components and data flow

The [component reference](COMPONENTS.md) maps the engine's functional regions.
The CLI parses arguments in `main`, then dispatches to one `cmd_*` function.

1. `parse_mirror` recognizes fixed banner triples and retains page URLs.
2. Mirror extraction creates page-local `source_anchor` values. Bulk processing
   splits mirrors into a dedicated page directory and preserves page provenance.
3. Exact hashing reduces repeated bulk units. Optional embeddings cluster retained
   representatives; failed embeddings must not delete extracted units.
4. `render_markdown` renders supplied unit JSON without an LLM pass. `index`
   persists unit vectors; `novelty` compares later candidates with prior indexes.
5. Callers consume stdout or local artifacts. Other repositories may ingest the
   results into their own semantic stores or MCP services.

## Storage and configuration

`render` writes under `~/.claude/distillations/` and tries a source-adjacent copy
for file sources. Unit vector indexes live in its `.index/` directory. Bulk
progress, previews, split pages, and masters live beside the selected input.
See [CLI and operations](cli-and-operations.md) before a write-producing command.

Embedding configuration comes from `OLLAMA_HOST`, `OLLAMA_HOSTS`, and
`DISTILL_EMBED_MODEL`. The optional shared client owns host pooling, retries,
model probing, and embedding transport. Standard-library lexical operation
remains available without that client or a reachable host. Vector indexing
requires actual embeddings and fails explicitly when they are unavailable.

## Architectural decisions

| Decision | Reason |
| --- | --- |
| Keep one canonical importable module. | Existing skills and callers consume this script directly; avoid packaging-dependent core operation. |
| Keep mirror banners fixed. | web-text-mirror owns the external format. |
| Retain page provenance throughout transforms. | A reduced unit must remain traceable to its source. |
| Delegate optional Ollama transport. | Reuse the shared client instead of maintaining a second pool/retry implementation. |
| Keep generated metadata deterministic and checked. | CI detects stale file/CLI inventories without a live model. |
| Keep legacy helpers frozen. | They are corpus-specific historical programs with import-time side effects. |
| Generate static indexes without a watcher. | Documentation maintenance must not silently start embeddings or background work. |

## Constraints and historical evidence

Semantic clustering compares representatives pairwise and can be expensive for
large corpora. No latency or throughput target is enforced. Input/output artifacts
are ordinary local files; use dedicated locations and retain original inputs.
See [security](SECURITY.md), [testing](TESTING.md), and
[caching and optimization](caching-and-optimization.md).

`KICKOFF.md`, `STATUS.md`, and `SUMMARY.md` describe the August 2026 cross-repo
pipeline build. Their external tools, package versions, LAN hosts, and acceptance
figures are historical evidence, not live guarantees about another checkout.
