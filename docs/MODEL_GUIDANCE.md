# Which Claude model to use for which work in this project

Owner's instruction (Q319): *"produce a guidance file for using the different models and work by it
when starting the various agents, to save tokens and still keep the results good. It may take a
little longer, but not too much — that is a price I am willing to pay."*

So the trade this file makes is deliberate: **a cheaper model or a lower effort is allowed to take
more turns, but it is not allowed to produce a worse answer.** Where a task has a history of being
got wrong by guessing, it goes to the strong model regardless of price.

Read this file before dispatching work. It is compared against the real usage log every three days
(see *Keeping this file honest* at the end) and rewritten from what the log shows, not from opinion.

- **Guidance:** this file.
- **Log of what actually ran:** `docs/model_usage/usage_log.jsonl` (+ `scripts/model_log.py`).
- **Reviews:** `docs/model_usage/reviews/` — one dated file per review.

---

## 1. The models, and what they cost

Prices per million tokens, from the `claude-api` skill's table (cached 2026‑11‑03). Always re-read
that table in a review rather than trusting the copy below.

| Model | id | in | out | cache read | context |
|---|---|---|---|---|---|
| Opus 5.5 | `claude-opus-5-5` | $4 | $20 | $0.20 | 1M |
| Opus 5 | `claude-opus-5` | $5 | $25 | ~$0.50 | 1M |
| Sonnet 5.5 | `claude-sonnet-5-5` | $2 | $10 | $0.10 | 1M |
| Haiku 5.5 | `claude-haiku-5-5` | $0.10 | $0.50 | — | 1M (prompts >100K: $0.50 / $2.50) |
| Fable 5.2 | `claude-fable-5-2` | $8 | $40 | $0.20 | 1M |

**The cache-read column is the one that decides the bill here.** Measured on this project's own
session on 2026‑11‑11: 155.9 **billion** cache-read tokens against 23 M input and 453 M output. A
long session re-reads its own context on every turn, so the cache-read price is multiplied by the
number of turns, while the input price is paid once. Opus 5.5 reads cache at 2.5× less than Opus 5;
Sonnet 5.5 at 5× less.

**Consequence, and the first rule of this file:** never run this project on Opus 5. Opus 5.5 is both
newer and cheaper on every axis. There is no task for which Opus 5 is the right answer.

---

## 2. Routing table

Pick by **what kind of wrongness the task risks**, not by how big it feels.

| Kind of work | Model | Effort | Why |
|---|---|---|---|
| Wiring an existing pattern into one more place: a new group entry, adopting a button, a CSS rule, a new field on a panel | `claude-sonnet-5-5` | `medium` | The pattern is in the file next to it. Half the price of Opus 5.5 and a fifth of its cache read. |
| Search / selection / colour plumbing, `colOf()` overrides, the systems list, the navigation-tool picker | `claude-sonnet-5-5` | `medium` | Known seams, named in `PROJECT_STATE.md`; the failure mode is a typo, not a wrong idea. |
| Geometry and measurement that must be *correct*: area, volume, circumference, Cobb, expected imaging value per pixel, ROM limits, pose kinematics | `claude-opus-5-5` | `high` | A plausible-looking wrong formula is the worst outcome this project can ship, and it will not announce itself. |
| Anything crossing module boundaries: worker protocols, cache invalidation (`rasterKey`, `axisCache`, `frames`), the pose rig against the engines, the two engines against each other | `claude-opus-5-5` | `high` | Every real bug found in Q318 lived in a seam: a debounce with no ceiling, a constant declared in the wrong scope, a system key the batching loop never visited. None were visible in the file being edited. |
| Debugging something that is reported broken and whose cause is not yet known | `claude-opus-5-5` | `high` | See above. Cheap models are fine at applying a diagnosis and poor at forming one. |
| Anatomical fact work: ROM tables, tissue properties, ligament subdivision, citations | `claude-opus-5-5` | `high` | The standing rule — real sources only, never fabricated geometry — makes a confident invention far more expensive than any token saving. |
| Running a test suite, a build, a regeneration; reading a log and reporting pass/fail | `claude-haiku-5-5` | — | No judgement required. Must return only the verdict lines, never the log. |
| Mechanical sweeps: rename across files, apply one known edit to six build dirs, collect ids from a manifest | `claude-haiku-5-5` | — | Verify the result with a test, not by reading it. |
| Something genuinely stuck after a strong-model attempt has failed twice | `claude-fable-5-2` | `high` | Twice the price of Opus 5.5. It is an escape hatch, not a default; record in the log why it was needed. |

**Effort.** Opus 5.5 defaults to `medium`, which is below where this project's hard work wants to
be, so set it explicitly. Do not use `max`: on the tasks above it has not been shown to buy anything
over `high`, and it is the most expensive setting there is. Prefer *Opus 5.5 at lower effort* over
*Sonnet at high effort* when the task has any correctness risk — a stronger model thinking less is a
better trade here than a weaker model thinking more.

