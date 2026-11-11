# Integrations and assumptions

| Boundary | Configuration / authentication | Data and assumptions |
| --- | --- | --- |
| web-text-mirror input | Caller-selected local file; no auth in this repo. | Fixed banner triples containing HTTP(S) page URLs. Retain source documents. |
| Ollama via optional shared client | `OLLAMA_HOST`, optional `OLLAMA_HOSTS`, and `DISTILL_EMBED_MODEL`; no credential setting is defined here. | Unit text leaves the process for embeddings; trust and secure the selected hosts. Missing models may be pulled. |
| curl fetch | Caller supplies an HTTP(S) URL and timeout. | Returned text is untrusted. No crawler or website-completeness guarantee. |
| Local filesystem | OS user permissions. | Outputs are ordinary files; central distillations, vector indexes, split files and bulk progress can contain source text. |
| Installed skill engine copy | Location varies by skill installation. | Canonical copy lives in this repository; inspect and preserve a divergent installed copy before synchronization. |
| Downstream hub / MCP | Separate repository and configuration. | Historical references only; no live service dependency or health claim here. |

The CLI reads environment settings at startup/import; it does not source `.env`.
The default host is localhost, with model `mxbai-embed-large`. Optional host pools
accept comma-separated endpoints and `url=weight` syntax. CLI thresholds and other
flags come from `main`; see [CLI and operations](cli-and-operations.md).

`render` outputs under `~/.claude/distillations/`; vector indexes use `.index/`.
Bulk outputs sit beside the chosen input. Keep data outside the source checkout
when it is private. Gitignore patterns are convenience rules, not a data-loss or
privacy boundary.

No server/dashboard, Node package, MCP configuration, semantic watcher, or automatic
re-embedding pipeline is introduced by repository bootstrapping. Generated source
indexes are static text/JSON and require no model.
