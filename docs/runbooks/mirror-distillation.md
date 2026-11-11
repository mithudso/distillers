# Process a mirror

## Preconditions

Use Python 3.11+ and a known local web-text-mirror input. Keep the source intact.
Choose a dedicated destination or a disposable copy for write-producing checks.

## Actions

```bash
python3 distill_offline.py mirror --in /path/to/mirror.md
python3 distill_offline.py mirror --in /path/to/mirror.md --list
python3 distill_offline.py mirror --in /path/to/mirror.md --extract
python3 distill_offline.py bulk /path/to/copied-mirror.md --no-semantic
```

For an explicit split destination, use
`mirror --in /path/to/mirror.md --split-dir /path/to/dedicated-pages`.
Do not remove unowned files when a split reports a collision.

## Verification

Check nonzero expected pages, HTTP(S) page URLs, and page URL `source_anchor`
values in extracted units. Inspect the bulk progress index and master for retained
provenance and content. A successfully parsed local file does not prove that the
upstream website is complete. Treat extraction as degraded heuristic candidates.

## Escalation

For malformed input, compare the fixed banner triple in the
[README](../../README.md#mirror-contract). For output conflicts, select a fresh
location and preserve the conflicting directory. Record the redacted command,
exit status and diagnostic when reporting a reproducible engine defect.
