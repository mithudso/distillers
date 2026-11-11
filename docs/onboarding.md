# Onboarding

1. Read the [README](../README.md) and [project wiki](wiki/README.md).
2. Use [installation](INSTALLATION.md) to run the stdlib core; add the semantic
   extra only when you need embedding integration.
3. Read [CLAUDE.md](../CLAUDE.md), the [architecture](ARCHITECTURE.md), and
   [components](COMPONENTS.md) before changing code.
4. Run [the checks](TESTING.md) and a known-mirror statistics command.
5. Trace one `main` dispatcher branch into its `cmd_*` function. Keep the mirror
   format, source anchors, local output ownership, and lexical fallback intact.
6. Use the [contribution workflow](../CONTRIBUTING.md) and
   [release runbook](runbooks/release-and-rollback.md) to deliver a change.

The historical root reports describe an earlier cross-repository build. The four
helper scripts are frozen and should not be imported or used as onboarding demos.