---

## 3. Rules that save far more than the model choice does

Measured in the Q318 round. Each of these cost real tokens before it was fixed.

1. **Never read a published artifact in full to republish it.** `action: "list"` with
   `scope: "files"` is enough: it names the paths, which is all a `files` map needs. One full read of
   a built page costs ~15 k tokens and there are six pages. Read the page itself only when its text
   must actually be inspected.
2. **Send only what changed.** On an artifact update, files left out of `files` are kept. The
   geometry sidecars are 14 MB each and never change; listing them again is pure waste.
3. **Browser checks run in the background and return their verdict, not their output.** Every
   `verify_*_q*.py` prints `OK` / `FAIL` lines and a final `_OK` / `_FAIL`. Grep for those. A
   headless-Chromium run that is allowed to print freely will dump a page's worth of DOM.
4. **One regeneration per batch of changes, never per change.** `regen_template_only.py all` takes
   about four minutes and rewrites six pages. Finish the batch, then regenerate once.
5. **For a fast iteration loop, patch the built page in `/dev/shm` with the same string replacement
   as the source**, test there, and only then regenerate properly. This turned a four-minute cycle
   into seconds while hunting the multislices bug.
6. **Delegate verbose work, return a summary.** A subagent's whole output does not enter the main
   thread — only its report. Test runs, log analysis, exploration and doc fetching belong there.
7. **Targeted `grep` for a symbol beats opening a file**, and a large file is opened by line range.
   `viewer/zan_atlas.template.html` is ~15 k lines; a bare `grep` of a common word in it has
   produced a 220 KB tool result in this project.
8. **Quote paths and line numbers instead of pasting code** into the reply.

---

## 3a. Scope of every task: the two Base models only (owner, 2026-11-13)

The imaging-based and combined models are frozen. Brief every agent to verify on
`build/q309/viewer_zan_atlas` and `build/q309/viewer_base_female` only, to regenerate only
`base_m base_f`, and never to publish a frozen page. Verifying on a frozen page is wasted tokens.

## 4. How to dispatch an agent under this file

When starting a subagent, state in its prompt: the goal, what has already been ruled out, the files
worth reading **by path**, and the scope boundary. The prompt is the only context it gets.

- Give it the model from the table above; pass `effort` only where the table names one.
- Point it at the one or two files it needs, not at the repo.
- Tell it to return a short report: what changed, what was measured, what is still open. Not the
  diffs, not the logs.
- A check it could run in three tool calls is not worth an agent. Run it inline.
- Never let two agents edit the same file.
- **Log every agent stretch with its model, its effort, and the completion notice's
  `subagent_tokens` and tool-use count in `--notes`.** `get_session` sees only the main thread, so
  without this a subagent entry is blind (review 2026-11-13: 3 of 8 entries were).

### The project rules every agent inherits

These are not negotiable and must be repeated into any agent prompt that could touch them:

- **Real sources only.** Nothing fitted from literature is presented as measured; it is badged
  rule-based, with its volume recorded and its citations on its card.
- **Edit the single source**, `viewer/<module>/*.js` or `clinical/*.js`, then run the matching
  `scripts/sync_*.py`. Editing a template directly breaks the sync tests, and has been done by
  mistake in at least three rounds.
- **The public templates must not name the private modalities** — the Q226/Q228 word list. A member
  may claim a private button by class (`adoptSel`), never by id.
- **Nothing in `build/` is deleted without the owner's approval, per deletion.**
- Develop and push only to `claude/3d-human-anatomy-atlas-e0kbxe`; no pull request unless asked.
- No model identifier in any commit message, code comment, or anything else pushed to the
  repository. This file is the one exception, because naming the models *is* its subject.

---

## 5. Keeping this file honest

Every three days a review runs (owner's instruction: *"compare the guidance with the log and check
whether it was actually followed, and whether the guidance justifies itself, and whether there is new
information or new models worth taking into account"*). The procedure:

1. `python3 scripts/model_log.py summary --days 3` — what ran, on what, for how much.
2. Re-read the `claude-api` skill's model table. New model, or a price change? Prices have already
   moved once during this project.
3. For each routing row the log exercised, ask the two questions separately:
   - **Was it followed?** A row nothing obeyed is a row that is wrong or unknown, not a row to
     repeat louder.
   - **Did it pay?** A cheap row that produced a bug someone else had to find was not cheap. The log
     records `rework_of` for exactly this.
4. Propose a change only where the log supports it, then check the proposal against every finding in
   the log — not only the ones that prompted it — before writing it in.
5. Write the review to `docs/model_usage/reviews/<date>.md`, update this file, and commit both.

A review that changes nothing is a real outcome and is still written down.

Reviews so far: `reviews/2026-11-13.md` — no routing row changed; subagent logging made mandatory;
watch items: run-and-report inline vs Haiku, cache-write cost after restarts.
