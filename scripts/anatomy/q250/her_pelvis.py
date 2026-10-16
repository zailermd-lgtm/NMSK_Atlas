"""Q250: the Visible Human FEMALE's pelvic ring in HER atlas frame: her own CT hip bones (build/q244/viewer_f_hr, label ct_vhf) + the HRA VH_F sacrum and coccyx
(HuBMAP HRA, CC BY 4.0; built from the same donor's CT; registered onto her CT pelvis in Q233 with a residual of 1.2 mm median, data/derived/Q233_hra_to_vhf_transform.json).
Her own CT sacrum label carries the coccyx and a piece of the right ilium (Q233), so the cleaner HRA sacrum / coccyx are used for those two."""
from __future__ import annotations
import json, os, sys
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))


def her_ring(own_dir="build/q244/viewer_f_hr"):
    import q233_load as Q
    from scripts.anatomy.q233 import hra_register as H
    os.environ["Q233_SRC_own_f"] = own_dir
    S0 = Q.load("own_f")
    tr = json.loads((REPO / "data/derived/Q233_hra_to_vhf_transform.json").read_text())
    s, R, t = tr["scale"], np.array(tr["rotation"]), np.array(tr["translation_mm"])
    ring = {}
    for x in S0:
        if x["id"] in ("hip_bone_l", "hip_bone_r"):
            ring[x["id"]] = (np.asarray(x["v"], float), np.asarray(x["f"]))
    for nm, key in (("VH_F_sacrum", "sacrum"), ("VH_F_coccyx", "coccyx")):
        for node, v, f in H.hra_mesh("VH_F_Pelvis"):
            if node == nm:
                ring[key] = (s * v @ R.T + t, np.asarray(f))
    return ring
