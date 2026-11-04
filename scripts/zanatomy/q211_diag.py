#!/usr/bin/env python3
"""Q211 diagnosis of the Q198 junction findings of the two Z-fitted pages: for every structure of a junction zone, how far is it from where the BONE CHAIN puts it
(base vertex + the bone-anchored field of the base -> fitted bone displacement)?  A flagged structure that sits where the chain says (<= 6 mm mean) is a pose / metric artefact of that finding;
one that does not is a real defect.   python3 scripts/zanatomy/q211_diag.py male|female JOINT [JOINT ...]  -> data/derived/Q211_diag_<which>_<joint>.json (+ print)"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.zanatomy import q211_core as K  # noqa: E402

REPO = K.REPO


def chain_deviation(which, joint, side, tag0=None, log=print):
    cfg = K.PAGES[which]
    pg, base = K.load(which), K.load(which, base=True)
    raw = json.loads((REPO / f"build/q211_raw/Q198_model_{tag0 or cfg['key0']}.json").read_text())
    j = next(x for x in raw["junctions"] if x["name"] == joint and x["side"] == side)
    c = np.asarray(j["centre_mm"], float)
    m = set(K.matched(pg, base))
    bones = [i for i in K.bone_ids(pg) if i in m]
    v0 = {i: base.v(i) for i in bones}
    v1 = {i: pg.v(i) for i in bones}
    F = K.ChainField(v0, v1, c, bones)
    log(f"{which} {joint} {side}: moving bones {sorted(F.bone_dv.items(), key=lambda kv: -kv[1])[:8]}")
    rows = {}
    for i in j["zone_ids"]:
        if i not in m or pg.sys(i) in ("bone", "skin"):
            continue
        a, b = pg.v(i), base.v(i)
        exp = b + F(b)
        dev = np.linalg.norm(a - exp, axis=1)
        mv = np.linalg.norm(a - b, axis=1)
        rows[i] = {"sys": pg.sys(i), "dev_mean": round(float(dev.mean()), 1), "dev_p90": round(float(np.percentile(dev, 90)), 1), "dev_max": round(float(dev.max()), 1), "move_mean": round(float(mv.mean()), 1),
                   "field_mean": round(float(np.linalg.norm(F(b), axis=1).mean()), 1)}
    return rows, j, F, pg, base


if __name__ == "__main__":
    which, joints = sys.argv[1], sys.argv[2:]
    for jn in joints:
        for side in ("l", "r"):
            rows, j, F, pg, base = chain_deviation(which, jn, side)
            v = np.array([r["dev_mean"] for r in rows.values()])
            print(f"  {len(rows)} zone structures; dev_mean median {np.median(v):.1f} p90 {np.percentile(v, 90):.1f}; > 6 mm: {(v > 6).sum()}, > 10 mm: {(v > 10).sum()}")
            (REPO / "data" / "derived" / f"Q211_diag_{which}_{jn}_{side}.json").write_text(json.dumps(rows, indent=0))
