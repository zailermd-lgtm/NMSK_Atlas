"""Q207 hand skin vs the (evidence-fit) hand bones of a page, against the Z SOURCE page (same builder, unfitted):
  * per hand / wrist bone: depth of the bone surface below the FINE skin envelope (mm; median, p5, share outside > 0.5 / > 3 mm) page vs source -> 'thin' / 'thick' verdict
  * hand skin patches: edge-length ratio vs the source (p5 / median / p95), slab thickness (ray along the inward normal) page vs source
    python3 scripts/zanatomy/q207_handskin.py male|female PAGE_DIR OUT.json"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q207_core as C  # noqa: E402
from scripts.zanatomy import q207_geom as G  # noqa: E402

RAW = {"male": (REPO / "build/q197/viewer_zan_atlas", "atlas_viewer_zan_atlas"), "female": (REPO / "build/q202/viewer_base_female", "atlas_viewer_base_female")}
HAND_SKIN = re.compile(r"palm|dorsum_of_hand|digits_of_hand|nail_plate_(l|r)$|perionyx_(l|r)$|wrist|foveola|forearm")
BONE = re.compile(r"radius|ulna|scaphoid|lunate|triquetrum|pisiform|trapezi|capitate|hamate|metacarpal|finger_of_hand")


def coarse_of(page, which):
    from scripts.zanatomy.q198_core import SkinField
    skin = [dict(v=page.v(i), f=page.f(i)) for i in page.skin_ids]
    return SkinField(skin, 3.0, close=2)


class CoarseAdapter:
    def __init__(self, sf):
        self.sf = sf

    def value(self, P, outside=50.0):
        r = self.sf.signed(P)
        return r


def depth_table(page, V, coarse, side, wrist, zone_pts_lo_hi):
    lo, hi = zone_pts_lo_hi
    F = C.Fine(page, V, coarse, lo, hi, h=1.0)
    rows = {}
    for i in page.ids:
        if page.sys(i) == "bone" and i.endswith("_" + side) and BONE.search(i) and "foot" not in i:
            d = -F.value(page.v(i))                      # depth below the skin (+ inside)
            rows[i] = d
    return rows, F


def run(which, page_dir, out, log=print):
    pg = C.Page(which, src=page_dir)
    rp = C.Page(which, src=RAW[which][0], stem=RAW[which][1])
    W = pg.wrist()
    Wr = rp.wrist()
    res = {"page": str(page_dir), "sides": {}}
    cp, cr = None, None
    for side in "lr":
        zone = pg.zone_structs(side, W[side])
        pts = np.vstack([pg.v(i)[m] for i, m in zone.items()])
        lo, hi = pts.min(0) - 22, pts.max(0) + 22
        zr = rp.zone_structs(side, Wr[side])
        ptr = np.vstack([rp.v(i)[m] for i, m in zr.items()])
        lor, hir = ptr.min(0) - 22, ptr.max(0) + 22
        if cp is None:
            cp = coarse_of(pg, which)
            cr = coarse_of(rp, which)
        Vp = {i: pg.v(i) for i in pg.skin_ids}
        Vr = {i: rp.v(i) for i in rp.skin_ids}
        dp, Fp = depth_table(pg, Vp, CoarseAdapter(cp), side, W[side], (lo, hi))
        dr, Fr = depth_table(rp, Vr, CoarseAdapter(cr), side, Wr[side], (lor, hir))
        bones = {}
        for i, d in dp.items():
            s = dr.get(i)
            row = {"median_depth_mm": round(float(np.median(d)), 1), "p5_depth_mm": round(float(np.percentile(d, 5)), 1), "outside_gt0.5mm_pct": round(float((d < -0.5).mean() * 100), 1),
                   "outside_gt3mm_pct": round(float((d < -3).mean() * 100), 1), "max_outside_mm": round(float(max(-d.min(), 0)), 1)}
            if s is not None:
                row["source_median_depth_mm"] = round(float(np.median(s)), 1)
                row["source_p5_depth_mm"] = round(float(np.percentile(s, 5)), 1)
                ratio = row["median_depth_mm"] / max(row["source_median_depth_mm"], 0.5)
                row["verdict"] = "thin" if (row["outside_gt3mm_pct"] > 5 or row["p5_depth_mm"] < -1.0 or ratio < 0.5) else ("thick" if (row["median_depth_mm"] > 1.8 * row["source_median_depth_mm"] + 3.0) else "ok")
            bones[i] = row
        patches = {}
        for i in pg.skin_ids:
            if i.endswith("_" + side) and HAND_SKIN.search(i) and i in rp.S:
                er = G.edge_ratio(pg.v(i), pg.f(i), rp.v(i))
                t1 = G.slab_thickness(pg.v(i), pg.f(i))
                t0 = G.slab_thickness(rp.v(i), rp.f(i))
                patches[i] = {"edge_ratio_p5": round(float(np.percentile(er, 5)), 2), "edge_ratio_median": round(float(np.median(er)), 2), "edge_ratio_p95": round(float(np.percentile(er, 95)), 2),
                              "thickness_median_mm": round(float(np.nanmedian(t1)), 2), "source_thickness_median_mm": round(float(np.nanmedian(t0)), 2)}
        res["sides"][side] = {"bones": bones, "patches": patches,
                              "n_thin": sum(1 for r in bones.values() if r.get("verdict") == "thin"), "n_thick": sum(1 for r in bones.values() if r.get("verdict") == "thick")}
        log(f"  {which} {side}: bones thin {res['sides'][side]['n_thin']} thick {res['sides'][side]['n_thick']} of {len(bones)}")
    Path(out).write_text(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2], sys.argv[3])
