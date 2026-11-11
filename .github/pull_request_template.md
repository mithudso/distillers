## What changed and why

<!-- Describe the trigger and resulting behavior. Name the engine stage when relevant. -->

## Tests

<!-- Include commands and key results; distinguish local/fake tests from live acceptance. -->

- [ ] `python3 -m py_compile distill_offline.py scripts/*.py`
- [ ] `python3 -m unittest discover -s tests -v`
- [ ] `python3 scripts/generate_repo_docs.py --check`
- [ ] Known-docset `mirror --in` smoke checked
- [ ] Stdlib core, lexical fallback, and per-page provenance preserved
- [ ] Installed skill copy synchronized when engine changed

## Risk

<!-- Note output/schema compatibility, runtime limits, and material unverified paths. -->

## Rollback

<!-- Give the task-specific restore/revert approach; preserve user data and history. -->
