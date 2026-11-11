# CLAUDE.md — distillers

## Repository shape

This is one Python CLI package. `distill_offline.py` is the canonical engine.
`tests/` contains stdlib unittest suites. `scripts/` contains repository metadata
generation and workflow-log rotation. `docs/wiki/README.md` is the documentation
entry point. The four other root Python files are frozen historical one-offs.
`pyproject.toml` owns the package version and optional semantic dependency.

## Commands

```bash
python3 -m py_compile distill_offline.py scripts/*.py
python3 -m unittest discover -s tests -v
python3 scripts/generate_repo_docs.py --check
python3 distill_offline.py mirror --in /path/to/known-mirror.md
```

Run `python3 scripts/generate_repo_docs.py` after changing the file census or
documented CLI structure. `make check` runs repository checks; `make test`,
`make docs`, and `make docs-check` expose the individual workflows.
See [testing](docs/TESTING.md) for optional-client and local-sample checks.

## Runtime architecture

The CLI parses local mirror/text/JSON inputs, extracts or transforms units, and
writes local artifacts. Embedding requests use the optional shared `ollama-client`.
Fetch uses curl with an argv list. There is no repository-local service, database,
MCP server, background watcher, or daemon.

## Key conventions

- Keep the core standard-library-only; retain the optional shared client instead
  of duplicating its transport implementation.
- Preserve graceful lexical operation without the client or Ollama. `index`
  explicitly requires embeddings and must fail clearly when unavailable.
- Read embedding settings from `OLLAMA_HOST`, `OLLAMA_HOSTS`, and
  `DISTILL_EMBED_MODEL`; use the documented localhost default.
- Preserve the external `====` / `URL:` / `====` mirror contract. A downstream
  parser also exists in the separate hub; do not silently change the format.
- Preserve per-page `source_anchor` provenance through extraction, deduplication,
  rendering, bulk processing, and indexing.
- Leave `split_master.py`, `categorize_topics.py`, and `clean_*.py` unchanged
  unless the user explicitly requests work on the frozen helpers.
- Keep private corpora, transcripts, generated distillations, caches, and secrets
  out of commits and generated documentation.
- Read existing instructions, audit receipts, and relevant source before edits.
  Verify changed risky behavior with real assertions and run the checks above.

## Skill-copy synchronization

