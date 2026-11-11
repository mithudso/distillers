# Deliver or roll back a change

## Preconditions

Identify the task-owned diff, current branch, worktree ownership, and remote
`main`. Preserve unrelated edits and private/runtime artifacts. Use an isolated
worktree when necessary. Read [contributing](../../CONTRIBUTING.md).

## Delivery actions

1. Review the complete task diff. Run `make check` and the applicable known-mirror
   smoke. Confirm intended behavior and source provenance.
2. Regenerate static metadata, update workflow logs/version, and synchronize the
   installed engine when changed, preserving any divergent local copy first.
3. Stage task-owned paths, commit descriptively, push the branch, and open/update
   its PR with final scope, validation, risks and rollback.
4. Wait for checks on the final pushed commit. Fix failures and routine conflicts
   without discarding either side's work. Merge only when checks pass.
5. Confirm the PR is merged and its content is on remote `main`. Fetch and safely
   synchronize a clean compatible local default branch. Remove only this task's
   clean merged branch/worktree. Complete the tracker after verified delivery.

Do not force-push, rewrite `main`, bypass protection, or merge another unfinished
task. If access or required checks block delivery, retain a pushed recoverable
branch/PR and record the exact blocker.

## Rollback and verification

Reproduce the regression with a focused test. For shipped code, prepare a revert
or corrective PR and pass the same checks; do not rewrite remote history. Restore
only task-owned files from the run's external snapshot when local rollback is
needed. Preserve user data and newer shared work. Re-synchronize the installed
engine if the verified canonical script changes again.

Confirm reverted/corrected content on remote `main`, rerun the relevant scenario,
and update the task and durable lesson with the concrete trigger.

## Escalation

Stop destructive actions when ownership is uncertain. Record failed checks,
credential/access errors, or branch-protection requirements without weakening
safeguards or presenting queued auto-merge as a completed delivery.
