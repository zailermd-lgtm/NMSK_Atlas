#!/usr/bin/env python3
"""The project's record of which Claude model actually did which work, and what it cost.

Owner (Q319): "produce a log that follows the real use of Claude's models in this project, the use
of tokens, time, and the work that was done", and then, every three days, "compare the guidance with
the log and check whether it was actually followed, and whether the guidance justifies itself".

So this is a log with a purpose: it exists to be argued with. `docs/MODEL_GUIDANCE.md` says which
model should do which work; this file records which one did, what it cost, and -- the field that
decides whether a cheap choice was really cheap -- whether anything had to be redone afterwards.

WHERE THE NUMBERS COME FROM. The token counters are not visible to a shell: they are reported by the
session itself (the claude-code-remote `get_session` tool, under `external_metadata.usage`) and they
are CUMULATIVE for the whole session. So the flow is:

    # once, at the start of a stretch of work
    <get_session> > /tmp/.../s.json && python3 scripts/model_log.py snapshot --session-json /tmp/.../s.json

    # at the end of it, with the same call again: the delta is the work's real cost
    <get_session> > /tmp/.../s.json
    python3 scripts/model_log.py append --session-json /tmp/.../s.json \
        --round Q319 --work "spine motion in Pose, by vertebra and by segment" \
        --guidance-row "geometry-and-measurement" --followed yes

Without a snapshot to subtract, `append` records the counters as cumulative and says so, rather than
reporting a session's whole history as the cost of one afternoon. An entry may also be written with
no session file at all (`--tokens-unknown`), because a log that refuses imprecise entries is a log
nobody writes in; `summary` then counts it separately instead of pretending it was free.

    python3 scripts/model_log.py summary --days 3        # what the three-day review reads
    python3 scripts/model_log.py summary --all --json    # the same, for a script
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DIR = REPO / "docs" / "model_usage"
LOG = DIR / "usage_log.jsonl"
STATE = DIR / ".session_state.json"
GUIDANCE = REPO / "docs" / "MODEL_GUIDANCE.md"

# the routing rows of docs/MODEL_GUIDANCE.md, short keys so an entry can name the row it followed
ROWS = [
    "existing-pattern",          # wiring a known pattern into one more place
    "ui-plumbing",               # search / selection / colour / systems list / tool picker
    "geometry-and-measurement",  # anything that must be numerically right
    "cross-module",              # worker protocols, cache invalidation, engine vs engine
    "unknown-cause-debug",       # reported broken, cause not yet known
    "anatomical-fact",           # ROM, tissue properties, subdivision, citations
    "run-and-report",            # tests, builds, regeneration, log reading
    "mechanical-sweep",          # renames, applying one known edit N times
    "stuck",                     # escape hatch after the strong model has failed twice
    "none",                      # work that predates the guidance, or does not fit a row
]
TOKEN_KEYS = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_session(path: Path) -> dict:
    """Pull the few fields that matter out of a get_session dump (its shape may grow; be lenient)."""
    d = json.loads(path.read_text())
    ccr = d.get("ccr", d)
    ctx = ccr.get("session_context") or {}
    ext = ccr.get("external_metadata") or {}
    usage = ext.get("usage") or {}
    return {
        "session": ccr.get("id"),
        "model": ext.get("last_served_model") or ctx.get("model") or ccr.get("configured_model"),
        "effort": ext.get("effort_level") or ctx.get("effort_level"),
        "tokens": {k: int(usage.get(k) or 0) for k in TOKEN_KEYS},
        "cost_usd": float(usage.get("cost_usd") or 0.0),
        "updated_at": ccr.get("updated_at"),
    }


def load_state() -> dict:
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {}


def save_state(st: dict) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=1, sort_keys=True) + "\n")


def entries() -> list[dict]:
    if not LOG.exists():
        return []
    out = []
    for line in LOG.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except ValueError:
                pass            # a hand-edited line must not break the review
    return out


def git_commits(since: str | None) -> list[str]:
    """The commits that landed in the window: the work, in the project's own words."""
    if not since:
        return []
    try:
        r = subprocess.run(["git", "log", "--oneline", f"--since={since}", "--no-merges"],
                           cwd=REPO, capture_output=True, text=True, timeout=30)
        return [l for l in r.stdout.splitlines() if l.strip()] if r.returncode == 0 else []
    except (OSError, subprocess.SubprocessError):
        return []


