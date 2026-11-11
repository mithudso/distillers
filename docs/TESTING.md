# Testing

## Strategy and gates

The suite uses stdlib `unittest`, temporary files, mocks, subprocesses, and a local
fake HTTP server. Tests should assert output, provenance, fallback, failure
behavior, and cleanup for important or changed risky paths. There is no numeric
line-coverage threshold and no blanket 100% coverage requirement.

```bash
python3 -m py_compile distill_offline.py scripts/*.py
python3 -m unittest discover -s tests -v
python3 scripts/generate_repo_docs.py --check
```

These are the core CI gates on Python 3.11 and 3.14. Core jobs explicitly skip
four transport tests that need the optional client; fallback tests still run.
The pinned shared-client repository is private. Authenticated semantic CI is
optional and skipped when unconfigured; see the setup below. Local optional
jobs exercise fake-server transport. No live Ollama, ChromaDB, private corpus or
actual model pull is needed by the tests.

Run one existing suite with:

```bash
python3 -m unittest discover -s tests -p test_ollama_layer.py -v
```

`make check` runs the repository gates. Use `make docs` to regenerate static
metadata and `make docs-check` to check it without changing files.

## Known-docset mirror smoke

When the local Aider sample is present:

```bash
python3 distill_offline.py mirror --in ~/.claude/skills/web-text-mirror/text-mirror/aider.chat.md
```

The sample observed on 2026-11-11 reports 128 pages, 1007829 bytes, and 250711
estimated tokens. `est_tokens` is a character-count heuristic, not a tokenizer
measurement. These observations describe that local file; they do not prove
website completeness. The 127-page figures in historical reports describe an
older run.

## Bulk and provenance integration

Use a disposable fixture or a copied mirror, then run:

```bash
python3 distill_offline.py bulk /path/to/copied-mirror.md --no-semantic
```

Check that retained units and the master preserve page URLs; inspect repeated
runs and changed inputs when altering resume logic. Bulk writes files beside the
input. Never run integration checks against private production artifacts unless
that scope was explicitly authorized.

## Adding tests and limits

Name test modules `test_*.py`. Use `TemporaryDirectory` for outputs, restore
environment changes, and close HTTP servers even after failed assertions.
Inject embedding replies and failures rather than depending on a live model.
For changed logging, assert the emitted diagnostic as well as the result.

The suite verifies engine contracts and fake transport, not embedding quality,
real model compatibility, website completeness, or the availability of downstream
hub/MCP services. Historical semantic acceptance results in `STATUS.md` were not
revalidated by these gates. There is no held-out performance benchmark or empirical
champion promotion surface in this repository.

On local Python 3.15, the pinned optional client can emit upstream HTTPError
cleanup ResourceWarnings during deliberate 404/503 fake-server responses. The
assertions pass. This repository does not modify that separate dependency.

## Authenticated optional CI

The public core jobs need no private dependency or credential. The semantic jobs
run only when repository variable `DISTILL_SEMANTIC_CI` is `true` and repository
secret `OLLAMA_CLIENT_READ_TOKEN` supplies read-only access to the private
`mithudso/ollama-client` repository. The workflow checks out its exact pinned
commit without persisting credentials. Fork PRs never run the authenticated job.
No token or variable was created during bootstrap. With this option unconfigured,
semantic CI is explicitly skipped; validate it locally with the optional extra.
The delivery PR records core and optional-job outcomes separately.
