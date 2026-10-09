"""Q206: vessel / nerve continuity across the wrist.  For every parent -> child pair of the chains below (both present on the page): the surface gap = the smallest vertex-to-vertex distance
between the two meshes (mm), measured on the DISPLAYED (shipped) meshes of a page.  The unfitted Z page is the reference (same chain in the Z source).
    python3 scripts/zanatomy/q206_continuity.py KEY [KEY ...]  -> data/derived/Q206_continuity.json (merged)"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q206_paths  # noqa: F401,E402
from scripts.zanatomy.q198_load import load  # noqa: E402

CHAINS = [  # (parent, child): arteries / veins / nerves across the wrist, ids without the side suffix
    ("zan_radial_artery", "zan_deep_palmar_arch"), ("zan_radial_artery", "zan_palmar_carpal_branch_of_radial_artery"), ("zan_radial_artery", "zan_superficial_palmar_arch"),
    ("zan_ulnar_artery", "zan_superficial_palmar_arch"), ("zan_ulnar_artery", "zan_dorsal_carpal_branch_of_ulnar_artery"), ("zan_radial_artery", "zan_dorsal_carpal_anastomosis"),
    ("zan_deep_palmar_arch", "zan_palmar_metacarpal_arteries"), ("zan_superficial_palmar_arch", "zan_common_palmar_digital_arteries"),
    ("zan_common_palmar_digital_arteries", "zan_proper_palmar_digital_arteries"),
    ("zan_radial_veins", "zan_deep_venous_palmar_arch"), ("zan_ulnar_veins", "zan_superficial_venous_palmar_arch"),
    ("median_n_lateral_root", "zan_palmar_branch_of_median_nerve"), ("median_n_lateral_root", "zan_common_palmar_digital_branches_of_median_nerve"),
    ("zan_common_palmar_digital_branches_of_median_nerve", "zan_proper_palmar_digital_branches_of_median_nerve"),
    ("ulnar_n", "ulnar_n_superficial_branch"), ("ulnar_n", "ulnar_n_deep_branch"), ("ulnar_n", "zan_dorsal_branch_of_ulnar_nerve"),
    ("ulnar_n_superficial_branch", "zan_common_palmar_digital_branches_of_ulnar_nerve"), ("zan_common_palmar_digital_branches_of_ulnar_nerve", "zan_proper_palmar_digital_branches_of_ulnar_nerve"),
    ("zan_communicating_branch_of_median_nerve_with_ulnar_nerve", "zan_common_palmar_digital_branches_of_ulnar_nerve"),
    ("radial_n_superficial_branch", "zan_dorsal_digital_branches_of_radial_nerve"), ("zan_dorsal_branch_of_ulnar_nerve", "zan_dorsal_digital_branches_of_ulnar_nerve"),
]


def gaps(S, side):
    by = {s["id"]: s for s in S}
    out = {}
    for p, c in CHAINS:
        a, b = by.get(f"{p}_{side}"), by.get(f"{c}_{side}")
        if a is None or b is None:
            continue
        ta, tb = cKDTree(a["v"]), cKDTree(b["v"])
        d = float(tb.query(a["v"])[0].min())
        out[f"{p} -> {c}"] = round(d, 2)
    return out


def run(key):
    S = load(key)
    return {sd: gaps(S, sd) for sd in "lr"}


if __name__ == "__main__":
    f = REPO / "data" / "derived" / "Q206_continuity.json"
    allr = json.loads(f.read_text()) if f.exists() else {}
    for k in sys.argv[1:]:
        allr[k] = run(k)
        print(k, {sd: (len(v), round(float(np.mean(list(v.values()))), 2) if v else None, max(v.values(), default=None)) for sd, v in allr[k].items()})
    f.write_text(json.dumps(allr, indent=1))
