# MCP boundary

This repository ships no MCP server, registered MCP tool, MCP authentication, or
required MCP development configuration. `.mcp.json` and `.vscode/mcp.json` are
intentionally absent.

A separate local hub historically invoked this CLI and indexed its output. The
August 2026 records in `KICKOFF.md`, `STATUS.md`, and `SUMMARY.md` describe that
integration; they do not establish its current installation, tool inventory, or
health. Verify the downstream checkout and its own documentation before using it.

If adding an MCP wrapper, keep it separately scoped: define authentication,
transport, argument validation, data ownership, write permissions, and independent
server tests. The offline engine and core checks must continue to run without it.
