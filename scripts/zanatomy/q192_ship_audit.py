"""Q192 no-regression check on the SHIPPED geometry: every structure of build/viewer_zan_female_q192 vs build/viewer_zan_female_q191, vertex by vertex.

    python3 scripts/zanatomy/q192_ship_audit.py [--before DIR] [--after DIR] [--out data/derived/Q192_ship_diff.json]
Unchanged = same vertex count and largest vertex displacement <= 0.05 mm (16-bit quantisation of a mesh whose bounding box did not move is bit-identical; a moved
mesh is compared as point sets).  Everything outside the LEFT hand / wrist scope (scripts/zanatomy/q191_hand.scope('l') + left hand bones + radius_l / ulna_l) must be
unchanged: trunk, legs, feet, head, the whole right arm and hand."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q191_hand as H  # noqa: E402
from scripts.zanatomy import trunk_refit_q186c_audit as A186  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default=str(REPO / "build" / "viewer_zan_female_q191"))
    ap.add_argument("--after", default=str(REPO / "build" / "viewer_zan_female_q192"))
    ap.add_argument("--out", default=str(REPO / "data" / "derived" / "Q192_ship_diff.json"))
    a = ap.parse_args(argv)
    from scripts.transfer.zan_to_vhf_whole_body import DEFAULT_REPORT
    regions = json.loads(DEFAULT_REPORT.read_text())["region_of_structure"]
    Mb, Ma = A186.load_viewer(Path(a.before)), A186.load_viewer(Path(a.after))
    assert set(Mb) == set(Ma), "structure sets differ"
    pend = [{"mesh_id": k, "cat": m["sys"]} for k, m in Mb.items()]
    left_scope = set(H.scope(pend, regions, "l")) | set(H.bone_ids("l")["carpals"] + H.bone_ids("l")["mc"] + H.bone_ids("l")["phal"]) | {"radius_l", "ulna_l"}
    right_scope = set(H.scope(pend, regions, "r")) | set(sum(H.bone_ids("r").values(), [])) | {"radius_r", "ulna_r"}
    changed, unchanged, surface_p99 = {}, 0, {}
    for k, mb in Mb.items():
        ma = Ma[k]
        if len(mb["v"]) != len(ma["v"]) or len(mb["f"]) != len(ma["f"]):
            d = float("inf")
        else:
            d = float(np.abs(mb["v"] - ma["v"]).max())
        if d > 0.05 and np.isfinite(d):
            d = float(max(cKDTree(mb["v"]).query(ma["v"])[0].max(), cKDTree(ma["v"]).query(mb["v"])[0].max()))
        if d <= 0.05:
            unchanged += 1
        else:
            changed[k] = round(d, 2) if np.isfinite(d) else "topology changed"
            # surface-to-surface distance (decimation re-samples a mesh whose input moved by a hair: the vertex distance overstates the change)
            A_, B_ = H.surf_pts(mb["v"], mb["f"], 4000), H.surf_pts(ma["v"], ma["f"], 4000)
            sd = max(float(np.percentile(cKDTree(B_).query(A_)[0], 99)), float(np.percentile(cKDTree(A_).query(B_)[0], 99)))
            surface_p99[k] = round(sd, 2)
    outside = [k for k in changed if k not in left_scope]
    reg = {}
    for k in Mb:
        r = regions.get(k, "other")
        reg.setdefault(r, [0, 0])
        reg[r][0] += 1
        reg[r][1] += int(k not in changed)
    out = {"structures": len(Mb), "unchanged_within_0.05mm": unchanged, "changed": len(changed), "outside_left_hand_scope_changed": outside,
           "outside_left_hand_scope_changed_detail": {k: changed[k] for k in outside},
           "right_hand_changed": sum(1 for k in changed if k in right_scope), "right_hand_scope_structures": len(right_scope & set(Mb)),
           "left_hand_scope_structures": len(left_scope & set(Mb)), "left_hand_scope_changed": sum(1 for k in changed if k in left_scope),
           "outside_left_hand_scope_surface_p99_mm": {k: surface_p99[k] for k in outside},
           "outside_left_hand_scope_surface_p99_max_mm": max([surface_p99[k] for k in outside] or [0.0]),
           "outside_left_hand_scope_surface_p99_gt_1mm": [k for k in outside if surface_p99[k] > 1.0],
           "changed_ids": changed, "unchanged_by_q168_region": {k: {"total": v[0], "unchanged": v[1]} for k, v in reg.items()}}
    Path(a.out).write_text(json.dumps(out, indent=1))
    print({k: v for k, v in out.items() if k not in ("changed_ids", "unchanged_by_q168_region", "outside_left_hand_scope_changed_detail", "outside_left_hand_scope_surface_p99_mm", "outside_left_hand_scope_changed")})
    print(out["outside_left_hand_scope_changed_detail"])


if __name__ == "__main__":
    main()
