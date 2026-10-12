#!/usr/bin/env python3
"""Q217: why the Q204 regional audit reports `inside_bone` on some carried left forearm / arm structures although none is inside a bone.  Per changed structure: deepest vertex in his EXACT bone solid (0.5 mm, q217_common.BoneVox)
vs deepest vertex in the Q204 solid (2 mm voxels, surface raster closed and eroded; q204_regions.BoneVox, finer-mesh bones fatter by ~2 mm, coarse ones by more), and the volume of each bone solid against its mesh volume.
Writes data/derived/Q217_inbone_check.json.      python3 scripts/zanatomy/q217_inbone_check.py"""
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer import q217_common as C  # noqa: E402
from scripts.transfer import q217_final_zan as F  # noqa: E402
from scripts.zanatomy import q205_pages as P5  # noqa: E402
from scripts.zanatomy.q198_core import Grid  # noqa: E402
import trimesh  # noqa: E402


def q204_field(bones):
    import scripts.zanatomy.q204_paths  # noqa: F401
    from scripts.zanatomy.q204_regions import BoneVox as QB
    allb = [dict(id=i, v=np.asarray(v, float), f=np.asarray(f, np.int64)) for i, (v, f) in bones.items()]
    lo = np.min([b["v"].min(0) for b in allb], 0) - 8
    hi = np.max([b["v"].max(0) for b in allb], 0) + 8
    return QB(allb, lo, hi)


def solids(bones):
    out = {}
    for i, (v, f) in bones.items():
        g = Grid(v.min(0) - 6, v.max(0) + 6, 2.0)
        sol = g.solid(v, f, close=1)
        m = trimesh.Trimesh(v, f)
        out[i] = dict(q204_solid_cm3=round(float(sol.sum() * 8 / 1000), 1), mesh_cm3=round(abs(float(m.volume)) / 1000, 1), vertices=int(len(v)))
    return out


def structures(page_items, bones, ids):
    ex, q = C.BoneVox(bones), q204_field(bones)
    res = {}
    for i in ids:
        v = page_items[i]
        d1 = ex.depth(v)
        _, d2 = q.fn(v)
        res[i] = dict(exact_depth_max_mm=round(float(d1.max()), 1), exact_pct_over_1mm=round(100 * float((d1 > 1).mean()), 1),
                      q204_depth_max_mm=round(float(d2.max()), 1), q204_pct_over_1p5mm=round(100 * float((d2 > 1.5).mean()), 1))
    return res


def main():
    man, blob = P5.load_page(F.OUT, F.STEM)
    pg = P5.decode(man, blob)
    rep = json.loads((REPO / "data/derived/Q217_ship_diff_zan.json").read_text())
    ids = sorted(i for i in rep["geometry_changed"] if pg[i]["m"]["sys"] in ("muscle", "vessel", "nerve"))
    bones = {i: (s["v"], s["f"]) for i, s in pg.items() if s["m"]["sys"] == "bone" and i.endswith("_l") and s["v"][:, 0].max() < -60 and s["v"][:, 1].mean() > 60}
    out = {"z_male_fitted": dict(structures=structures({i: pg[i]["v"] for i in ids}, bones, ids), bones=solids({k: v for k, v in bones.items() if k in ("ulna_l", "radius_l", "humerus_l")}))}
    from scripts.transfer.q200_bundle import Bundle
    from scripts.transfer import q217_own as O
    B = Bundle(O.OUT_BUNDLE)
    rp = json.loads((REPO / "data/derived/Q217_own_report.json").read_text())
    fixed, obones, skin = O.own_context(B)
    oi = sorted(set(rp["replaced"]) | set(rp["added"]))
    items = {}
    for i in oi:
        g = B.get(i)
        if g is not None:
            items[i] = g["v"]
    out["own_male"] = dict(structures=structures(items, obones, list(items)), bones=solids({k: v for k, v in obones.items() if k in ("ulna_l", "radius_l", "humerus_l")}))
    (REPO / "data/derived/Q217_inbone_check.json").write_text(json.dumps(out, indent=1))
    for n, o in out.items():
        bad = {i: s for i, s in o["structures"].items() if s["q204_depth_max_mm"] > 5}
        print(n, "structures", len(o["structures"]), "max exact depth", max(s["exact_depth_max_mm"] for s in o["structures"].values()), "q204 depth > 5 mm:", len(bad),
              "exact depth of those <=", max([s["exact_depth_max_mm"] for s in bad.values()] or [0]), "| bones", o["bones"])


if __name__ == "__main__":
    main()
