#!/usr/bin/env python3
"""Q250: articulation check of a page: for the main joints the minimum surface-to-surface clearance between the two bones (dense surface samples, mm; >0 = gap, the Z-Anatomy bones touch / overlap
slightly so a small value is normal) before vs after the deformation; a change of more than 3 mm flags a joint that the deformation opened or closed.
    python3 scripts/anatomy/q250/joint_check.py BEFORE_DIR AFTER_DIR STEM OUT.json"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.anatomy.q250 import lib as L  # noqa: E402

PAIRS = []
for sd in "lr":
    PAIRS += [(f"hip joint {sd}", f"femur_{sd}", f"hip_bone_{sd}"), (f"sacroiliac {sd}", "sacrum", f"hip_bone_{sd}"), (f"glenohumeral {sd}", f"humerus_{sd}", f"scapula_{sd}"),
              (f"acromioclavicular {sd}", f"scapula_{sd}", f"clavicle_{sd}"), (f"sternoclavicular {sd}", "sternum", f"clavicle_{sd}"), (f"elbow humero-ulnar {sd}", f"humerus_{sd}", f"ulna_{sd}"),
              (f"elbow humero-radial {sd}", f"humerus_{sd}", f"radius_{sd}"), (f"knee femoro-tibial {sd}", f"femur_{sd}", f"tibia_{sd}"), (f"knee patello-femoral {sd}", f"femur_{sd}", f"patella_{sd}"),
              (f"ankle {sd}", f"tibia_{sd}", f"talus_{sd}"), (f"proximal radio-ulnar {sd}", f"radius_{sd}", f"ulna_{sd}"), (f"wrist radio-carpal {sd}", f"radius_{sd}", f"zan_scaphoid_bone_{sd}"),
              (f"costovertebral rib 7 {sd}", f"zan_seventh_rib_{sd}", "zan_vertebra_t7"), (f"costovertebral rib 2 {sd}", f"zan_second_rib_{sd}", "zan_vertebra_t2"),
              (f"costovertebral rib 11 {sd}", f"zan_eleventh_rib_{sd}", "zan_vertebra_t11")]
PAIRS += [("pubic symphysis", "hip_bone_l", "hip_bone_r"), ("lumbosacral L5-S1", "zan_vertebra_l5", "sacrum"), ("sacrococcygeal", "sacrum", "coccyx"), ("L4-L5", "zan_vertebra_l4", "zan_vertebra_l5"),
          ("T12-L1", "zan_vertebra_t12", "zan_vertebra_l1"), ("T6-T7", "zan_vertebra_t6", "zan_vertebra_t7"), ("C7-T1", "zan_vertebra_c7", "zan_vertebra_t1"), ("atlanto-occipital", "zan_atlas_c1", "occipital"),
          ("temporomandibular l", "mandible", "temporal_l"), ("temporomandibular r", "mandible", "temporal_r")]


def clearance(S, a, b, n=40000):
    if a not in S or b not in S:
        return None
    pa = L.sample(S[a]["v"], S[a]["f"], n)[0]; pb = L.sample(S[b]["v"], S[b]["f"], n)[0]
    return float(cKDTree(pb).query(pa)[0].min())


def main(before, after, stem, out):
    _, _, S0 = L.load_page(before, stem); _, _, S1 = L.load_page(after, stem)
    res = {}
    for name, a, b in PAIRS:
        c0, c1 = clearance(S0, a, b), clearance(S1, a, b)
        if c0 is None:
            continue
        res[name] = dict(bones=[a, b], before_mm=round(c0, 2), after_mm=round(c1, 2), change_mm=round(c1 - c0, 2), flagged=bool(abs(c1 - c0) > 3.0))
    R = dict(before=before, after=after, joints=res, flagged=[k for k, v in res.items() if v["flagged"]], n=len(res))
    Path(out).write_text(json.dumps(R, indent=1) + "\n")
    print(len(res), "joints;", "flagged:", R["flagged"])


if __name__ == "__main__":
    main(*sys.argv[1:5])
