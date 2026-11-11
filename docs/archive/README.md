# Workflow log archive

`scripts/rotate_workflow_logs.py` preserves older version/prompt sections here
when `memory.md` or `prompts.md` exceeds approximately 200 KB. The current sections
remain in the root logs. The tool must refuse rotation while a corresponding
editor swap file exists. Do not remove archived history merely to reduce size.
