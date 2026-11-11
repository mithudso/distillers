# AGENTS.md — distillers

[CLAUDE.md](CLAUDE.md) is the authoritative shared contributor guidance.
Read it and the [project wiki](docs/wiki/README.md) before changes.

- `distill_offline.py` is canonical. Synchronize the installed skill copy after
  edits, preserving any different local content first.
- The core uses only the standard library. Shared `ollama-client` is optional;
  unavailable embeddings must retain lexical merge/novelty/bulk behavior.
- Read configuration from `OLLAMA_HOST`, `OLLAMA_HOSTS`, and
  `DISTILL_EMBED_MODEL`; do not hardcode private endpoints.
- The fixed mirror banner and per-page `source_anchor` are external contracts.
- Verify syntax, tests, generated documentation, and a known-docset `mirror --in`
  run before delivery. Exact commands are in [CLAUDE.md](CLAUDE.md#commands).
- The four historical helper scripts are frozen one-offs.
- Preserve other agents' edits and private/runtime artifacts. Follow the workflow
  log and delivery rules in [CLAUDE.md](CLAUDE.md).

## Agent inventory

There are no repository-local `.claude/agents/` or `.github/agents/` definitions.
Host-provided reviewers are session tools, not shipped project components. No
external authentication or MCP server is required to run the core checks.

<!-- llms-routing:pointer --> See `## llms routing` in CLAUDE.md for the llms files and quick answers.
