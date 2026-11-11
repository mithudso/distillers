# Requirements

## Functional requirements

1. Accept fixed web-text-mirror banners, including single-page mirrors.
2. Preserve source-page provenance for retained and combined units.
3. Parse, extract, diff, merge, render, and process local documents without an LLM.
4. Keep heuristic extraction explicitly labeled as degraded candidate material.
5. Provide lexical operation without third-party runtime packages or Ollama.
6. Delegate optional embedding transport to the shared client; retain content on
   recoverable embedding failures and fail clearly when vector indexing is impossible.
7. Keep local output ownership explicit and avoid overwriting unowned split files.
8. Generate deterministic repository metadata and detect drift in CI.

## Compatibility and quality

The package requires Python 3.11+; CI exercises 3.11 and 3.14. The core uses only
stdlib modules. `fetch` additionally needs curl. There is no service port, database,
Node runtime, background watcher, hardware minimum, enforced latency objective,
or numeric coverage threshold. Semantic clustering can be quadratic in retained
representatives; use bounded corpora and the [optimization reference](caching-and-optimization.md).

## Dependency inventory

| Dependency | Requirement / source | Purpose |
| --- | --- | --- |
| Python | `requires-python` in `pyproject.toml` | Core runtime and stdlib test/tooling stack. |
| setuptools | Build requirement in `pyproject.toml` | Optional package installation/build. |
| `ollama-client` | Optional `semantic` extra, Git commit pinned in `pyproject.toml` | Shared embedding pool/transport. |
| curl | External executable, only for `fetch` | HTTP(S) ingest. |
| GitHub Actions | Commit-pinned workflow actions | Hosted CI checkout and Python setup. |

The manifest and workflow files are authoritative for exact pins. No ChromaDB,
trafilatura, pytest, linter, or type-checker dependency is required here. Historical
external-hub versions are not this package's requirements.
