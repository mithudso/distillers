# Components

## Engine

The public CLI dispatcher is `main(argv=None)` in
[`distill_offline.py`](../distill_offline.py). The module is also importable; its
leading-underscore helpers are implementation details.

| Region / symbols | Inputs and outputs | Side effects and dependencies |
| --- | --- | --- |
| `parse_mirror`, `docset_key`, `split_mirror_to_dir` | Banner Markdown to page records, identity, or page files. | Split writes to a dedicated caller-selected directory and tracks owned files. |
| `cmd_extract`, `cmd_mirror` | Text/mirrors to JSON units, page URLs, statistics, or split files. | Stdlib parsing; retained units keep page provenance. |
| `render_markdown`, `cmd_render` | Classified JSON to Markdown/JSON artifacts. | Central output plus best-effort file-source-adjacent copy. |
| `cmd_diff`, `cmd_merge` | File differences or new/existing units to JSON. | Optional embeddings for semantic merge; lexical fallback. |
| `cmd_index`, `cmd_novelty` | Unit JSON and stored indexes to vectors or novel/matched units. | Local vector storage; optional shared client. `index` requires embeddings. |
| `cmd_fetch`, `cmd_clean` | URL or local HTML/text to plain text. | Fetch invokes curl; HTML stripping uses stdlib `HTMLParser`. |
| `cmd_bulk`, `clean_and_split`, `categorize` | Directory/document/mirror to deduplicated master. | Local progress/preview/master outputs; optional embedding requests. |

Example import:

```python
from distill_offline import parse_mirror, render_markdown
pages = parse_mirror(mirror_text)
markdown = render_markdown(distillation_data)
```

## Tooling and tests

`scripts/generate_repo_docs.py` generates the file map, retrieval index, and
operation/tool inventory from repository sources; `--check` detects drift.
`scripts/rotate_workflow_logs.py` archives older workflow-log sections without
losing entries. The Makefile exposes `check`, `test`, `docs`, and `docs-check`.
The `.github/workflows/ci.yml` job runs the checks in supported Python/client
core jobs and optional authenticated semantic jobs. `tests/` owns isolated behavioral and fake-Ollama coverage.

See [the generated file map](codebase-overview.md) for the complete path census.
No standalone `lib/` split is required: the canonical engine module is directly
importable and existing skill consumers depend on that file.

## Frozen helpers

`split_master.py`, `categorize_topics.py`, `clean_binary_garbage.py`, and
`clean_index_garbage.py` are corpus-specific historical scripts. They use hardcoded
paths and perform writes at module import. Do not import or run them as library
components. They remain unchanged unless explicitly scoped by the user.

## Dependency direction

The engine optionally imports the shared client. Tests import the engine and
inject local inputs or fake transport. Repository tooling reads source metadata;
the engine does not depend on that tooling. Downstream hub stores and MCP servers
are consumers in other repositories, not dependencies of the CLI.