def cmd_snapshot(a) -> int:
    s = read_session(Path(a.session_json))
    st = load_state()
    st[s["session"] or "unknown"] = {"at": utcnow(), "tokens": s["tokens"], "cost_usd": s["cost_usd"]}
    save_state(st)
    print(f"snapshot {s['session']} at {utcnow()}: " +
          ", ".join(f"{k.replace('_tokens','')}={s['tokens'][k]:,}" for k in TOKEN_KEYS))
    return 0


def cmd_append(a) -> int:
    DIR.mkdir(parents=True, exist_ok=True)
    e: dict = {"ts": utcnow(), "round": a.round, "work": a.work, "actor": a.actor,
               "guidance_row": a.guidance_row}
    if a.followed is not None:
        e["followed"] = a.followed == "yes"
    if a.rework_of:
        e["rework_of"] = a.rework_of
    if a.minutes is not None:
        e["minutes"] = a.minutes
    if a.notes:
        e["notes"] = a.notes

    if a.session_json:
        s = read_session(Path(a.session_json))
        e["session"] = s["session"]
        e["model"] = a.model or s["model"]
        e["effort"] = a.effort or s["effort"]
        prev = load_state().get(s["session"] or "unknown")
        if prev:
            e["tokens"] = {k: s["tokens"][k] - int(prev["tokens"].get(k, 0)) for k in TOKEN_KEYS}
            e["cost_usd"] = round(s["cost_usd"] - float(prev.get("cost_usd") or 0.0), 4)
            e["token_scope"] = "delta"
            e["since"] = prev["at"]
            if any(v < 0 for v in e["tokens"].values()):   # the session restarted its counters
                e["token_scope"] = "delta_suspect"
        else:
            e["tokens"] = s["tokens"]
            e["cost_usd"] = round(s["cost_usd"], 4)
            e["token_scope"] = "session_cumulative"
        # and move the mark forward, so the next entry measures from here
        st = load_state()
        st[s["session"] or "unknown"] = {"at": e["ts"], "tokens": s["tokens"], "cost_usd": s["cost_usd"]}
        save_state(st)
    else:
        if not a.tokens_unknown:
            print("refusing: give --session-json for real counters, or --tokens-unknown to say so")
            return 2
        e["model"] = a.model
        e["effort"] = a.effort
        e["token_scope"] = "unknown"

    if a.since:
        e["commits"] = git_commits(a.since)
    if a.evidence:
        e["evidence"] = a.evidence

    with LOG.open("a") as fh:
        fh.write(json.dumps(e, sort_keys=True) + "\n")
    print(f"logged {e['round']}: {e['work'][:70]} [{e.get('model')}/{e.get('effort')}, "
          f"{e['token_scope']}]")
    return 0


def fmt_tok(t: dict) -> str:
    return (f"in {t.get('input_tokens',0):,} out {t.get('output_tokens',0):,} "
            f"cache-r {t.get('cache_read_tokens',0):,} cache-w {t.get('cache_write_tokens',0):,}")


