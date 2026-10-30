#!/usr/bin/env python3
"""Q225: exact (0.5 mm solid) re-measure of the Q204 bone-bone penetration pairs > 3 mm: depth of the vertices of bone a inside the solid of bone b and vice versa (max, share > 1 mm).
-> build/q225_agg/pairs_exact.json"""
import json, sys
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q225_paths  # noqa: F401,E402
from scripts.zanatomy.q198_load import load  # noqa: E402
from scripts.transfer import q217_domain as D  # noqa: E402
from scripts.transfer.q216_common import VoxGrid  # noqa: E402
from scipy import ndimage as ndi  # noqa: E402

out = {}
for key in ("z_male_fit", "z_female_fit"):
    d = json.loads((REPO / f"data/derived/Q225_audit_{key}.json").read_text())
    S = load(key); byid = {s["id"]: s for s in S}
    for p in d["bone_penetrating_pairs"]:
        if p["max_depth_mm"] < 4.4 or p["a"] not in byid or p["b"] not in byid:
            continue
        a, b = byid[p["a"]], byid[p["b"]]
        lo = np.minimum(a["v"].min(0), b["v"].min(0)) - 6; hi = np.maximum(a["v"].max(0), b["v"].max(0)) + 6
        h = 0.5 if np.prod(hi - lo) / 0.125 < 1.2e8 else 1.0
        g = VoxGrid(lo, hi, h)
        res = {"q204_max_depth_mm": p["max_depth_mm"], "grid_h": h}
        for nm, (x, y) in (("a_in_b", (a, b)), ("b_in_a", (b, a))):
            occ = D.bone_solid(g, y["v"], y["f"])
            if h == 0.5:
                occ = occ[::2, ::2, ::2]
            dep = ndi.distance_transform_edt(occ, sampling=1.0)
            i = np.floor((x["v"] - g.lo) + 0.5).astype(np.int64)
            ok = ((i >= 0) & (i < np.asarray(dep.shape))).all(1)
            dd = np.zeros(len(x["v"])); dd[ok] = dep[i[ok, 0], i[ok, 1], i[ok, 2]]
            res[nm] = {"max_mm": round(float(dd.max()), 1), "pct_over_1mm": round(100 * float((dd > 1).mean()), 1)}
        out[f"{key}:{p['a']}|{p['b']}"] = res
        print(key, p["a"], p["b"], res, flush=True)
(REPO / "build/q225_agg/pairs_exact.json").write_text(json.dumps(out))
