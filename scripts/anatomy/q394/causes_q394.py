#!/usr/bin/env python3
"""Q394: why each structure is outside the skin -- the cause class of every census entry.

    python3 scripts/anatomy/q394/causes_q394.py --census CENSUS.json --page-dir DIR --baseline DIR318 [--json OUT] [--cache DIR]

CENSUS.json is under_skin_q394's per-state census of DIR ({state: {id: entry}}). Classes:
  (a) source        at rest, and most of its outside vertices (>= half) were outside in the OLDEST kept page too (the Q318 backups
                    `*.q318` in build/q309/<dir>, before every later geometry round; for Base·F that page already carries the
                    Q250 body deformation of the build)
  (b) our edit      at rest, outside now but not in the Q318 page: the rounds that changed the structure or the skin region over
                    it, from the "Qnnn" notes on their cards (Q333 ... Q392), and whether the structure's own vertices changed
  (c) pose          outside in a pose state only (its rest vertices are under the skin)
  (d) thin skin     added to (a) / (b): under the closest outer point of the deepest outside vertex the slab is thinner than
                    THIN_MM (outer to inner sheet; <= 0: no inner sheet there, a skin hole / border)
"""
from __future__ import annotations

import argparse, json, re, sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import under_skin_q394 as U  # noqa: E402

THIN_MM = 0.5
QTAG = re.compile(r"\bQ(3[2-9]\d)\b")


def tags(rec):
    return sorted(set("Q" + m for m in QTAG.findall(json.dumps(rec or {}))))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--census", required=True)
    ap.add_argument("--page-dir", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--json")
    ap.add_argument("--cache")
    a = ap.parse_args(argv)
    C = json.loads(Path(a.census).read_text(encoding="utf-8"))
    pg = U.Page(a.page_dir, cache_dir=a.cache)
    rest = {k: v for k, v in C["rest"].items() if not k.startswith("__") and not U.excluded(k)}
    # baseline census of the same structures (same vertex count only)
    b = U.Page(Path(a.baseline) / pg.d.name if (Path(a.baseline) / pg.d.name).exists() else a.baseline, cache_dir=a.cache)
    same = [k for k in rest if k in b.V and len(b.V[k]) == len(pg.V[k])]
    cb = U.census(b, "rest", ids=same) if same else {}
    cb.pop("__suspect__", None); cb.pop("__hidden__", None)
    sk = U.Skin(pg.skin_ids, pg.V, pg.F, pg.cls())
    out = {}
    for k, e in rest.items():
        vv = np.asarray(e["verts"])
        _, so, si, own, _, q = sk.test(pg.V[k][vv])
        j = int(np.argmax(so))
        thick = float(-sk.inner.query(q[j:j + 1])[0][0])      # the slab under the closest outer point: outer to inner sheet
        skin = sk.ids[own[j]]
        moved = float(np.abs(pg.V[k] - b.V[k]).max()) if k in same else None
        skin_moved = float(np.abs(pg.V[skin] - b.V[skin]).max()) if skin in b.V and len(b.V[skin]) == len(pg.V[skin]) else None
        old = set(cb.get(k, {}).get("verts", []))
        share = len(old & set(e["verts"])) / max(1, e["n"])
        cls = "a" if (k in same and share >= 0.5) else "b"
        if thick < THIN_MM:
            cls += "+d"
        out[k] = dict(state="rest", cls=cls, n=e["n"], max_mm=e["max_mm"], p95_mm=e["p95_mm"], region=e["region"],
                      skin_thickness_mm=round(thick, 2), outside_in_q318=len(old), share_q318=round(share, 2),
                      structure_moved_since_q318_mm=None if moved is None else round(moved, 2),
                      skin_moved_since_q318_mm=None if skin_moved is None else round(skin_moved, 2),
                      rounds=sorted(set(tags(pg.g.M[k].get("rec"))) | set(tags(pg.g.M[skin].get("rec")))))
    for s, cs in C.items():
        if s == "rest":
            continue
        for k, e in cs.items():
            if k.startswith("__") or U.excluded(k):
                continue
            rv = set(rest.get(k, {}).get("verts", []))
            pose_only = [v for v in e["verts"] if v not in rv]
            if not pose_only:
                continue
            out[f"{k}@{s}"] = dict(state=s, cls="c", n=len(pose_only), n_total=e["n"], max_mm=e["max_mm"], p95_mm=e["p95_mm"],
                                   region=e["region"])
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    from collections import Counter
    print("classes:", dict(Counter(v["cls"] for v in out.values())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
