# Token efficiency

## Context discipline
- Read only the files/sections needed for the task; never scan the repo broadly.
- Prefer targeted grep for a symbol over opening whole files; open large files by line range.
- Never echo long file contents, logs, or diffs into the chat; summarize and cite paths/line numbers.
- Delegate verbose operations (test runs, log analysis, doc fetching, exploration) to subagents; return only a short summary to the main thread.
- Prefer CLI tools (gh, aws, etc.) over MCP servers when both can do the job.

## Editing
- Surgical edits only: diffs/string replacement, never full-file rewrites for partial changes.
- Do exactly what was asked; no speculative refactoring — suggest improvements in one line max.
- Test the minimal relevant path; full suite only on request.
- On failure: report the exact error + one proposed fix; max two retries.

## Output
- Terse replies: no restating the request, no plan narration for simple tasks, no boilerplate comments.

# Compact instructions
When compacting, preserve: current task goal, files changed, decisions made,
failing tests with exact errors, commands already run, next actions.
Drop: abandoned exploration paths, repeated logs, resolved discussions.

# Session state
At major milestones, update PROJECT_STATE.md (decisions, files changed, open
issues, next action) so a fresh session can resume from it after /clear.

# Model routing
- Before dispatching a subagent, or choosing how to run a stretch of work, follow
  `docs/MODEL_GUIDANCE.md`: it names the model and effort per kind of task here, and the
  token-saving rules that were measured, not guessed.
- Never run this project on Opus 5 — Opus 5.5 is newer and cheaper on every axis, cache reads
  included, and cache reads dominate this project's bill.
- Record each stretch of work in the log: `python3 scripts/model_log.py append ...`
  (`docs/model_usage/README.md`). The `rework_of` field is what tells a later review whether a
  cheap choice was really cheap.
- A review every three days compares the log with the guidance and rewrites the guidance from what
  the log shows. Do not edit the routing table from opinion between reviews.

# Scope: only the two Base models move
- Owner, 2026-11-13: the imaging-based and the combined models are FROZEN, "without changing
  anything", until he says otherwise. Work, verify and publish only Base · Male and Base · Female.
- Frozen at their published versions: Combined · Male v88, Combined · Female v101, Imaging-based ·
  Male v166, Imaging-based · Female v156. Never republish them; `regen_template_only.py all` now
  builds only `base_m base_f` and refuses a frozen page without `--allow-frozen`.
- Shared viewer code is still synced into both templates (the sync tests require it), but no work is
  done for the own engine's sake and nothing is verified on a frozen page. When a model is unfrozen,
  check it from scratch: shared changes made during the freeze were never tested on it.
