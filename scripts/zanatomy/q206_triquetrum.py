#!/usr/bin/env python3
"""Q206: can the identity / position of her RIGHT triquetrum (13.5 mm from the refit ulna, base 5.7) be resolved from her cryosection photographs?  Read-only diagnosis -> data/derived/Q206_triquetrum_r.json
Evidence: data/derived/Q192_left_hand_evidence.npz['right_hand'] (cream bone voxels of her right-hand photographs, 0.25 mm units, photograph frame = CT frame + (-1, -2, 13) mm, Q192_right_hand_validation.json).
For each Z carpal of the Q205 female page: share of its surface within 1.5 mm of a photograph bone voxel; position along her ulna axis against her CT radius / ulna ends and her CT carpal mesh."""
import json
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
NAMES = ["scaphoid", "lunate", "triquetrum", "pisiform", "trapezium", "trapezoid", "capitate", "hamate"]


def main():
    from scripts.zanatomy import q206_state as ST, q191_hand as H
    from scripts.transfer.zan_to_vhf_whole_body import load_her_meshes
    by, pre, raw = ST.load("female")
    her = load_her_meshes()
    z = np.load(REPO / "data" / "derived" / "Q192_left_hand_evidence.npz")
    ev = z["right_hand"].astype(float) * float(z["unit_mm"]) - np.array([-1.0, -2.0, 13.0])
    wr = by["radius_r"]["v"][np.argmin(by["radius_r"]["v"][:, 1])]
    E = cKDTree(ev[np.linalg.norm(ev - wr, axis=1) < 90])
    out = {"evidence_voxels_within_90mm_of_wrist": int(E.n), "carpal_support": {}}
    for n in NAMES:
        b = by[f"zan_{n}_bone_r"]
        d = E.query(H.surf_pts(b["v"], b["f"], 2500, 1))[0]
        out["carpal_support"][n] = {"surface_within_1.5mm_of_photograph_bone_pct": round(100 * float((d < 1.5).mean()), 1), "median_mm": round(float(np.median(d)), 2)}
    h = her["ulna_r"]["v"]
    c = h.mean(0)
    ax = np.linalg.svd(h - c, full_matrices=False)[2][0]
    ax = -ax if ax[1] > 0 else ax
    f = lambda v: float(((v - c) @ ax).max())
    g = lambda v: float(((v - c) @ ax).mean())
    out["along_her_ulna_axis_mm"] = {"her_CT_ulna_distal_end": round(f(h), 1), "her_CT_radius_distal_end": round(f(her["radius_r"]["v"]), 1), "refit_Z_ulna_distal_end": round(f(by["ulna_r"]["v"]), 1),
                                      "refit_Z_radius_distal_end": round(f(by["radius_r"]["v"]), 1), "Z_carpal_centroids": {n: round(g(by[f"zan_{n}_bone_r"]["v"]), 1) for n in NAMES},
                                      "her_CT_carpal_mesh_extent": [round(float(((her["carpals_r"]["v"] - c) @ ax).min()), 1), round(f(her["carpals_r"]["v"]), 1)]}
    cm = cKDTree(her["carpals_r"]["v"])
    out["Z_triquetrum_to_her_CT_carpal_mesh_mean_mm"] = round(float(cm.query(by["zan_triquetrum_bone_r"]["v"])[0].mean()), 2)
    out["gap_refit_ulna_to_Z_triquetrum_mm"] = round(float(cKDTree(by["ulna_r"]["v"]).query(by["zan_triquetrum_bone_r"]["v"])[0].min()), 2)
    out["gap_her_CT_ulna_to_Z_triquetrum_mm"] = round(float(cKDTree(h).query(by["zan_triquetrum_bone_r"]["v"])[0].min()), 2)
    out["verdict"] = ("not resolved, not changed: her photographs support the Z triquetrum where it is (88 % of its surface within 1.5 mm of cream bone voxels, median 0.5 mm; the pisiform is the weakest carpal, 32 %), "
                      "and her CT carpal mesh is 54 mm long (a carpal block is 30-35 mm) and starts exactly at the ends of her CT ulna / radius, so its proximal ~20 mm are most likely the distal radius / ulna "
                      "epiphyses (her radius / ulna meshes are cut there); neither source separates the triquetrum from its neighbours, the 13.5 mm is the surface gap refit ulna -> triquetrum (32 mm to her cut CT ulna)")
    (REPO / "data" / "derived" / "Q206_triquetrum_r.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
