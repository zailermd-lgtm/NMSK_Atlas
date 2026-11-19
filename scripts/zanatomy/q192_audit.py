"""Q192 audit of the LEFT hand / wrist structures (before = Q191 state, after = Q192), same criteria as Q191 (scripts/zanatomy/q191_audit.py), plus the two checks
the left-hand change needs:

  * the left rows are evaluated against the left-hand ENVELOPE (her skin united with the hand silhouettes of her own photographs; her skin mesh alone lacks the distal
    fingers), the right rows against her skin mesh exactly as in Q191;
  * forearm structures OUTSIDE the hand scope that the refit radius_l / ulna_l now touch (a bone moved 25-30 mm must not end up inside forearm muscle).

    python3 scripts/zanatomy/q192_audit.py --npz DUMP.npz --label after        (pre-decimation dump, has the Z source -> stretch)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.zanatomy import q190_metrics as Mx  # noqa: E402
from scripts.zanatomy import q191_audit as A  # noqa: E402
from scripts.zanatomy import q191_hand as H  # noqa: E402
from scripts.zanatomy import q192_left_hand as Q192  # noqa: E402


def forearm_inside_bones(by: dict, raw: dict, regions: dict, side="l") -> dict:
    """left forearm muscles / nerves / vessels outside the hand zone: share of their vertices inside the displayed radius / ulna (> 1.5 mm deep)"""
    ids, act, hb = A.zone(by, raw, side, regions)
    zb = H.merged_bones([(by[f"radius_{side}"]["v"].astype(float), by[f"radius_{side}"]["f"]), (by[f"ulna_{side}"]["v"].astype(float), by[f"ulna_{side}"]["f"])])
    out = {}
    for i, d in by.items():
        if not i.endswith("_" + side) or d["cat"] not in ("muscle", "nerve", "vessel", "tendon"):
            continue
        v = d["v"].astype(float)
        m = (v[:, 1] > 160.0) & (v[:, 1] < 360.0) & (np.abs(v[:, 0] + 190.0) < 60.0)          # the left forearm column
        if m.sum() < 20:
            continue
        dep = zb.depth(v[m])
        out[i] = {"vertices_in_column": int(m.sum()), "inside_bone_pct": round(100 * float((dep > 1.5).mean()), 2)}
    return out


def detached_from_bones(by: dict, raw: dict, regions: dict, side="l") -> dict:
    """a structure must stay where it is in the Z source relative to the hand / forearm bones: median distance of its zone vertices to the nearest displayed bone vertex vs the same distance in the
    Z source (x body scale).  An unmoved structure beside moved bones (Q192 first build: hypothenar muscles + ulnar-side vessels stayed 45 mm behind their bones) explodes this ratio."""
    ids, act, hb = A.zone(by, raw, side, regions)
    bones = hb + [f"radius_{side}", f"ulna_{side}"]
    tb = cKDTree(np.vstack([by[i]["v"][::2] for i in bones]))
    tr = cKDTree(np.vstack([raw[i][::2] * Mx.BODY_SCALE for i in bones]))
    out = {}
    for i in ids:
        a = act[i]
        if a.sum() < 20 or by[i]["cat"] == "skin":
            continue
        d1 = float(np.median(tb.query(by[i]["v"][a])[0]))
        d0 = float(np.median(tr.query(raw[i][a] * Mx.BODY_SCALE)[0]))
        out[i] = {"median_dist_to_bones_mm": round(d1, 1), "source_mm": round(d0, 1), "excess_mm": round(d1 - d0, 1)}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    from scripts.ribs_from_ct_labels import load_skin
    from scripts.transfer.zan_to_vhf_whole_body import DEFAULT_REPORT, load_her_meshes
    her, skin = load_her_meshes(), load_skin("vhf")
    regions = json.loads(DEFAULT_REPORT.read_text())["region_of_structure"]
    L = Mx.load_dump(a.npz)
    by = {d["id"]: {"v": d["v"], "f": d["f"], "cat": d["cat"]} for d in L}
    raw = {d["id"]: d["r"] for d in L}
    tab_r = A.audit(by, raw, her, skin, regions, with_stretch=True)
    env = Q192.Envelope(skin, Q192.load_evidence()).mesh()
    tab_l = A.audit(by, raw, her, env, regions, with_stretch=True)
    tab = {k: v for k, v in tab_r.items() if k.startswith("_") or v.get("side") == "r"}
    tab.update({k: v for k, v in tab_l.items() if not k.startswith("_") and v.get("side") == "l"})
    res = {"label": a.label, "note": "left rows vs the left-hand envelope (her skin + photograph silhouettes), right rows vs her skin mesh", "thresholds": A.THRESH, "table": tab,
           "issues": A.issues(tab), "left_forearm_inside_radius_ulna": forearm_inside_bones(by, raw, regions),
           "left_distance_to_bones_vs_source": detached_from_bones(by, raw, regions)}
    out = Path(a.out or REPO / "data" / "derived" / f"Q192_hand_audit_{a.label}.json")
    out.write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res["issues"]["by_criterion"], indent=1))
    dd = res["left_distance_to_bones_vs_source"]
    print("left structures > 8 mm farther from the hand/forearm bones than in the Z source:", sorted((round(v["excess_mm"]), k) for k, v in dd.items() if v["excess_mm"] > 8.0))


if __name__ == "__main__":
    main()
