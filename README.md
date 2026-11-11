# distillers

An offline document-distillation CLI for reducing text corpora into source-anchored
knowledge units. It splits web-text-mirror docsets, extracts heuristic units,
deduplicates, renders Markdown, and optionally uses Ollama embeddings for semantic
matching. The core runs on Python 3.11+ with the standard library.

## Quick start

```bash
git clone https://github.com/mithudso/distillers.git
cd distillers
python3 distill_offline.py mirror --in /path/to/mirror.md
python3 distill_offline.py mirror --in /path/to/mirror.md --extract
python3 distill_offline.py bulk /path/to/mirror.md --no-semantic
```

`mirror` defaults to JSON statistics. `--extract` produces explicitly degraded
heuristic candidates; an LLM classification pass is a separate workflow. `bulk`
writes a split directory, progress index, preview, and master beside the input.
Use a dedicated output location and retain the original source.

## Commands

All commands start with `python3 distill_offline.py`.

| Subcommand | Purpose |
| --- | --- |
| `mirror --in M.md` | Show statistics; use `--list`, `--split-dir D`, or `--extract` for page URLs, page files, or source-anchored units. |
| `bulk PATH --no-semantic` | Process a directory, document, or mirror with exact deduplication and no embedding requests. |
| `bulk PATH` | Add semantic clustering when the optional client and Ollama are available; retain units when embeddings fail. |
| `render --in units.json` | Write central JSON/Markdown and best-effort source-adjacent copies. |
| `diff --old A --new B` | Emit added and removed line groups as JSON. |
| `merge --existing E.json --new-units N.json` | Fold near-duplicate new units into an existing distillation; `--semantic` opts into embeddings. |
| `index --in dist.json --name N` | Persist an embedding index; requires the optional client and reachable Ollama. |
| `novelty --in cand.json --against N` | Filter candidates against prior indexes, with lexical fallback. |
| `fetch --url https://example.com` | Fetch HTTP(S) text through curl and strip HTML. |
| `clean --in F` / `extract --in F` | Clean local HTML or extract heuristic candidate units. |

See the [CLI and operations reference](docs/cli-and-operations.md) for defaults,
output locations, and side effects.

## Configuration

Set these in the process environment. The CLI does not load `.env` automatically.

| Variable | Default | Meaning |
| --- | --- | --- |
| `OLLAMA_HOST` | `http://localhost:11434` | Single Ollama embedding endpoint. |
| `OLLAMA_HOSTS` | unset | Comma-separated pool, optionally `url=weight`; overrides the single endpoint. |
| `DISTILL_EMBED_MODEL` | `mxbai-embed-large` | Embedding model. |

Install the optional shared client in a virtual environment with
`python3 -m pip install '.[semantic]'`. The core has no required runtime package.
Merge, novelty, and bulk retain lexical behavior if embeddings are unavailable;
`index` returns an error because a vector index requires embeddings. A missing
embedding model may be pulled by the client integration. Use `--no-semantic` for
a bulk run that must make no embedding or model-download requests.

## Mirror contract

Each page starts with the fixed web-text-mirror banner:

```text
==========================================================================
URL: https://example.com/docs/page.html
==========================================================================
<page text>
```

The delimiter lines contain at least ten `=` characters. Single-page mirrors
are valid. Retained units carry page URL provenance in `source_anchor`;
deduplication must preserve the sources it combines. This repository adapts to
the banner contract owned by web-text-mirror.

## Architecture and documentation

`distill_offline.py` is the canonical importable engine and CLI. The optional
shared `ollama-client` owns embedding transport. Downstream semantic stores and
MCP services live in other repositories; this repository installs no server,
daemon, or watcher. See [architecture](docs/ARCHITECTURE.md).

- [Project wiki](docs/wiki/README.md): commands, scripts, references, and maintenance strategy.
- [Installation](docs/INSTALLATION.md), [onboarding](docs/onboarding.md), and [development](docs/DEVELOPMENT.md).
- [Testing](docs/TESTING.md), [security](docs/SECURITY.md), and [contributing](CONTRIBUTING.md).
- [Components](docs/COMPONENTS.md), [file map](docs/codebase-overview.md), and [requirements](docs/requirements.md).
- [Integrations](docs/integrations-and-assumptions.md), [external calls](docs/external-calls.md), and [MCP boundary](docs/MCP.md).
- [Logging](docs/logging.md), [optimization](docs/caching-and-optimization.md), and [known limitations](docs/known-issues.md).
- [Mirror runbook](docs/runbooks/mirror-distillation.md), [fallback runbook](docs/runbooks/embedding-fallback.md), and [release/rollback](docs/runbooks/release-and-rollback.md).

`KICKOFF.md`, `STATUS.md`, and `SUMMARY.md` are historical build records. Their
August 2026 measurements and external-service descriptions are not current
acceptance results. The four root helper scripts (`split_master.py`,
`categorize_topics.py`, and `clean_*.py`) are frozen corpus-specific one-offs.

## License

[Apache License 2.0](LICENSE).
