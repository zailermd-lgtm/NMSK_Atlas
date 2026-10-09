"""Q207 evaluation of a skin state V (dict id -> vertices) of a page against the structures of the hand / wrist / distal-forearm zone:
 * AUDIT measure (Q198 SkinField, h = 3 mm, closing 2; > 3 mm outside counts; the female with the Q198 sealers) -- what Q198 / Q204 / Q206 report
 * FINE measure (1 mm envelope of q207_core.Fine; > 0.5 mm / > 3 mm outside)
 * the person's own skin (watertight CT / cryosection surface): share of skin vertices outside it
 * slab thickness, edge-length ratio vs the Z source, self / mutual intersections of the skin faces."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q207_core as C  # noqa: E402
from scripts.zanatomy import q207_geom as G  # noqa: E402

BONE = re.compile(r"radius|ulna|scaphoid|lunate|triquetrum|pisiform|trapezi|capitate|hamate|metacarpal|finger_of_hand")
CLASSES = ("bone", "vessel", "nerve", "joint", "bursa", "fascia", "muscle", "cartilage", "lymph")


def sealers(which, page):
    if which != "female":
        return []
    from scripts.zanatomy.q198_audit import female_sealers
    S = [dict(id=i, name=e["m"]["name"], sys=e["m"]["sys"], side=e["m"]["side"], v=e["v"], f=e["f"]) for i, e in page.S.items() if e["m"]["sys"] == "skin"]
    return female_sealers("z_female_fit", S)


def coarse_field(which, page, V, seal=None):
    from scripts.zanatomy.q198_core import SkinField
    skin = [dict(id=i, sys="skin", v=V[i], f=page.f(i)) for i in page.skin_ids]
    return SkinField(skin + (seal if seal is not None else sealers(which, page)), 3.0, close=2)


class CoarseAdapter:
    def __init__(self, sf):
        self.sf = sf

    def value(self, P, outside=50.0):
        return self.sf.signed(P)


def zone_measure(page, V, which, side, wrist, coarse_sf, own=None, zone=None, demand_only=None):
    """-> dict with per-class and per-structure numbers of the zone structures against the skin state V"""
    zone = zone or page.zone_structs(side, wrist)
    pts = np.vstack([page.v(i)[m] for i, m in zone.items()])
    lo, hi = pts.min(0) - 22, pts.max(0) + 22
    fine = C.Fine(page, V, CoarseAdapter(coarse_sf), lo, hi, h=1.0)
    rows = {}
    for i, m in zone.items():
        v = page.v(i)[m]
        sa = coarse_sf.signed(v)
        sf = fine.value(v)
        rows[i] = {"sys": page.sys(i), "n": int(m.sum()), "audit_gt3_pct": round(float((sa > 3).mean() * 100), 1), "audit_max_mm": round(float(max(sa.max(), 0)), 1),
                   "fine_gt0.5_pct": round(float((sf > 0.5).mean() * 100), 1), "fine_gt3_pct": round(float((sf > 3).mean() * 100), 1), "fine_max_mm": round(float(max(sf.max(), 0)), 1)}
    summ = {}
    for c in CLASSES:
        r = [x for x in rows.values() if x["sys"] == c]
        if r:
            summ[c] = {"structures": len(r), "audit_gt5pct": sum(x["audit_gt3_pct"] > 5 for x in r), "fine_gt5pct": sum(x["fine_gt3_pct"] > 5 for x in r),
                       "audit_mean_outside_pct": round(float(np.mean([x["audit_gt3_pct"] for x in r])), 2), "fine_mean_gt0.5_pct": round(float(np.mean([x["fine_gt0.5_pct"] for x in r])), 2),
                       "audit_worst_mm": max(x["audit_max_mm"] for x in r), "fine_worst_mm": max(x["fine_max_mm"] for x in r)}
    bones = {i: x for i, x in rows.items() if x["sys"] == "bone" and BONE.search(i)}
    return {"structures": rows, "classes": summ, "bones": bones, "fine_inside_frac": round(float(fine.inside_true.mean()), 4)}


def skin_quality(page, V, V0, raw, ids, own=None):
    """per moved patch: thickness, edge ratio vs source, own-skin containment"""
    out = {}
    for i in ids:
        v, v0, f = V[i], V0[i], page.f(i)
        t1, t0 = G.slab_thickness(v, f), G.slab_thickness(v0, f)
        er1 = G.edge_ratio(v, f, raw[i]) if i in raw else None
        er0 = G.edge_ratio(v0, f, raw[i]) if i in raw else None
        row = {"thickness_median_mm": [round(float(np.nanmedian(t0)), 2), round(float(np.nanmedian(t1)), 2)], "thickness_p5_mm": [round(float(np.nanpercentile(t0, 5)), 2), round(float(np.nanpercentile(t1, 5)), 2)]}
        if er1 is not None:
            row["edge_ratio_p5_p95"] = [[round(float(np.percentile(er0, 5)), 2), round(float(np.percentile(er0, 95)), 2)], [round(float(np.percentile(er1, 5)), 2), round(float(np.percentile(er1, 95)), 2)]]
        if own is not None:
            s0, s1 = own.sd(v0), own.sd(v)
            row["outside_own_skin_gt2mm_pct"] = [round(float((s0 > 2).mean() * 100), 2), round(float((s1 > 2).mean() * 100), 2)]
        out[i] = row
    return out


def intersections(page, V, ids):
    m = {i: (V[i], page.f(i)) for i in ids}
    Vc, F, ow, names = G.concat(m)
    pr = G.intersecting_pairs(Vc, F, ow)
    return len(pr), G.count_by_owner(pr, ow, names)