def cmd_summary(a) -> int:
    es = entries()
    if not a.all:
        cut = datetime.now(timezone.utc) - timedelta(days=a.days)
        kept = []
        for e in es:
            try:
                if datetime.strptime(e["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) >= cut:
                    kept.append(e)
            except (KeyError, ValueError):
                pass
        es = kept
    if a.json:
        print(json.dumps(es, indent=1, sort_keys=True))
        return 0

    if not es:
        print(f"no entries in the last {a.days} days" if not a.all else "the log is empty")
        return 0

    print(f"=== {len(es)} entries" + ("" if a.all else f" in the last {a.days} days") + " ===")
    # Only `delta` entries may be ADDED UP. A `session_cumulative` entry already contains every delta
    # recorded after it, so adding the two together counts the same tokens twice -- which the first
    # summary of this log did, reporting a session's whole history as the cost of one afternoon.
    by_model: dict[str, dict] = {}
    unknown = cumulative = 0
    for e in es:
        m = f"{e.get('model') or '?'} / {e.get('effort') or '-'}"
        b = by_model.setdefault(m, {"n": 0, "cost": 0.0, "minutes": 0.0,
                                    **{k: 0 for k in TOKEN_KEYS}})
        b["n"] += 1
        b["minutes"] += float(e.get("minutes") or 0)
        if e.get("token_scope") == "delta":
            b["cost"] += float(e.get("cost_usd") or 0)
            for k in TOKEN_KEYS:
                b[k] += int((e.get("tokens") or {}).get(k, 0))
        elif e.get("token_scope") == "session_cumulative":
            cumulative += 1
        else:
            unknown += 1
    for m, b in sorted(by_model.items()):
        print(f"  {m:<34} {b['n']:>3} entr. {b['minutes']:>7.0f} min  ${b['cost']:>10.2f}  {fmt_tok(b)}")
    print("  (the sums are of measured deltas only)")
    if cumulative:
        print(f"  ({cumulative} entr. hold a whole session's cumulative counters, which already contain the "
              f"deltas above -- listed below, never added in)")
        for e in es:
            if e.get("token_scope") == "session_cumulative":
                t = e.get("tokens") or {}
                print(f"      {e['ts'][:10]} {e.get('model')}: ${float(e.get('cost_usd') or 0):,.2f}  {fmt_tok(t)}")
    if unknown:
        print(f"  ({unknown} entr. with no measured counters -- not in the sums above)")

    print("\n--- against the guidance ---")
    rows: dict[str, dict] = {}
    for e in es:
        r = rows.setdefault(e.get("guidance_row") or "none", {"n": 0, "followed": 0, "broke": 0, "unset": 0})
        r["n"] += 1
        if e.get("followed") is True:
            r["followed"] += 1
        elif e.get("followed") is None:
            r["unset"] += 1
        if e.get("rework_of"):
            r["broke"] += 1
    for name in ROWS:
        r = rows.get(name)
        if not r:
            continue
        print(f"  {name:<26} {r['n']:>3} used, {r['followed']:>3} followed the row, "
              f"{r['unset']:>3} unstated, {r['broke']:>3} needed rework")
    stray = sorted(set(rows) - set(ROWS))
    if stray:
        print(f"  rows not in the guidance: {', '.join(stray)}")

    rework = [e for e in es if e.get("rework_of")]
    if rework:
        print("\n--- what had to be redone (a cheap choice that produced this was not cheap) ---")
        for e in rework:
            print(f"  {e['ts'][:10]} {e.get('model')}: {e['work'][:62]}")
            print(f"      redoing: {e['rework_of'][:90]}")

    last = DIR / "reviews"
    revs = sorted(last.glob("*.md")) if last.is_dir() else []
    print(f"\nlast review: {revs[-1].name if revs else 'none yet'}; guidance: "
          f"{'present' if GUIDANCE.exists() else 'MISSING'}")
    if revs:
        age = datetime.now(timezone.utc) - datetime.fromtimestamp(revs[-1].stat().st_mtime, timezone.utc)
        print(f"             {age.days} days old" + ("  <-- a review is due (every 3 days)" if age.days >= 3 else ""))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("snapshot", help="mark the counters now, so the next append is a delta")
    s.add_argument("--session-json", required=True, help="a get_session dump")
    s.set_defaults(fn=cmd_snapshot)

    a = sub.add_parser("append", help="record a stretch of work")
    a.add_argument("--round", required=True, help="the round it belongs to, e.g. Q319")
    a.add_argument("--work", required=True, help="what was done, in one line")
    a.add_argument("--guidance-row", default="none", choices=ROWS,
                   help="which routing row of docs/MODEL_GUIDANCE.md this work belongs to")
    a.add_argument("--followed", choices=["yes", "no"], default=None,
                   help="was that row's model actually used")
    a.add_argument("--rework-of", default=None,
                   help="if this work exists because something earlier was wrong, say what")
    a.add_argument("--actor", default="main", help='"main", or "subagent:<type>"')
    a.add_argument("--model", default=None, help="override the model the session reports")
    a.add_argument("--effort", default=None)
    a.add_argument("--minutes", type=float, default=None)
    a.add_argument("--since", default=None, help="git --since for the commits of this stretch")
    a.add_argument("--evidence", default=None, help="what proves it worked (a verifier's verdict)")
    a.add_argument("--notes", default=None)
    a.add_argument("--session-json", default=None, help="a get_session dump, for real counters")
    a.add_argument("--tokens-unknown", action="store_true",
                   help="write the entry with no counters rather than not writing it")
    a.set_defaults(fn=cmd_append)

    m = sub.add_parser("summary", help="what the three-day review reads")
    m.add_argument("--days", type=int, default=3)
    m.add_argument("--all", action="store_true")
    m.add_argument("--json", action="store_true")
    m.set_defaults(fn=cmd_summary)

    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