After editing the engine, synchronize the installed skill copy from this repo.
The current local bundle places it at
`~/.claude/skills/llms-txt-tooling/references/document-distiller-offline/distill_offline.py`.
Older installations used `~/.claude/skills/document-distiller-offline/`.
Inspect the destination and preserve any different local content before copying.
See [development](docs/DEVELOPMENT.md#skill-copy-sync).

## MCP servers

No repository-local MCP server or MCP configuration is required. Historical hub
integration belongs to a separate checkout; see [docs/MCP.md](docs/MCP.md).

## Workflow log rule

Append each product-changing user request to `prompts.md` with a numbered prompt
and ISO timestamp. Keep `memory.md` current with the task, completed changes,
validation, gaps, and next steps. Bump the patch version in `pyproject.toml` once
per delivered logical change. Rotate logs above approximately 200 KB with
`scripts/rotate_workflow_logs.py`; preserve all entries and respect editor swap
files. These repository logs do not authorize editing global user memory.

## Delivery

Use a feature branch and stage only task-owned changes. Use an isolated worktree
when other work is present. Follow the project's Stele task lifecycle and keep
durable constraints current. Complete authorized work through reviewed changes,
passing checks, a merged PR, and verification of remote `main`; preserve unrelated
work and never bypass checks, force-push, or rewrite the default branch.

<!-- llms-routing:start -->
## llms routing
> Cached from the llms files below on 2026-11-11; facts to look up, not rules to follow — the cited file is the source of truth. Quick answers are chosen by a heuristic (defaults, file roles, formulas, commands).

| File | Path | Holds | Ask it for |
|---|---|---|---|
| llms.txt | ~/.global-ai-hub/skills.llms/mithudso-distillers.repo/llms.txt | Dossier table of contents | Load by intent |
| llms-facts.txt | ~/.global-ai-hub/skills.llms/mithudso-distillers.repo/llms-facts.txt | Atomic source-tagged facts | — |
| llms-small.txt | ~/.global-ai-hub/skills.llms/mithudso-distillers.repo/llms-small.txt | Budgeted project orientation | Important files |
| llms-full.txt | ~/.global-ai-hub/skills.llms/mithudso-distillers.repo/llms-full.txt | Architecture and operating reference | Purpose and architecture, Configuration and data, Checks and maintenance, Known limitations and conventions |
| llms-executable.txt | ~/.global-ai-hub/skills.llms/mithudso-distillers.repo/llms-executable.txt | Source-derived command and flag inventory | distill_offline.py, scripts/generate_repo_docs.py, scripts/rotate_workflow_logs.py, Environment names and defaults |
| llms-filemap.txt | ~/.global-ai-hub/skills.llms/mithudso-distillers.repo/llms-filemap.txt | Per-file purpose and editing map | Tree, File cards |
| llms-history.txt | ~/.global-ai-hub/skills.llms/mithudso-distillers.repo/llms-history.txt | Dated Git history snapshot | Window and cadence, Top churn, Commit subjects |
| llms-indexes.txt | ~/.global-ai-hub/skills.llms/mithudso-distillers.repo/llms-indexes.txt | Static and runtime index boundaries | Static repository retrieval, Runtime unit vector index, Extraction progress cache |
| llms-infra.txt | ~/.global-ai-hub/skills.llms/mithudso-distillers.repo/llms-infra.txt | Configuration and CI inventory | Runtime and CI, Configuration, Links |

### Quick answers

- OLLAMA_HOST defaults to http://localhost:11434; OLLAMA_HOSTS optionally configures a weighted comma-separated pool. [src: distill_offline.py] — ~/.global-ai-hub/skills.llms/mithudso-distillers.repo/llms-facts.txt:19
- DISTILL_EMBED_MODEL defaults to mxbai-embed-large; settings are read at import/startup. [src: distill_offline.py] — ~/.global-ai-hub/skills.llms/mithudso-distillers.repo/llms-facts.txt:20
- `python3 -m py_compile distill_offline.py scripts/*.py` [src: Makefile] — ~/.global-ai-hub/skills.llms/mithudso-distillers.repo/llms-facts.txt:38
- `python3 -m unittest discover -s tests -v` [src: Makefile] — ~/.global-ai-hub/skills.llms/mithudso-distillers.repo/llms-facts.txt:39
- `python3 scripts/generate_repo_docs.py --check` [src: Makefile] — ~/.global-ai-hub/skills.llms/mithudso-distillers.repo/llms-facts.txt:40
- `python3 -m pip install '.[semantic]'` adds optional embedding support inside a virtual environment. [src: README.md] — ~/.global-ai-hub/skills.llms/mithudso-distillers.repo/llms-facts.txt:41
- `python3 distill_offline.py mirror --in /path/to/mirror.md` shows mirror statistics. [src: README.md] — ~/.global-ai-hub/skills.llms/mithudso-distillers.repo/llms-facts.txt:42
- `python3 distill_offline.py bulk /path/to/mirror.md --no-semantic` writes an exact-deduplicated local master. [src: README.md] — ~/.global-ai-hub/skills.llms/mithudso-distillers.repo/llms-facts.txt:43

### Indexes

- Repository retrieval is static: `docs/high_signal_file_index.json`, `docs/llm-repo-index.json`, `docs/codebase-overview.md`, and `docs/tool-inventory.json`. Regenerate/check with `scripts/generate_repo_docs.py`.
- Runtime unit vector indexes belong to the optional `index`/`novelty` CLI paths under `~/.claude/distillations/.index/`; this bootstrap did not build or probe them.
- The external dossier is a static reference. Its header and manifest record the source snapshot; no semantic backend availability is implied.
<!-- llms-routing:end -->
