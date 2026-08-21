# Docs-to-Skill Distillation Pipeline — build kickoff

## Goal
Build an end-to-end, mostly-offline pipeline that turns a complete textual mirror of a company's documentation suite into a token-lean, reusable distilled skill package: mirror → distill → semantically index → serve via MCP. Local/self-hosted components only: trafilatura (extraction), Ollama (embeddings), ChromaDB (vector store). Success: for a given docset, the pipeline produces a distilled, source-anchored skill artifact (per the document-distiller conventions) that answers docset questions without re-reading the full mirror, with measured token savings (see Verification).

## Components and roles
| Path / repo | What it is | Treatment |
|---|---|---|
| `~/dev/web-text-mirror` (github.com/mithudso/web-text-mirror) | Mirrors a whole docset into a single markdown file; effectively complete — its current output format is the fixed input contract for this pipeline | Read-only; build against its output format |
| `/Users/mitch.hudson/.claude/skills/web-text-mirror/text-mirror/aider.chat.md` | Sample mirror output — should be the complete Aider chat docs; verify completeness before relying on it. If incomplete, re-run web-text-mirror against the Aider docs to regenerate it, and note that in STATUS.md | Test input for the distiller; its distillation becomes the reference example of correct output |
| `~/dev/distillers` (github.com/mithudso/distillers.git) | Offline distillation scripts | Primary modify target; repo needs initializing (Stage 2 safety rules) |
| `~/dev/llm-memory-pyramid` | Indexing of files and folders — part of the indexing layer | Integrate; modify as needed. Decide in the Stage 1 plan how it divides responsibility with `semantic_indexer.py` (e.g., traversal/watching vs embedding/query) |
| `~/dev/net-dns-monitor/scripts/` — `semantic_indexer.py`, `install_indexer_daemon.sh`, `mcp_server.py`, `query_index.py`, `watch_and_index.py` | Working reference implementations of indexing / watching / MCP serving | Port + generalize into `~/.global-ai-hub`; do NOT edit in place |
| `~/.global-ai-hub` (incl. `scripts/`) | LLM-agnostic central hub — final home of generalized indexer + MCP server; already has a decent amount in place | Inventory first, then extend; preserve existing content |
| `~/dev/mdb-context-hub` | Existing MCP hub whose tool-registration pattern this generalizes | Read-only design reference |

