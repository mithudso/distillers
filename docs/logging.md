# Logging

The CLI writes command results and bulk progress to stdout. JSON-producing commands
reserve stdout for their result. Warnings and errors go to stderr, including
lexical fallback, failed file reads, embedding failures, and source-adjacent copy
failures. Invalid inputs generally return exit code 2 through `main`'s handled
error path.

The engine has no persistent centralized log file, logging daemon, remote sink,
structured JSONL attempt history, or dashboard. Its structured artifacts include
unit JSON and bulk/vector indexes; these are output data, not an audit log.

When adding diagnostics, name the operation and failure outcome. Keep stdout
parseable for JSON commands. Test meaningful warning/error paths with captured
stderr and assert the associated result or exit status. Avoid logging document
bodies, credentials, tokens, environment values, or secret-bearing URLs.

Existing diagnostic context can include paths and endpoint information. Review
stderr before sharing it. For a failed run, retain the command with sensitive
arguments removed, exit status, relevant warning, and artifact counts locally.
Use [the fallback runbook](runbooks/embedding-fallback.md) or
[the security policy](../.github/SECURITY.md) as appropriate.
