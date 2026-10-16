#!/usr/bin/env python3
"""Q202: does the seam weld change what lies inside / outside the skin?  vertices of every non-skin, non-bone structure vs the voxel skin envelope (3 mm, Q198 SkinField), old skin vs new skin
(female: the closure slab is added to the OLD skin too, so only the weld is compared).  -> data/derived/Q202_containment.json"""
import json, sys
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q202_metrics as M, q198_core as C

CASES = {"fit_f": (("build/q199/viewer_zan_female", "build/q202/viewer_zan_female"), "atlas_viewer_zan_female"),
         "fit_m": (("build/q201/viewer_zan_vhm", "build/q202/viewer_zan_vhm"), "atlas_viewer_zan_male_fitted"),
         "base_f": (("build/q197/viewer_base_female", "build/q202/viewer_base_female"), "atlas_viewer_base_female")}
SOFT = {"muscle", "nerve", "vessel", "viscera", "fascia", "joint", "bursa", "lymph"}

out = {}
for k, ((d0, d1), stem) in CASES.items():
    S0 = M.struct_list(REPO / d0, stem); S1 = M.struct_list(REPO / d1, stem)
    sk0 = [s for s in S0 if s["sys"] == "skin"]; sk1 = [s for s in S1 if s["sys"] == "skin"]
    clos = [s for s in sk1 if s["id"] == "zan_skin_perineal_closure"]
    soft = [s for s in S1 if s["sys"] in SOFT]
    res = {}
    for name, sk in (("old", sk0 + clos), ("new", sk1)):
        F = C.SkinField(sk, 3.0, close=2)
        V = np.concatenate([s["v"] for s in soft]); sd = F.signed(V)
        res[name] = {"envelope_L": round(F.vol_L, 2), "soft_vertices": int(len(V)), "outside_gt2mm_pct": round(float((sd > 2).mean() * 100), 3), "outside_gt5mm_pct": round(float((sd > 5).mean() * 100), 3)}
    out[k] = res
    print(k, res)
(REPO / "data" / "derived" / "Q202_containment.json").write_text(json.dumps(out, indent=1))
