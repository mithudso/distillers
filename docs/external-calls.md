# External calls

The maintained CLI has two network boundaries. The optional shared client owns
its internal HTTP calls; this repository does not duplicate that transport.
Current code locations are identified by symbol to avoid stale handwritten line
numbers; the generated [operations inventory](operations-registry.json) carries
source metadata.

| Operation / source | Target and data | Trigger | Diagnostic / test / retry policy |
| --- | --- | --- | --- |
| Fetch — `distill_offline.py`, `cmd_fetch` | Caller-selected HTTP(S) URL through curl; response text returns to stdout after HTML cleanup. | `python3 distill_offline.py fetch --url URL` | stderr error and exit 2 on handled failure; isolated tests cover the boundary. curl has `--max-time`; the engine does not add retries. |
| Embedding — `distill_offline.py`, `_ollama_embed`, `_has_model`, `_client` | Configured Ollama hosts via shared client; unit text out, vectors/model metadata in. A missing model may be pulled. | `index`, `novelty`, `merge --semantic`, or default-semantic `bulk` | Fake-Ollama tests and injected failure tests; callers emit explicit error/fallback warnings. Pool failover/retry belongs to the shared client. |

Embedding failures retain lexical merge/novelty/bulk operation. `index` returns an
error instead of claiming a vector index exists. The generated
[tool inventory](tool-inventory.json) describes CLI commands; it is not an MCP
registration or HTTP-route inventory.

## Local persistence boundaries

`cmd_render` writes central JSON/Markdown and best-effort source-adjacent copies.
`split_mirror_to_dir` writes manifest-owned split pages. `cmd_bulk` writes progress,
preview, and master artifacts. `cmd_index` writes flat-JSON vectors. Inspect these
artifacts and retain source documents; successful process exit alone is not a
claim about a downstream datastore. See [CLI operations](cli-and-operations.md).

## Five-standard bootstrap applicability

| Standard | CLI status |
| --- | --- |
| Named trigger / registry | CLI subcommands exist; a generated static operation inventory documents them. There is no generic `ops run` executor. |
| Central structured error sink | Not implemented. The local CLI uses stdout/stderr; no JSONL attempt-history service is claimed. |
| Automatic remediation map | Not implemented. The [fallback runbook](runbooks/embedding-fallback.md) guides operator action; it is not an automatic remediator. |
| Dashboard card | Inapplicable to the shipped CLI; no dashboard is added. |
| Datastore verification | No external datastore is written by these network calls. Local artifacts require inspection; no `DATASTORE_VERIFY_FAILED` service contract is claimed. |

This is an explicitly adapted offline-CLI bootstrap, not a pass against the full
web-service auto-remediation contract. Adding that framework would require a
separate product scope. No model requests, re-embedding, or service installation
are required to generate or check the static inventory.
