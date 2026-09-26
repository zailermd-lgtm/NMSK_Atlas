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
