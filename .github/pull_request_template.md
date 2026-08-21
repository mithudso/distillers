## Summary

<!-- What changed and why. Name the pipeline stage if this touches distill_offline.py. -->

## Verification

<!-- Paste the commands you ran and their key output. See docs/TESTING.md. -->

- [ ] `python3 -m py_compile distill_offline.py` passes
- [ ] `mirror --in <sample>` stats unchanged (or intended change noted above)
- [ ] `bulk` funnel stage counts checked when the funnel path changed
- [ ] Stdlib-only preserved (no new dependencies)
- [ ] Per-page `source_anchor` provenance preserved
- [ ] Skill copy re-synced to `~/.claude/skills/document-distiller-offline/` if `distill_offline.py` changed
