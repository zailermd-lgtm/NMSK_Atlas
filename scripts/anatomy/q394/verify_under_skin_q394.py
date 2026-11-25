#!/usr/bin/env python3
"""Q394 verifier: every structure that must lie under the skin does -- at rest and in the main pose states (Base · Male / Female).

    python3 scripts/anatomy/q394/verify_under_skin_q394.py --page-dir DIR [--rig RIG.json] [--states rest,...] [--open FILE]
                                                            [--json OUT] [--cache DIR]

Runs the census of scripts/anatomy/q394/under_skin_q394.py (the Q353 outside test, every vertex, ray-parity confirmed) on the page
(a regenerated page, or its private copy) with the page's own pose rig (data/anatomy/pose_rig_<key>.json unless --rig), in STATES.
Prints one line per state and per structure outside, then
  Q394_UNDER_SKIN_OK    every structure of the set has 0 vertices outside in every state, or every residual is on the documented
                        open-defect list (--open, default data/derived/Q394_open_defects_<page>.json) and < RESID_MM deep;
  Q394_UNDER_SKIN_FAIL  otherwise, with the counts (an open defect deeper than RESID_MM is a FAIL: it is documented, not fixed).
Excluded structures (on / through the surface) are listed with their reason (under_skin_q394.EXCLUDE).
"""
from __future__ import annotations

import argparse, json, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import under_skin_q394 as U  # noqa: E402

RESID_MM = 0.5


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-dir", required=True)
    ap.add_argument("--rig")
    ap.add_argument("--states", default=",".join(U.STATES))
    ap.add_argument("--open")
    ap.add_argument("--json")
    ap.add_argument("--cache")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    pg = U.Page(a.page_dir, a.rig, a.cache)
    inc, exc = pg.tested()
    op = Path(a.open) if a.open else REPO / f"data/derived/Q394_open_defects_{pg.d.name}.json"
    documented = {}
    if op.exists():
        for e in json.loads(op.read_text(encoding="utf-8")).get("open", []):
            documented.setdefault(e["state"], set()).add(e["id"])
    print(f"Q394 under-skin verifier: {pg.d.name}, {len(inc)} structures must lie under the skin, {len(exc)} excluded "
          f"(on / through the surface); open-defect list {op.name if op.exists() else '(none)'}", flush=True)
    rep = dict(page=pg.d.name, tested=len(inc), excluded=exc, states={})
    bad = undocumented = deep_open = 0
    for s in a.states.split(","):
        t = time.time()
        c = U.census(pg, s, ids=inc)
        sus = c.pop("__suspect__", {})
        rep["states"][s] = {k: {x: v[x] for x in ("n", "nv", "max_mm", "p95_mm", "region")} for k, v in c.items()}
        nverts = sum(v["n"] for v in c.values())
        und = [k for k in c if k not in documented.get(s, set())]
        deep = [k for k in c if k in documented.get(s, set()) and c[k]["max_mm"] >= RESID_MM]
        bad += len(c); undocumented += len(und); deep_open += len(deep)
        ok = not und and not deep
        print(f"  {'OK  ' if ok else 'FAIL'} {s:14s} structures outside {len(c):4d}, vertices {nverts:6d} "
              f"(undocumented {len(und)}, documented but >= {RESID_MM} mm {len(deep)}; parity-rejected Q353 hits {sum(sus.values())}) "
              f"[{time.time() - t:.0f}s]", flush=True)
        if not a.quiet:
            for k, v in sorted(c.items(), key=lambda kv: -kv[1]["max_mm"]):
                print(f"       {k:60s} {v['n']:5d}/{v['nv']:5d} max {v['max_mm']:6.2f} p95 {v['p95_mm']:6.2f} mm  {v['region']}"
                      f"{'' if k in documented.get(s, set()) else '  UNDOCUMENTED'}")
    ok = undocumented == 0 and deep_open == 0
    if a.json:
        Path(a.json).write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
    print(("Q394_UNDER_SKIN_OK" if ok else "Q394_UNDER_SKIN_FAIL") +
          f" {pg.d.name}: {bad} (state, structure) residuals, undocumented {undocumented}, documented >= {RESID_MM} mm {deep_open}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
