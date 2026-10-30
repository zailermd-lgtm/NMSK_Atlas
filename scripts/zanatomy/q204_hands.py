#!/usr/bin/env python3
"""Q204 READ-ONLY: fingers / hands of a Z page: chain links (wrist radius/ulna -> carpals, carpals -> metacarpals, metacarpal -> proximal -> middle -> distal phalanx) surface gaps, per-link bend angle,
bone length, bone vertices outside the skin; run on the fitted pages AND their unfitted bases (same ids) so the change made by the fit is visible.
    python3 scripts/zanatomy/q204_hands.py MODEL   -> build/q204_raw/Q204_hands_<MODEL>.json"""
import json, re, sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q204_paths  # noqa: F401,E402
from scripts.zanatomy.q198_load import load  # noqa: E402
from scripts.zanatomy.q198_core import SkinField, surf_points  # noqa: E402
from scripts.zanatomy import q198_audit as QA  # noqa: E402

ORD = ["first", "second", "third", "fourth", "fifth"]


def axis_len(v):
    c = v.mean(0)
    u, s, vt = np.linalg.svd(v - c, full_matrices=False)
    t = (v - c) @ vt[0]
    return c, vt[0], float(t.max() - t.min())


def main(key):
    kind = "zan"
    S = load(key)
    by = {s["id"]: s for s in S}
    skin_structs = [s for s in S if s["sys"] == "skin"]
    skin = SkinField(skin_structs + QA.female_sealers(key, S), 3.0, close=2)
    pts = {}

    def P(i):
        if i not in pts:
            pts[i] = surf_points(by[i]["v"], by[i]["f"], 0.8, cap=30000)
        return pts[i]

    def gap(a, b):
        return round(float(cKDTree(P(a)).query(P(b)[:: max(1, len(P(b)) // 5000)])[0].min()), 2)
    out = {"model": key, "sides": {}}
    for sd in ("l", "r"):
        rec = {"links": [], "fingers": {}}
        carp = [i for i in by if re.search(rf"(scaphoid|lunate|triquetrum|pisiform|trapezium|trapezoid|capitate|hamate)_bone_{sd}$", i)]
        ra, ul = f"radius_{sd}", f"ulna_{sd}"
        for c in carp:
            g = min(gap(ra, c) if ra in by else 99, gap(ul, c) if ul in by else 99)
            rec["links"].append({"link": f"forearm bones -> {c[4:-2]}", "gap_mm": g, "kind": "wrist"}) if re.search(r"scaphoid|lunate|triquetrum", c) else None
        cids = {}
        for k, o in enumerate(ORD, 1):
            mc = f"zan_{o}_metacarpal_bone_{sd}"
            ch = [mc] + [f"zan_{t}_phalanx_of_{o}_finger_of_hand_{sd}" for t in ("proximal", "middle", "distal")]
            ch = [x for x in ch if x in by]
            cids[o] = ch
            if mc in by and carp:
                g = min(gap(mc, c) for c in carp)
                rec["links"].append({"link": f"carpals -> {o} metacarpal", "gap_mm": g, "kind": "carpometacarpal"})
            f = {"bones": [], "links": []}
            for a, b in zip(ch[:-1], ch[1:]):
                f["links"].append({"link": f"{a[4:-2]} -> {b[4:-2]}", "gap_mm": gap(a, b)})
            ax = []
            for i in ch:
                c, a_, L = axis_len(by[i]["v"])
                sdv = skin.signed(by[i]["v"])
                f["bones"].append({"id": i, "length_mm": round(L, 1), "outside_skin_pct": round(100 * float((sdv > 3).mean()), 1), "outside_skin_max_mm": round(float(max(sdv.max(), 0)), 1)})
                ax.append(a_)
            f["bend_deg"] = [round(float(np.degrees(np.arccos(np.clip(abs(float(np.dot(ax[j], ax[j + 1]))), 0, 1)))), 1) for j in range(len(ax) - 1)]
            rec["fingers"][o] = f
        out["sides"][sd] = rec
    (REPO / "build" / "q204_raw" / f"Q204_hands_{key}.json").write_text(json.dumps(out))
    print(key, "hands done")


if __name__ == "__main__":
    main(sys.argv[1])
