# Development

## Setup

Use Python 3.11 or newer. The core requires no third-party runtime package. Git
and an optional `make` installation support the contributor workflow. curl is
needed only for `fetch`.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m unittest discover -s tests -v
```

For optional fake-Ollama integration tests and semantic use:

```bash
.venv/bin/python -m pip install -e '.[semantic]'
.venv/bin/python -m unittest discover -s tests -v
```

The optional extra uses the shared dependency pinned in `pyproject.toml`.
Tests use local fakes; no live Ollama, model download, or ChromaDB is required.
No dev server, hot reload, watcher, formatter, linter, or type checker is required
or configured. Syntax compilation, behavior tests, and metadata drift checks are
the enforced gates.

## Commands

```bash
python3 -m py_compile distill_offline.py scripts/*.py
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s tests -p test_ollama_layer.py -v
python3 scripts/generate_repo_docs.py
python3 scripts/generate_repo_docs.py --check
```

Stage intended new files before regenerating; the generator reads only the Git
index census and never includes arbitrary untracked notes.

`make check`, `make test`, `make docs`, and `make docs-check` provide these
workflows through the repository Makefile. See [testing](TESTING.md) for the
known-docset smoke command and coverage policy. CI runs syntax, behavior tests,
and metadata checks on Python 3.11 and 3.14. Optional authenticated client CI
requires the explicit repository setting and read-only secret described in
[testing](TESTING.md#authenticated-optional-ci); it is skipped when unconfigured.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `OLLAMA_HOST` | `http://localhost:11434` | Single embedding host. |
| `OLLAMA_HOSTS` | unset | Comma-separated pool; optional `url=weight`; takes precedence. |
| `DISTILL_EMBED_MODEL` | `mxbai-embed-large` | Embedding model. |

The CLI reads the process environment at import/startup. `.env.example` documents
settings; the CLI does not load `.env` files. Run `bulk --no-semantic` to avoid
embedding requests. A missing model may be downloaded during semantic use.

## Change workflow

Read [CLAUDE.md](../CLAUDE.md), then trace the relevant CLI and helper functions.
Use a feature branch and isolate unrelated shared work. First reproduce a real
behavior defect, add focused assertions for risky changes, then implement the
smallest supported correction. Keep the fixed banner format, unit provenance,
stdlib core, and fallback behavior intact. Update docs and generated inventories
with changes; do not touch the frozen historical helpers without explicit scope.

Append the request and result to the repository workflow logs and bump the
package patch version once per delivered logical change. Make PR descriptions
state behavior, verification, risks, and rollback. Follow the
[release runbook](runbooks/release-and-rollback.md) through remote verification.

## Skill-copy sync

`distill_offline.py` is canonical here. The current local skill installation uses
`~/.claude/skills/llms-txt-tooling/references/document-distiller-offline/distill_offline.py`.
Older installations used `~/.claude/skills/document-distiller-offline/`.
Inspect the installation, preserve a different existing copy outside the repo,
then copy the verified engine into the actual installed location. Confirm byte
identity with `cmp`. Do not replace unrelated skill instructions.

## Troubleshooting

- Optional integration tests skipped: install `.[semantic]` in the interpreter
  running the suite; the core and absent-library fallback remain testable.
- Embeddings unavailable: use the [fallback runbook](runbooks/embedding-fallback.md).
- Generated-document drift: run the generator, inspect its diff, then check again.
- Mirror split refuses a destination: use a dedicated directory; do not delete
  another person's files to make the command succeed.
- Old bulk measurements differ: verify the input and flags. Historical sample
  figures are not a fixed acceptance contract.
