#!/usr/bin/env python3
"""Q217: muscle | muscle adjacency of the left elbow zone by SURFACE distance: pairs of the 27 arm / forearm muscles that touch (<= 2 mm) in the unfitted Z male base; for each page the distance (mm) between the two surfaces
(0 = overlap).  arm | forearm pairs are the ones that cross the elbow.   python3 scripts/zanatomy/q217_adjacency.py zan_m zan_m_a own_m own_m_a -> data/derived/Q217_adjacency.json"""
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q217_paths  # noqa: F401,E402
from scripts.zanatomy import q198_load as L  # noqa: E402
from scripts.transfer import q217_common as C  # noqa: E402

ARM = set(C.side_ids(C.ARM))


def main(keys):
    B = {s["id"]: s for s in L.load("z_male")}
    names = [i for i in C.side_ids(C.FOREARM + C.ARM) if i in B]
    pairs = C.adjacency_pairs({i: (B[i]["v"], B[i]["f"]) for i in names}, names)
    out = {"pairs_touching_in_base": len(pairs), "arm_forearm_pairs": sum(1 for a, b, d in pairs if (a in ARM) != (b in ARM)), "pages": {}}
    for k in keys:
        S = {s["id"]: s for s in L.load(k)}
        rows = []
        for a, b, d0 in pairs:
            if a in S and b in S:
                rows.append((a, b, C.min_dist((S[a]["v"], S[a]["f"]), (S[b]["v"], S[b]["f"]))))
        arm = [r for r in rows if (r[0] in ARM) != (r[1] in ARM)]
        absent = [(a, b) for a, b, d in pairs if a not in S or b not in S]
        out["pages"][k] = dict(pairs_present=len(rows), pairs_absent=len(absent), gap_gt5=sum(1 for r in rows if r[2] > 5), gap_gt5_arm_forearm=sum(1 for r in arm if r[2] > 5),
                               arm_forearm_present=len(arm), max_gap_mm=round(max([r[2] for r in rows], default=0), 1), worst=[(a, b, round(d, 1)) for a, b, d in sorted(rows, key=lambda r: -r[2])[:6]])
        print(k, {x: y for x, y in out["pages"][k].items() if x != "worst"}, out["pages"][k]["worst"][:3], flush=True)
    (REPO / "data/derived/Q217_adjacency.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
