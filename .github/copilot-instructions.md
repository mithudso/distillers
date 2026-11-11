## Default Execution Strategy

- Read contributor guidance and relevant source before editing.
- Run the repository checks after changes and verify changed risky behavior.
- Use commands and paths established by the repository; do not invent them.
- Follow the workflow log rule in `CLAUDE.md`: request log, memory log, and one
  package patch bump per delivered logical change.
- Preserve unrelated edits and private/runtime data; finish authorized delivery.

## Orientation

Start with `CLAUDE.md`, `docs/wiki/README.md`, `README.md`, and the relevant
architecture/testing/runbook page. `CLAUDE.md` owns shared conventions.

## Build, Test, and Validation Commands

```bash
python3 -m py_compile distill_offline.py scripts/*.py
python3 -m unittest discover -s tests -v
python3 scripts/generate_repo_docs.py --check
python3 distill_offline.py mirror --in /path/to/known-mirror.md
```

Use `make check`, `make test`, `make docs`, and `make docs-check` for repository
workflows. Optional client installation: `python3 -m pip install '.[semantic]'`
in a virtual environment. No linter, type checker, server, or watcher is required.

## High-level Architecture

One importable Python module dispatches CLI commands. It reads local inputs,
preserves source provenance and writes local artifacts. Optional embeddings use
the shared client; fetch uses curl. Downstream hub/MCP services are external.

## Key Conventions

1. The core uses stdlib; the semantic client remains optional.
2. Keep lexical fallback; vector indexing must fail clearly without embeddings.
3. Preserve fixed mirror banners and per-page `source_anchor`.
4. Read endpoint/model configuration from documented environment variables.
5. Keep the four frozen historical helper scripts unchanged unless explicitly scoped.
6. Preserve output ownership and original inputs; use dedicated split directories.
7. Keep sensitive source text, secrets and runtime artifacts out of commits/indexes.
8. Regenerate static metadata and synchronize the actual installed skill copy
   after canonical engine changes, preserving different local content first.