## Stages — do in order (later stages depend on earlier interfaces)
1. **Recon + plan.** Inventory `~/.global-ai-hub` and `~/dev/distillers`; inspect mdb-context-hub's MCP pattern and the text-mirror output format via aider.chat.md. Read-only recon sub-tasks may run in parallel (subagents fine); keep inventory to top-level structure and key entry points, not file-by-file review. Write a short stage-by-stage plan that records these design decisions, then pause once for my confirmation: (a) what the semantic index covers — raw mirror chunks, distilled units, or both (recommend both: raw chunks for retrieval, distilled units for dedup/novelty filtering); (b) the split of responsibility between `semantic_indexer.py` and llm-memory-pyramid; (c) 2–3 factual acceptance questions drawn from distinct sections of aider.chat.md, with answers verified against the mirror text, recorded in STATUS.md as the acceptance set; (d) the exact scope of the memory-pyramid MCP tool surface (see Stage 5). After the plan is confirmed, proceed through Stages 2–6 without further pausing unless a Constraint below is triggered. Think the Stage 4 embedding-target design and Stage 5 tool surface through carefully in this plan — they are hard to unwind later.
2. **Initialize the distillers repo safely.** Check the remote first (`git ls-remote https://github.com/mithudso/distillers.git`). If the remote has content and the local `~/dev/distillers` is empty, clone. If the local directory is non-empty (it is — it's a working directory), `git init` + add the remote + fetch; reconcile local files against remote HEAD without discarding either side, and show me the diff before overwriting any pre-existing file. Never force-push; confirm with me before any history-altering git operation.
3. **Update the distiller scripts** so each offline stage does as much work as possible in scripts (zero/low model tokens), consuming web-text-mirror's single-markdown output directly (the format is fixed — adapt the distillers to it, not the reverse). The docset/mirror file path is a required script argument, never hardcoded — aider.chat.md is only the test input. Output is the distilled, source-anchored skill artifact described in Goal. Test end-to-end on aider.chat.md.
4. **Semantic indexing.** Generalize the indexing layer (per the Stage 1 decision) to embed via Ollama into ChromaDB, covering the layers decided in the plan. My Ollama host is `192.168.4.75` — read host, embedding model, and any ports from config/env (e.g. `OLLAMA_HOST`, `EMBED_MODEL`) in all delivered code, never hardcode. If `EMBED_MODEL` is unset, pick an embedding model actually available on the host, record the choice in STATUS.md, and use that recorded choice as the default thereafter. If the host has no embedding-capable model installed, list what is available in STATUS.md and ask before pulling one. Maintain one shared index per docset, keyed deterministically by `<source hostname>__<mirror filename>`; consuming skills reuse it rather than re-embedding.
5. **Generalized MCP server in `~/.global-ai-hub`.** Expose the pipeline as MCP tools modeled on mdb-context-hub but LLM-agnostic — at minimum: kick off a mirror/distill run, index a file/folder/docset, query the semantic index, list indexed docsets, and memory-pyramid processing (ingest/refresh a file or folder into the memory index — exact surface per the Stage 1(d) decision). Bind to localhost; port from config/env with a stated default. Do not install/enable any daemon (the `install_indexer_daemon.sh` pattern) or leave any service running without my explicit confirmation — starting the server briefly for the Verification smoke test is allowed without asking, provided you stop it afterward.
6. **Update the consuming skills** — document-distiller / distill-offline, /dr, and concept-family-explorer — to use both the text-mirror output and the semantic index (via the MCP tools) when gathering source material, instead of re-fetching or re-reading full documents. If a consuming skill needs a docset that has no index yet, it should invoke the Stage 5 mirror/distill/index tools first.

## Constraints
- Ask before destructive or hard-to-reverse actions: force pushes, deleting/overwriting existing content in `~/.global-ai-hub` or `~/dev/distillers`, daemon installs, leaving services running.
- If several independent ambiguities block progress, batch your clarifying questions into one message rather than guessing silently; log any assumption you do make.
- Every distilled output unit keeps a source anchor back to the mirrored markdown (file + section), matching the existing document-distiller convention.
- When porting reference code, preserve its working semantics; generalize interfaces rather than redesigning wholesale.

## Verification — definition of done per stage
- **Distiller:** processes aider.chat.md end-to-end; output non-empty and source-anchored; report tokens(raw mirror) vs tokens(distilled output), counted with the project's existing token-count utility if one exists, else tiktoken cl100k_base.
- **Index:** build succeeds against the Ollama host with at least 95% of chunks embedded (failures logged in STATUS.md); for each Stage 1(c) acceptance question, a query derived from it returns the correct source section within the top 5 results.
- **MCP server:** starts and answers a smoke-test call for each exposed tool (then stop it).
- **Skills:** distill-offline (or /dr) answers the STATUS.md acceptance questions via the index, correctly, without loading the whole mirror.

Run each stage's check before moving to the next. If a check still fails after two fix attempts, document the blocker in STATUS.md and move on to work that is NOT downstream of the failed stage — stages that depend on it stay blocked until it is fixed.

## Failure handling
- Ollama host unreachable or embedding calls failing: retry up to 3 times with short backoff (~5s/15s/30s); then log the failure (including which chunks failed, for partial index builds) in STATUS.md and continue with work that doesn't need embeddings — never fail silently or block everything on it.
- MCP server fails to start (e.g., port conflict on the default) or one tool fails its smoke test: log the specific failure in STATUS.md and continue smoke-testing the remaining tools rather than blocking the stage.
- Missing/inaccessible path or repo: report exactly what's missing and continue with the remaining independent work.

## Deliverables
- Committed code in `distillers` (and any other touched repos), plus the generalized scripts + MCP server in `~/.global-ai-hub`. Commit convention: one commit per completed stage per repo, stage named in the message.
- A `STATUS.md` in `~/dev/distillers` tracking stage progress, decisions, acceptance questions, and blockers so a future session can resume.
- A final summary written to `~/dev/distillers/SUMMARY.md` and echoed in the final message: one section per repo touched, run commands in a code block, and a token-savings table (raw mirror vs distilled, per docset).

## Assumptions you may treat as decided (I'll correct if wrong)
- "Reusable skill" is literal: each docset's distillation lands as a source-anchored skill artifact (document-distiller conventions), not just a queryable index.
- Stage 6's scope is exactly as written above — point the existing skills at the mirror + index; no broader retraining.
- No hard token budget: success is the reported reduction vs the raw mirror, not a fixed number.
- All six stages are in scope; if scope must be cut, Stages 1–4 take priority.
