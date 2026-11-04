#!/usr/bin/env python3
"""Q225: re-measure the Q204 `inside_bone` findings (severity >= 2) with the EXACT 0.5 mm bone solid of the Q217 check (the Q204 2 mm solid is 20-40 % fatter than the bone meshes -> artefact).
Per structure: window = bbox +- 14 mm, all bones of the page that touch it, exact solid (q217_domain.bone_solid at 0.5 mm), depth (1 mm lattice) of the structure's vertices.
-> build/q225_agg/inbone_exact_<page>.json.   python3 scripts/zanatomy/q223_inbone_exact.py PAGEKEY"""
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

key = sys.argv[1]
C = json.loads((REPO / "build/q225_agg/candidates.json").read_text())[key]
want = [c for c in C if c["type"] == "soft_in_bone"]
S = load(key)
if key.startswith("own"):
    from scripts.zanatomy import q204_paths as P
    S = P.merge_zfill(S)
byid = {}
for s in S:
    byid.setdefault(s["id"], s)
bones = [s for s in S if s["sys"] == "bone"]
bb = [(b["v"].min(0), b["v"].max(0)) for b in bones]
out = {}
for c in want:
    s = byid[c["id"]]; v = s["v"]
    lo, hi = v.min(0) - 14, v.max(0) + 14
    if float(np.prod(hi - lo)) / 0.125 > 9e7:       # window too large for a 0.5 mm grid
        lo, hi = lo, hi
        h = 1.0
    else:
        h = 0.5
    g = VoxGrid(lo, hi, h)
    occ = np.zeros(g.shape, bool)
    for b, (bl, bh) in zip(bones, bb):
        if (bh < lo).any() or (bl > hi).any() or b["id"] == c["id"]:
            continue
        occ |= D.bone_solid(g, b["v"], b["f"])
    if h == 0.5:
        occ = occ[::2, ::2, ::2]; lo2 = g.lo
    else:
        lo2 = g.lo
    dep = ndi.distance_transform_edt(occ, sampling=1.0).astype(np.float32)
    i = np.floor((v - lo2) / 1.0 + 0.5).astype(np.int64)
    ok = ((i >= 0) & (i < np.asarray(dep.shape))).all(1)
    d = np.zeros(len(v), np.float32); d[ok] = dep[i[ok, 0], i[ok, 1], i[ok, 2]]
    out[c["id"]] = {"q204_pct": c["value"], "q204_detail": c["detail"], "sev": c["sev"], "exact_depth_max_mm": round(float(d.max()), 1), "exact_pct_over_1mm": round(100 * float((d > 1).mean()), 1),
                    "exact_pct_over_3mm": round(100 * float((d > 3).mean()), 1), "grid_h": h}
    print(key, c["id"], out[c["id"]]["exact_depth_max_mm"], out[c["id"]]["exact_pct_over_1mm"], flush=True)
(REPO / "build/q225_agg" / f"inbone_exact_{key}.json").write_text(json.dumps(out))
