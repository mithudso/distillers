# Diagnose embedding fallback

## Preconditions

Retain original inputs and prior indexes. Determine whether the command requires
vectors (`index`) or supports lexical operation (`merge`, `novelty`, `bulk`).
No service or daemon needs restarting for core operation.

## Actions

Check that the interpreter has the optional `.[semantic]` extra when embeddings
are intended. Inspect the configured host/model setting names without printing
private values into shared logs. Use `bulk --no-semantic` for a run that should
avoid all embedding/model-download requests. Semantic use may pull a missing
model; do not enable it merely to diagnose an offline core path.

If a host is unavailable, merge and novelty fall back to lexical matching. Bulk
retains units whose embeddings failed. `index` must return an error instead of
claiming a vector index was created. Avoid deleting or rebuilding historical
vectors as a troubleshooting shortcut.

## Verification

Inspect stderr for the explicit fallback/error and stdout/artifacts for the
retained units. Run `python3 -m unittest discover -s tests -v` for local fake and
injected-failure coverage. Those tests do not establish live model health.

## Escalation

If fallback loses content or provenance, report a minimal nonsensitive fixture,
redacted command and expected/actual result. If the issue is a host, model or
shared-client behavior, investigate that component in its own scope. Do not change
stored model identities to force incompatible vectors to compare.
