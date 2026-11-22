# The model-usage log

Owner (Q319): *"produce a log that follows the real use of Claude's models in this project, the use
of tokens, time, and the work that was done."*

| | |
|---|---|
| The log | `usage_log.jsonl` — one JSON object per stretch of work, append-only |
| The tool | `scripts/model_log.py` (`snapshot`, `append`, `summary`) |
| The guidance it is measured against | `../MODEL_GUIDANCE.md` |
| The three-day reviews | `reviews/<date>.md` |

## Where the numbers come from, and what they are worth

The token counters are not readable from a shell. They are reported by the session itself — the
claude-code-remote `get_session` tool, under `external_metadata.usage` — and they are **cumulative
for the whole session**. So an entry's cost is a *delta*: `snapshot` writes a mark, `append` later
subtracts it. Each entry says which it is, in `token_scope`:

- `delta` — measured between two marks. This is the number worth reasoning about.
- `session_cumulative` — no earlier mark existed, so the figure covers the session's whole history.
  The first entry in this log is one of these, and says so in its `notes`.
- `delta_suspect` — a counter went backwards (the session's container was rebuilt). Not trustworthy.
- `unknown` — the entry was written without a session dump. `summary` keeps these out of its sums
  and reports how many there were, rather than implying the work was free.

`cost_usd` is likewise the session's own figure, deltaed the same way.

## The field that makes the log useful

`rework_of`. A cheap model that produced something another round had to find and fix was not cheap,
and no token count shows that. When work exists because earlier work was wrong, say so there — the
three-day review reads it as the counterweight to the price columns.

`guidance_row` names which routing row of `MODEL_GUIDANCE.md` the work belonged to, and `followed`
says whether that row's model was the one that actually ran. A row that nothing obeys is a row that
is wrong, not a row to repeat more loudly.

## Writing an entry

```sh
S=<scratchpad>/sess.json          # a get_session dump, saved to a file

python3 scripts/model_log.py snapshot --session-json $S          # at the start
# ... the work ...
python3 scripts/model_log.py append --session-json $S \
    --round Q319 --work "spine motion in Pose, by vertebra and by segment" \
    --guidance-row geometry-and-measurement --followed yes \
    --minutes 95 --since "6 hours ago" \
    --evidence "Q319_SPINE_OK on both engines"
```

`--since` collects the round's commits from git, so the log records the work in the project's own
words rather than a summary of it. `--tokens-unknown` writes an entry with no counters: a log that
refuses imprecise entries is a log nobody writes in.

## Reading it

```sh
python3 scripts/model_log.py summary --days 3     # what the review reads
python3 scripts/model_log.py summary --all
python3 scripts/model_log.py summary --all --json # for a script
```

The summary also prints how old the last review is, and says when one is due.
