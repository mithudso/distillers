# Distillers project wiki

This wiki is the maintained entry point to the repository's verified commands,
scripts, references, and maintenance strategy. The linked documents own the
details; this page does not duplicate a second set of instructions.

## Start and understand

- [README](../../README.md): purpose, quick start, command overview and configuration.
- [Installation](../INSTALLATION.md) and [onboarding](../onboarding.md): first run.
- [Architecture](../ARCHITECTURE.md), [components](../COMPONENTS.md),
  [file map](../codebase-overview.md), and [requirements](../requirements.md).
- [Contributor guidance](../../CLAUDE.md), [agent inventory](../../AGENTS.md),
  and [contribution workflow](../../CONTRIBUTING.md).

## Commands and scripts

| Intent | Reference / command |
| --- | --- |
| Validate a change | [Testing](../TESTING.md); `make check`. |
| Run isolated tests | `python3 -m unittest discover -s tests -v`. |
| Refresh static metadata | `python3 scripts/generate_repo_docs.py` or `make docs`. |
| Detect index/inventory drift | `python3 scripts/generate_repo_docs.py --check` or `make docs-check`. |
| Rotate large workflow logs | `scripts/rotate_workflow_logs.py`; preserves old sections in `docs/archive/`. |
| Operate the CLI | [CLI and operations](../cli-and-operations.md). |
| Synchronize an installed engine | [Skill-copy sync](../DEVELOPMENT.md#skill-copy-sync). |

## Operating runbooks

- [Mirror processing](../runbooks/mirror-distillation.md).
- [Unavailable embeddings](../runbooks/embedding-fallback.md).
- [Delivery and rollback](../runbooks/release-and-rollback.md).

## References and project strategy

- [Integrations and assumptions](../integrations-and-assumptions.md),
  [external-call boundaries](../external-calls.md), and [MCP applicability](../MCP.md).
- [Security](../SECURITY.md), [logging](../logging.md),
  [optimization](../caching-and-optimization.md), and [known limitations](../known-issues.md).
- [Repository memory log](../../memory.md) and [request log](../../prompts.md).

The maintenance strategy is to preserve fixed mirror banners and per-page
provenance, retain stdlib lexical operation, reuse optional shared transport, and
fix corroborated behavior defects with isolated tests. Keep static inventories
current without starting a watcher, embedding run, or downstream service.
Historical build records remain evidence about their dated run; current source
and checks establish current behavior.

When a command, source boundary, or script changes, update its authoritative page,
regenerate inventories, run checks, and verify this navigation still reaches it.
