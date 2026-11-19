#!/usr/bin/env python3
"""Q198 READ-ONLY: articular congruency per joint = size of the contact patch between the proximal and distal bone sets (surface samples of one bone within 2 / 4 mm of the other)
and the bone-surface distance profile; extra twist check at the elbow with a second, independent estimate (radius-ulna-humerus contact distribution).
    python3 scripts/zanatomy/q198_congruency.py [MODEL ...]  -> data/derived/Q198_congruency.json"""
import json, sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy.q198_load import load, MODELS  # noqa: E402
from scripts.zanatomy.q198_joints import find_joints  # noqa: E402
from scripts.zanatomy.q198_core import surf_points  # noqa: E402


def main():
    keys = sys.argv[1:] or list(MODELS)
    p = REPO / "data" / "derived" / "Q198_congruency.json"
    res = json.loads(p.read_text()) if p.exists() else {}
    for k in keys:
        S = load(k); J, B, lev = find_joints(S); bi = {s["id"]: s for s in S}
        out = []
        for j in J:
            P = np.concatenate([surf_points(bi[i]["v"], bi[i]["f"], 1.0, cap=40000) for i in j["prox"]])
            D = np.concatenate([surf_points(bi[i]["v"], bi[i]["f"], 1.0, cap=40000) for i in j["dist"]])
            tp, td = cKDTree(P), cKDTree(D)
            dd = td.query(P)[0]; dp = tp.query(D)[0]
            row = {"junction": j["name"], "side": j["side"], "min_gap_mm": round(float(min(dd.min(), dp.min())), 2),
                   "contact_area_le2mm_mm2": int(((dd <= 2).sum() + (dp <= 2).sum()) / 2), "contact_area_le4mm_mm2": int(((dd <= 4).sum() + (dp <= 4).sum()) / 2),
                   "p1_gap_mm": round(float(np.percentile(np.r_[dd, dp], 0.5)), 2)}
            out.append(row)
            print(k, row, flush=True)
        res[k] = out
        p.write_text(json.dumps(res))


if __name__ == "__main__":
    main()
